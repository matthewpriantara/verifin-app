"""DB cache — simpan dan ambil JobCase berdasarkan hash teks (exact-match memory)."""
from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.api.v1.verify.schema import VerifyResponse
from app.database.models import JobCase
from app.services.hasher import compute_content_sha256

logger = logging.getLogger(__name__)

def _save_case_to_db(
    db: Session,
    raw_text: str,
    analysis: dict,
    osint_results: dict | None,
    entities: dict | None = None,
    source: str = "text",
) -> None:
    """Simpan case + entities lengkap (fondasi exact-match memory)."""
    from sqlalchemy.exc import IntegrityError

    try:
        text_hash = compute_content_sha256(raw_text)
        ent = entities or analysis.get("entities_analyzed") or {}
        companies = list(ent.get("companies") or [])
        phones = list(ent.get("contacts") or [])
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
            existing.osint_summary = _build_osint_summary(osint_results)
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
                osint_summary=_build_osint_summary(osint_results),
                osint_failed=osint_failed,
            )
            db.add(db_case)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("Error saving job case to database: %s", e)


def _get_cached_case_from_db(db: Session, raw_input_str: str) -> VerifyResponse | None:
    """Cek apakah lowongan/URL/gambar ini sudah pernah dianalisa (exact DB cache hit)."""
    if not raw_input_str or not raw_input_str.strip():
        return None
    try:
        text_hash = compute_content_sha256(raw_input_str)
        cached = db.query(JobCase).filter(JobCase.raw_text_hash == text_hash).first()
        if cached and cached.verdict and cached.verdict != "ERROR":
            llm_payload = cached.llm_output or {}
            ent = cached.entities or {
                "companies": cached.companies or [],
                "contacts": cached.phones or [],
                "emails": cached.emails or [],
                "urls": cached.urls or [],
                "addresses": cached.addresses or [],
                "salaries": cached.salaries or [],
            }
            analysis = {
                "verdict": cached.verdict,
                "risk_score": cached.risk_score,
                "summary": llm_payload.get("summary", ""),
                "risk_factors": llm_payload.get("risk_factors", []),
                "safe_factors": llm_payload.get("safe_factors", []),
                "recommendations": llm_payload.get("recommendations", []),
                "model_used": f"{llm_payload.get('model_used', 'claude-sonnet-4.5')} (DB Cache Hit)",
                "corrected_company_name": llm_payload.get("corrected_company_name"),
            }
            osint = cached.osint_summary or {}
            logger.debug("[DB Cache Hit] hash: %s", text_hash[:10])
            return _to_response(analysis, ent, osint)
    except Exception as e:
        logger.warning("[DB Cache Lookup] %s", e)
    return None


