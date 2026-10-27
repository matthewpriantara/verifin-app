from __future__ import annotations

import logging
import re
from urllib.parse import urlparse, urlunparse

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.v1.verify.schema import VerifyResponse
from app.config import LLM_MODEL, VERIFY_CACHE_ENABLED
from app.database.models import JobCase
from app.services.hasher import compute_content_sha256
from app.api.v1.verify.pipeline import _build_osint_summary, _to_response
from app.services.llm.verifin_reasoning import _soften_summary_claims

logger = logging.getLogger(__name__)
CACHE_SCHEMA_VERSION = 15


def _case_hash(raw_input: str) -> str:
    # Spasi/baris baru berlebih tidak membedakan lowongan; tanpa normalisasi ini teks yang sama
    # dengan baris baru di akhir tersimpan dua kali.
    normalized = re.sub(r"\s+", " ", (raw_input or "").strip())
    return compute_content_sha256(f"{normalized}\nmodel:{LLM_MODEL}")


def _legacy_case_hash(raw_input: str) -> str:
    """Hash sebelum normalisasi spasi; dipakai agar run ulang memperbarui baris lama, bukan menambah."""
    return compute_content_sha256(f"{raw_input}\nmodel:{LLM_MODEL}")


def _osint_has_failures(osint_results: dict | None) -> bool:
    """True bila ada pemeriksaan yang gagal dijalankan (bukan sekadar tidak menemukan apa-apa)."""
    if not osint_results:
        return False
    if any(isinstance(v, dict) and "error" in v for v in osint_results.values()):
        return True
    web = osint_results.get("web") or {}
    searches = web.get("searches") or []
    if searches and all(s.get("status") in ("UNAVAILABLE", "TIMEOUT") for s in searches):
        return True
    if (web.get("scam_check") or {}).get("status") == "UNAVAILABLE":
        return True
    for phone in osint_results.get("phones") or []:
        if isinstance(phone, dict) and phone.get("probe_status") in ("UNAVAILABLE", "TIMEOUT"):
            return True
    for addr in osint_results.get("address_validations") or []:
        details = (addr or {}).get("address_details") or {}
        if details.get("probe_status") in ("UNAVAILABLE", "TIMEOUT"):
            return True
    return False

def _save_case_to_db(
    db: Session,
    raw_text: str,
    analysis: dict,
    osint_results: dict | None,
    entities: dict | None = None,
    source: str = "text",
) -> dict:

    if db is None:
        return {"status": "SKIPPED", "case_id": None}

    try:
        text_hash = _case_hash(raw_text)
        ent = dict(entities or analysis.get("entities_analyzed") or {})
        companies = list(ent.get("companies") or [])
        phones = list(ent.get("phones") or [])
        emails = list(ent.get("emails") or [])
        urls = list(ent.get("urls") or [])
        addresses = list(ent.get("addresses") or [])
        salaries = list(ent.get("salaries") or [])

        uniq_c = {x.upper().strip() for x in companies if isinstance(x, str) and x.strip()}
        if len(uniq_c) > 1 or (len(companies) > 1 and len(phones) > 1) or analysis.get("is_multi_employer"):
            ent["is_multi_employer"] = True
        if analysis.get("not_a_job_posting") or ent.get("not_a_job_posting"):
            ent["not_a_job_posting"] = True

        if source == "url" and not urls:
            match_target = re.search(r"^URL Target:\s*(\S+)", raw_text or "", re.M)
            if match_target:
                target_url = match_target.group(1).strip()
                urls.append(target_url)
                if isinstance(ent, dict):
                    ent["urls"] = list(urls)
        llm_payload = {
            "summary": analysis.get("summary", ""),
            "risk_factors": analysis.get("risk_factors") or [],
            "safe_factors": analysis.get("safe_factors") or [],
            "recommendations": analysis.get("recommendations") or [],
            "model_used": analysis.get("model_used"),
            "corrected_company_name": analysis.get("corrected_company_name"),
            "shap_explanation": analysis.get("shap_explanation"),
            "not_a_job_posting": bool(ent.get("not_a_job_posting")),
            "is_multi_employer": bool(ent.get("is_multi_employer")),
        }

        osint_failed = _osint_has_failures(osint_results)

        preview = (raw_text or "").strip()
        if len(preview) > 2000:
            preview = preview[:2000] + "..."

        existing = db.query(JobCase).filter(JobCase.raw_text_hash == text_hash).first()
        if not existing:
            existing = db.query(JobCase).filter(JobCase.raw_text_hash == _legacy_case_hash(raw_text)).first()
        if existing:
            existing.raw_text_hash = text_hash
            existing.source = source
            existing.raw_text_preview = preview or None
            existing.company_name = companies[0] if companies else analysis.get("corrected_company_name")
            existing.companies = companies or None
            existing.phones = phones or None
            existing.emails = emails or None
            existing.urls = urls or None
            existing.addresses = addresses or None
            existing.salaries = salaries or None
            existing.entities = ent or None
            existing.verdict = analysis.get("verdict", "ERROR")
            existing.risk_score = int(analysis.get("risk_score") or 0)
            existing.llm_output = llm_payload
            existing.osint_summary = _cache_osint_payload(osint_results)
            existing.osint_failed = osint_failed
        else:
            db_case = JobCase(
                raw_text_hash=text_hash,
                source=source,
                raw_text_preview=preview or None,
                company_name=companies[0] if companies else analysis.get("corrected_company_name"),
                companies=companies or None,
                phones=phones or None,
                emails=emails or None,
                urls=urls or None,
                addresses=addresses or None,
                salaries=salaries or None,
                entities=ent or None,
                verdict=analysis.get("verdict", "ERROR"),
                risk_score=int(analysis.get("risk_score") or 0),
                llm_output=llm_payload,
                osint_summary=_cache_osint_payload(osint_results),
                osint_failed=osint_failed,
            )
            db.add(db_case)
        db.commit()
        case_id = existing.id if existing else db_case.id
        return {"status": "SAVED", "case_id": str(case_id)}
    except Exception as e:
        db.rollback()
        logger.warning("Error saving job case to database: %s", e)
        return {"status": "FAILED", "case_id": None}


def _job_case_to_response(cached: JobCase) -> VerifyResponse | None:
    if not cached or not cached.verdict or cached.verdict == "ERROR":
        return None
    llm_payload = cached.llm_output or {}
    # Hasil penilaian aturan berarti LLM gagal; jangan dipakai ulang agar permintaan berikutnya mencoba LLM lagi.
    if "Rule-Based Fallback" in str(llm_payload.get("model_used", "")):
        logger.info("[DB Cache Skip] rule-based fallback: %s", str(cached.id)[:8])
        return None
    ent = cached.entities or {
        "companies": cached.companies or [],
        "phones": cached.phones or [],
        "emails": cached.emails or [],
        "urls": cached.urls or [],
        "addresses": cached.addresses or [],
        "location_candidates": (cached.entities or {}).get("location_candidates", []),
        "salaries": cached.salaries or [],
    }
    analysis = {
        "case_id": str(cached.id),
        "verdict": cached.verdict,
        "risk_score": cached.risk_score,
        # Kasus lama di cache tetap dirapikan agar tidak menyebut lowongan "resmi"
        "summary": _soften_summary_claims(llm_payload.get("summary", "")),
        "risk_factors": llm_payload.get("risk_factors", []),
        "safe_factors": llm_payload.get("safe_factors", []),
        "recommendations": llm_payload.get("recommendations", []),
        "model_used": f"{llm_payload.get('model_used', 'unknown')} (DB Cache Hit)",
        "corrected_company_name": llm_payload.get("corrected_company_name"),
        "shap_explanation": llm_payload.get("shap_explanation"),
    }
    cached_osint = cached.osint_summary or {}
    if cached_osint.get("cache_schema_version") != CACHE_SCHEMA_VERSION:
        logger.info("[DB Cache Skip] stale cache schema: %s", str(cached.id)[:8])
        return None
    osint = cached_osint.get("response_osint")
    if not isinstance(osint, dict):
        logger.info("[DB Cache Skip] legacy/incomplete OSINT payload: %s", str(cached.id)[:8])
        return None
    if "social" not in osint and isinstance(osint.get("threads"), dict):
        osint = {**osint, "social": osint["threads"]}
        osint.pop("threads", None)
    return _to_response(analysis, ent, osint)


def _get_cached_case_from_db(db: Session, raw_input_str: str) -> VerifyResponse | None:
    if not VERIFY_CACHE_ENABLED:
        return None
    if not raw_input_str or not raw_input_str.strip():
        return None
    try:
        text_hash = _case_hash(raw_input_str)
        # Hasil dengan pemeriksaan gagal tidak dipakai ulang: permintaan berikutnya menghitung ulang
        cached = (
            db.query(JobCase)
            .filter(JobCase.raw_text_hash == text_hash, JobCase.osint_failed.is_(False))
            .first()
        )
        if cached:
            resp = _job_case_to_response(cached)
            if resp:
                logger.debug("[DB Cache Hit] hash: %s", text_hash[:10])
                return resp
        if re.match(r"^https?://", raw_input_str.strip(), re.I):
            return _get_cached_case_by_url(db, raw_input_str)
    except Exception as e:
        logger.warning("[DB Cache Lookup] %s", e)
    return None


_TRACKING_PARAMS = re.compile(r"^(?:utm_\w+|igsh|igshid|fbclid|gclid|mibextid|si|xmt|ref|ref_src|s|t|share_id|rdid)$", re.I)


def _strip_tracking(query: str, *, sort: bool = True) -> str:
    """Buang parameter pelacak (utm_*, igsh, fbclid, …). Parameter isi seperti
    `story_fbid` atau `v` (YouTube) dipertahankan karena membedakan postingan."""
    from urllib.parse import parse_qsl, urlencode
    kept = [(k, v) for k, v in parse_qsl(query, keep_blank_values=True) if not _TRACKING_PARAMS.match(k)]
    return urlencode(sorted(kept) if sort else kept)


def _normalize_url_variants(raw_url: str) -> list[str]:
    u = (raw_url or "").strip()
    if not u:
        return []
    variants = {u, u.rstrip("/")}
    try:
        parsed = urlparse(u)
        queries = {_strip_tracking(parsed.query), _strip_tracking(parsed.query, sort=False)}
        hosts = {parsed.netloc}
        hosts.add(parsed.netloc[4:] if parsed.netloc.startswith("www.") else f"www.{parsed.netloc}")
        for host in hosts:
            path = parsed.path.rstrip("/")
            for p in {path, path + "/"}:
                for query in queries:
                    variants.add(urlunparse((parsed.scheme, host, p, "", query, "")))
    except Exception:
        pass
    return sorted(v for v in variants if v)


def _url_conditions(variants: list[str]) -> list:
    """Cocok persis per URL. Pola awalan lama ("URL Target: {v}%") membuat
    `/p/AB` cocok dengan `/p/ABCDEF`."""
    from app.services.case_search import like_escape
    conditions = []
    for v in variants:
        conditions.append(JobCase.urls.contains([v]))
        conditions.append(JobCase.raw_text_preview == f"URL Target: {v}")
        conditions.append(JobCase.raw_text_preview.like(f"URL Target: {like_escape(v)}\n%", escape="\\"))
    return conditions


def _get_cached_case_by_url(db: Session, raw_url: str) -> VerifyResponse | None:
    if not VERIFY_CACHE_ENABLED:
        return None
    if not raw_url or not raw_url.strip():
        return None
    try:
        conditions = _url_conditions(_normalize_url_variants(raw_url))

        cached = (
            db.query(JobCase)
            .filter(
                JobCase.verdict.isnot(None),
                JobCase.verdict != "ERROR",
                JobCase.osint_failed.is_(False),
                or_(*conditions),
            )
            .order_by(JobCase.created_at.desc())
            .first()
        )
        if cached:
            resp = _job_case_to_response(cached)
            if resp:
                logger.info("[DB Cache Hit] url: %s -> case_id: %s", raw_url[:60], cached.id)
                return resp
    except Exception as e:
        logger.warning("[DB Cache URL Lookup] %s", e)
    return None


def _cache_osint_payload(osint_results: dict | None) -> dict | None:
    if not isinstance(osint_results, dict):
        return None
    summary = _build_osint_summary(osint_results) or {}
    return {
        **summary,
        "cache_schema_version": CACHE_SCHEMA_VERSION,
        "response_osint": osint_results,
    }
