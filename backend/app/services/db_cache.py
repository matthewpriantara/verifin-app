from __future__ import annotations

import logging
import re
from urllib.parse import urlparse, urlunparse

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.v1.verify.schema import VerifyResponse
from app.config import LLM_MODEL
from app.database.models import JobCase
from app.services.hasher import compute_content_sha256
from app.api.v1.verify.pipeline import _build_osint_summary, _to_response

logger = logging.getLogger(__name__)
CACHE_SCHEMA_VERSION = 7


def _case_hash(raw_input: str) -> str:
    return compute_content_sha256(f"{raw_input}\nmodel:{LLM_MODEL}")

def _save_case_to_db(
    db: Session,
    raw_text: str,
    analysis: dict,
    osint_results: dict | None,
    entities: dict | None = None,
    source: str = "text",
) -> dict:
    from sqlalchemy.exc import IntegrityError

    if db is None:
        return {"status": "SKIPPED", "case_id": None}

    try:
        text_hash = _case_hash(raw_text)
        ent = entities or analysis.get("entities_analyzed") or {}
        companies = list(ent.get("companies") or [])
        phones = list(ent.get("phones") or [])
        emails = list(ent.get("emails") or [])
        urls = list(ent.get("urls") or [])
        addresses = list(ent.get("addresses") or [])
        salaries = list(ent.get("salaries") or [])

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
        }

        osint_failed = False
        if osint_results:
            osint_failed = any(
                isinstance(v, dict) and "error" in v for v in osint_results.values()
            )

        preview = (raw_text or "").strip()
        if len(preview) > 2000:
            preview = preview[:2000] + "..."

        existing = db.query(JobCase).filter(JobCase.raw_text_hash == text_hash).first()
        if existing:
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
        "summary": llm_payload.get("summary", ""),
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
    if not raw_input_str or not raw_input_str.strip():
        return None
    try:
        text_hash = _case_hash(raw_input_str)
        cached = db.query(JobCase).filter(JobCase.raw_text_hash == text_hash).first()
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


def _normalize_url_variants(raw_url: str) -> list[str]:
    u = (raw_url or "").strip()
    if not u:
        return []
    variants = {u, u.rstrip("/"), u.rstrip("/") + "/"}
    try:
        parsed = urlparse(u)
        clean = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        variants.add(clean)
        variants.add(clean.rstrip("/"))
        variants.add(clean.rstrip("/") + "/")
        if parsed.netloc.startswith("www."):
            no_www = urlunparse((parsed.scheme, parsed.netloc[4:], parsed.path, "", "", ""))
            variants.add(no_www)
            variants.add(no_www.rstrip("/"))
            variants.add(no_www.rstrip("/") + "/")
        else:
            with_www = urlunparse((parsed.scheme, f"www.{parsed.netloc}", parsed.path, "", "", ""))
            variants.add(with_www)
            variants.add(with_www.rstrip("/"))
            variants.add(with_www.rstrip("/") + "/")
    except Exception:
        pass
    return sorted(list(variants))


def _get_cached_case_by_url(db: Session, raw_url: str) -> VerifyResponse | None:
    if not raw_url or not raw_url.strip():
        return None
    try:
        variants = _normalize_url_variants(raw_url)
        conditions = []
        for v in variants:
            conditions.append(JobCase.urls.contains([v]))
            conditions.append(JobCase.raw_text_preview.like(f"URL Target: {v}%"))

        cached = (
            db.query(JobCase)
            .filter(
                JobCase.verdict.isnot(None),
                JobCase.verdict != "ERROR",
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
