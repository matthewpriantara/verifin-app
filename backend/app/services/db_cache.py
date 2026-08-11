"""DB cache — simpan dan ambil JobCase berdasarkan hash teks (exact-match memory)."""
from __future__ import annotations  # noqa: F401 — stdlib compat shim, harmless

import logging

from sqlalchemy.orm import Session

from app.api.v1.verify.schema import VerifyResponse
from app.config import LLM_MODEL
from app.database.models import JobCase
from app.services.hasher import compute_content_sha256
from app.api.v1.verify.pipeline import _build_osint_summary, _to_response

logger = logging.getLogger(__name__)
CACHE_SCHEMA_VERSION = 7


def _case_hash(raw_input: str) -> str:
    """Hash input + model aktif — ganti LLM_MODEL otomatis invalidasi cache lama."""
    return compute_content_sha256(f"{raw_input}\nmodel:{LLM_MODEL}")

def _save_case_to_db(
    db: Session,
    raw_text: str,
    analysis: dict,
    osint_results: dict | None,
    entities: dict | None = None,
    source: str = "text",
) -> str:
    """Simpan case + entities lengkap. Return persistence_status: SAVED | FAILED."""
    from sqlalchemy.exc import IntegrityError

    if db is None:
        return "SKIPPED"

    try:
        text_hash = _case_hash(raw_text)
        ent = entities or analysis.get("entities_analyzed") or {}
        companies = list(ent.get("companies") or [])
        phones = list(ent.get("phones") or [])
        emails = list(ent.get("emails") or [])
        urls = list(ent.get("urls") or [])
        addresses = list(ent.get("addresses") or [])
        salaries = list(ent.get("salaries") or [])

        llm_payload = {
            "summary": analysis.get("summary", ""),
            "risk_factors": analysis.get("risk_factors") or [],
            "safe_factors": analysis.get("safe_factors") or [],
            "recommendations": analysis.get("recommendations") or [],
            "model_used": analysis.get("model_used"),
            "corrected_company_name": analysis.get("corrected_company_name"),
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
        return "SAVED"
    except Exception as e:
        db.rollback()
        logger.warning("Error saving job case to database: %s", e)
        return "FAILED"


def _get_cached_case_from_db(db: Session, raw_input_str: str) -> VerifyResponse | None:
    """Cek apakah lowongan/URL/gambar ini sudah pernah dianalisa (exact DB cache hit)."""
    if not raw_input_str or not raw_input_str.strip():
        return None
    try:
        text_hash = _case_hash(raw_input_str)
        cached = db.query(JobCase).filter(JobCase.raw_text_hash == text_hash).first()
        if cached and cached.verdict and cached.verdict != "ERROR":
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
                "verdict": cached.verdict,
                "risk_score": cached.risk_score,
                "summary": llm_payload.get("summary", ""),
                "risk_factors": llm_payload.get("risk_factors", []),
                "safe_factors": llm_payload.get("safe_factors", []),
                "recommendations": llm_payload.get("recommendations", []),
                "model_used": f"{llm_payload.get('model_used', 'unknown')} (DB Cache Hit)",
                "corrected_company_name": llm_payload.get("corrected_company_name"),
            }
            cached_osint = cached.osint_summary or {}
            if cached_osint.get("cache_schema_version") != CACHE_SCHEMA_VERSION:
                logger.info("[DB Cache Skip] stale cache schema: %s", text_hash[:10])
                return None
            osint = cached_osint.get("response_osint")
            if not isinstance(osint, dict):
                logger.info("[DB Cache Skip] legacy/incomplete OSINT payload: %s", text_hash[:10])
                return None
            # Cache sebelum rename menyimpan agregat seluruh platform sebagai
            # `threads`; normalisasi saat baca agar kontrak response sekarang
            # tetap `social` tanpa mengulang probe eksternal.
            if "social" not in osint and isinstance(osint.get("threads"), dict):
                osint = {**osint, "social": osint["threads"]}
                osint.pop("threads", None)
            logger.debug("[DB Cache Hit] hash: %s", text_hash[:10])
            return _to_response(analysis, ent, osint)
    except Exception as e:
        logger.warning("[DB Cache Lookup] %s", e)
    return None


def _cache_osint_payload(osint_results: dict | None) -> dict | None:
    """Simpan evidence response lengkap agar cache tidak menghasilkan SHAP palsu."""
    if not isinstance(osint_results, dict):
        return None
    summary = _build_osint_summary(osint_results) or {}
    return {
        **summary,
        "cache_schema_version": CACHE_SCHEMA_VERSION,
        "response_osint": osint_results,
    }
