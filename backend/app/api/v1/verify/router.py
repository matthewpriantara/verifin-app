"""
Router verifikasi Verifin.
Pipeline:
  teks   → NER/regex → OSINT → LLM reasoner (OpenAgentic grok-4.5)
  gambar → Vision OCR (Grok) → OSINT → LLM reasoner
"""

import os
import tempfile
from typing import List, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile, Depends
from app.database.postgres_client import get_db
from app.database.models import JobCase, AhuWhitelist

from app.api.v1.verify.schema import (
    ExtractedEntities,
    LlmStatusResponse,
    TextVerifyRequest,
    VerifyResponse,
)
from app.services.llm.verifin_reasoning import analyze_with_verifin, check_ai_status
from app.services.ner import extract_entities_from_text
from app.services.osint.address_validator import validate_address_and_business
from app.services.osint.company_validator import validate_companies
from app.services.osint.phone_validator import check_phones_kredibel
from app.services.osint.threads_osint import run_threads_osint
from app.services.osint.web_evidence import run_web_evidence
from app.services.osint.whois_handler import (
    check_domain_age,
    check_email_security,
    scan_email_osint,
    scan_username_osint,
)
from app.services.ocr import extract_text_from_image
from app.services.xai.shap_explainer import explain_verification_shap

router = APIRouter()


async def _run_osint_on_entities(entities: dict) -> dict:
    """OSINT live: WHOIS/DNS + OSM + Kredibel HP + Scrapling web + Threads."""
    osint_results: dict = {
        "domain": {
            "age_years": None,
            "created_at": "Tidak diketahui",
            "is_new": False,
        },
        "email_security": {"spf_active": False, "dmarc_active": False},
        "address_validations": [],
        "phones": [],
        "companies": [],
        "web": {
            "enabled": False,
            "websites": [],
            "searches": [],
            "risk_flags": [],
            "safe_flags": [],
        },
        "threads": {
            "enabled": False,
            "found": False,
            "posts": [],
            "profiles": [],
            "risk_flags": [],
        },
        "evidence_policy": {
            "mode": "factual_sources_only",
            "note": (
                "Semua temuan OSINT berasal dari fetch/scrape/API nyata "
                "(WHOIS, DNS, OSM, Kredibel, Scrapling, Threads). "
                "LLM reasoner dilarang mengarang fakta di luar evidence."
            ),
            "social": "threads_only",
        },
    }

    emails = entities.get("emails", [])
    if emails:
        first_email = emails[0]
        domain = first_email.split("@")[-1] if "@" in first_email else None
        if domain:
            try:
                age_info = check_domain_age(domain)
                if "age_years" not in age_info and age_info.get("age_days", -1) > 0:
                    age_info["age_years"] = round(age_info["age_days"] / 365, 2)
                security_info = check_email_security(domain)
                osint_results["domain"] = age_info
                osint_results["email_security"] = security_info
            except Exception as exc:
                osint_results["domain"] = {
                    "error": str(exc),
                    "is_new": True,
                    "age_years": None,
                    "created_at": "Unknown",
                }

    addresses = entities.get("addresses", [])
    companies = entities.get("companies", [])
    company_name = companies[0] if companies else None

    for address in addresses[:2]:
        try:
            addr_result = await validate_address_and_business(address, company_name)
            osint_results["address_validations"].append(addr_result)
        except Exception:
            osint_results["address_validations"].append(
                {
                    "address_input": address,
                    "address_found": False,
                    "error": "Gagal memvalidasi alamat.",
                }
            )

    # HP via Kredibel (Scrapling + cookies login)
    try:
        osint_results["phones"] = await check_phones_kredibel(
            entities.get("contacts") or [], limit=2
        )
    except Exception as exc:
        osint_results["phones"] = [
            {"source": "kredibel", "found": False, "error": str(exc), "risk_flags": []}
        ]

    # Web evidence via Scrapling (website + search) — data fetch nyata
    try:
        osint_results["web"] = await run_web_evidence(entities)
    except Exception as exc:
        osint_results["web"] = {
            "enabled": True,
            "websites": [],
            "searches": [],
            "risk_flags": [],
            "safe_flags": [],
            "error": str(exc),
        }

    # Company / PT — jejak publik saja (bukan klaim AHU palsu)
    try:
        osint_results["companies"] = await validate_companies(entities, limit=1)
    except Exception as exc:
        osint_results["companies"] = [
            {
                "checked": False,
                "error": str(exc),
                "registry": {"pt_registry_verified": False},
                "risk_flags": [],
                "safe_flags": [],
                "evidence": [],
            }
        ]

    # Medsos: Threads saja (cookie session)
    try:
        osint_results["threads"] = await run_threads_osint(entities)
    except Exception as exc:
        osint_results["threads"] = {
            "enabled": True,
            "found": False,
            "posts": [],
            "profiles": [],
            "risk_flags": [],
            "error": str(exc),
        }

    return osint_results


def _merge_entities(primary: dict, secondary: dict) -> dict:
    keys = ["companies", "contacts", "emails", "urls", "addresses", "salaries"]
    out = {}
    for key in keys:
        seen = set()
        merged = []
        for item in list(primary.get(key) or []) + list(secondary.get(key) or []):
            val = str(item).strip()
            if not val:
                continue
            low = val.lower()
            if low in seen:
                continue
            seen.add(low)
            merged.append(val)
        out[key] = merged
    return out


def _to_response(
    analysis: dict,
    entities: dict,
    osint_results: dict | None = None,
) -> VerifyResponse:
    corrected = analysis.get("corrected_company_name")
    if corrected and corrected not in (None, "null", ""):
        entities = {**entities, "companies": [str(corrected)]}

    # sanitize entities keys for schema
    safe_entities = {
        "companies": entities.get("companies") or [],
        "contacts": entities.get("contacts") or [],
        "emails": entities.get("emails") or [],
        "urls": entities.get("urls") or [],
        "addresses": entities.get("addresses") or [],
        "salaries": entities.get("salaries") or [],
    }

    risk_score = int(analysis.get("risk_score") or 0)
    verdict = analysis.get("verdict", "ERROR")
    risk_factors = analysis.get("risk_factors") or []
    safe_factors = analysis.get("safe_factors") or []

    shap_explanation = None
    try:
        shap_explanation = explain_verification_shap(
            risk_score=risk_score,
            verdict=verdict,
            osint_results=osint_results or {},
            risk_factors=risk_factors,
            safe_factors=safe_factors,
        )
    except Exception:
        shap_explanation = None

    return VerifyResponse(
        verdict=verdict,
        risk_score=risk_score,
        summary=analysis.get("summary", ""),
        risk_factors=risk_factors,
        safe_factors=safe_factors,
        recommendations=analysis.get("recommendations") or [],
        entities=ExtractedEntities(**safe_entities),
        model_used=analysis.get("model_used"),
        osint=osint_results,
        shap_explanation=shap_explanation,
    )


def _build_osint_summary(osint_results: dict | None) -> dict | None:
    """Snapshot ringan untuk audit/case-memory (hindari raw HTML besar)."""
    if not osint_results:
        return None
    phones = osint_results.get("phones") or []
    addrs = osint_results.get("address_validations") or []
    web = osint_results.get("web") or {}
    threads = osint_results.get("threads") or {}
    return {
        "phones": [
            {
                "phone": p.get("phone") or p.get("phone_local"),
                "rating": p.get("rating"),
                "reported_fraud": p.get("reported_fraud"),
                "review_count": p.get("review_count"),
            }
            for p in phones[:5]
            if isinstance(p, dict)
        ],
        "addresses": [
            {
                "input": a.get("address_input") or a.get("query"),
                "found": a.get("address_found") or a.get("found"),
                "display": ((a.get("address_details") or {}).get("display_name") or "")[:120],
            }
            for a in addrs[:5]
            if isinstance(a, dict)
        ],
        "web_search_count": len((web.get("searches") or [])),
        "web_safe_flags": (web.get("safe_flags") or web.get("safe_signals") or [])[:8],
        "web_risk_flags": (web.get("risk_flags") or [])[:8],
        "threads_query": threads.get("query"),
        "threads_found": bool(threads.get("found")),
        "domain": {
            "age_years": (osint_results.get("domain") or {}).get("age_years"),
            "is_new": (osint_results.get("domain") or {}).get("is_new"),
        },
    }


def _save_case_to_db(
    db: Session,
    raw_text: str,
    analysis: dict,
    osint_results: dict | None,
    entities: dict | None = None,
    source: str = "text",
) -> None:
    """Simpan case + entities lengkap (fondasi exact-match memory)."""
    import hashlib
    from sqlalchemy.exc import IntegrityError

    try:
        text_hash = hashlib.sha256(raw_text.strip().encode("utf-8")).hexdigest()
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
    except IntegrityError:
        db.rollback()
    except Exception as e:
        db.rollback()
        print(f"Error saving job case to database: {e}")


@router.post(
    "/verify/text",
    response_model=VerifyResponse,
    summary="Verifikasi Lowongan Kerja dari Teks",
)
async def verify_from_text(
    request: TextVerifyRequest = Body(...), 
    db: Session = Depends(get_db)
):
    try:
        entities = extract_entities_from_text(request.text)
        osint_results = await _run_osint_on_entities(entities)
        raw_text = request.text if request.include_raw_text else None
        analysis = await analyze_with_verifin(entities, osint_results, raw_text=raw_text)
        _save_case_to_db(
            db, request.text, analysis, osint_results, entities=entities, source="text"
        )
        return _to_response(analysis, entities, osint_results)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Gagal memproses verifikasi teks: {e}"
        ) from e


@router.post(
    "/verify/image",
    response_model=VerifyResponse,
    summary="Verifikasi Lowongan Kerja dari Gambar (PaddleOCR + OpenCV)",
    description=(
        "Gambar dibaca secara lokal menggunakan PaddleOCR + OpenCV CLAHE. "
        "Lanjut ekstraksi NER, OSINT evidence, dan LLM reasoning."
    ),
)
async def verify_from_image(
    file: UploadFile = File(
        ..., description="File gambar poster/screenshot lowongan (JPG/PNG/WEBP)"
    ),
    db: Session = Depends(get_db)
):
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Tipe file tidak didukung: {file.content_type}. Gunakan JPG, PNG, atau WEBP.",
        )

    contents = await file.read()
    if len(contents) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Ukuran file terlalu besar. Maksimal 20MB.")

    ext = os.path.splitext(file.filename or "")[-1] or ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        raw_text = extract_text_from_image(tmp_path)
        if not raw_text or not raw_text.strip():
            raise HTTPException(
                status_code=422,
                detail="Tidak ada teks yang berhasil dibaca dari gambar. Coba unggah gambar yang lebih jelas.",
            )

        entities = extract_entities_from_text(raw_text)
        osint_results = await _run_osint_on_entities(entities)
        analysis = await analyze_with_verifin(
            entities, osint_results, raw_text=raw_text
        )
        _save_case_to_db(
            db, raw_text, analysis, osint_results, entities=entities, source="image"
        )
        return _to_response(analysis, entities, osint_results)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Gagal memproses verifikasi gambar: {e}"
        ) from e
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


@router.get(
    "/verify/status",
    response_model=LlmStatusResponse,
    summary="Cek status LLM (OpenAgentic)",
)
async def check_ai_status_endpoint():
    return await check_ai_status()


@router.get("/check-domain")
def verify_domain(
    domain: str = Query(..., description="Domain email (misal: pertamina.com)"),
):
    age_info = check_domain_age(domain)
    security_info = check_email_security(domain)

    risk_score = 0
    reasons = []

    if age_info.get("is_new"):
        risk_score += 50
        reasons.append(
            f"Domain email sangat baru (dibuat pada {age_info.get('created_at')})"
        )

    if not security_info.get("spf_active"):
        risk_score += 25
        reasons.append("Domain tidak mengaktifkan proteksi SPF")

    if not security_info.get("dmarc_active"):
        risk_score += 25
        reasons.append("Domain tidak mengaktifkan kebijakan DMARC")

    verdict = "AMAN"
    if risk_score >= 75:
        verdict = "BAHAYA"
    elif risk_score >= 40:
        verdict = "WASPADA"

    return {
        "domain": domain,
        "risk_score": risk_score,
        "verdict": verdict,
        "reasons": reasons,
        "details": {"age": age_info, "security": security_info},
    }


@router.get("/osint/scan-email")
async def verify_email_osint(
    email: str = Query(..., description="Email yang dilacak footprint-nya"),
    categories: Optional[List[str]] = Query(None),
):
    try:
        results = await scan_email_osint(email, categories)
        return {"email": email, "found_count": len(results), "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/osint/scan-username")
async def verify_username_osint(
    username: str = Query(..., description="Username yang dilacak footprint-nya"),
    categories: Optional[List[str]] = Query(None),
):
    try:
        results = await scan_username_osint(username, categories)
        return {"username": username, "found_count": len(results), "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ─────────────────────────────────────────────────────────────────────────────
# DATABASE ACCESS ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/cases",
    summary="Ambil semua daftar kasus",
    description="Mengembalikan seluruh riwayat kasus verifikasi lowongan kerja dari database PostgreSQL."
)
def list_cases(limit: int = 100, skip: int = 0, db: Session = Depends(get_db)):
    try:
        cases = (
            db.query(JobCase)
            .order_by(JobCase.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [
            {
                "id": str(c.id),
                "source": c.source,
                "company_name": c.company_name,
                "phones": c.phones,
                "emails": c.emails,
                "verdict": c.verdict,
                "risk_score": c.risk_score,
                "osint_failed": c.osint_failed,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in cases
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengambil kasus: {str(e)}")


@router.get(
    "/cases/lookup/by-entity",
    summary="Cari case history by HP / email / company (exact match)",
    description="Fondasi case-memory: lookup exact phone/email/company dari riwayat job_cases.",
)
def lookup_cases_by_entity(
    phone: Optional[str] = Query(None, description="Nomor E.164 mis. +62812..."),
    email: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if not phone and not email and not company:
        raise HTTPException(
            status_code=400, detail="Sertakan minimal satu: phone, email, atau company"
        )
    try:
        cases = (
            db.query(JobCase)
            .order_by(JobCase.created_at.desc())
            .limit(500)
            .all()
        )
        hits = []
        phone_n = (phone or "").strip()
        email_n = (email or "").strip().lower()
        company_n = (company or "").strip().lower()
        for c in cases:
            phones = [str(p).strip() for p in (c.phones or [])]
            emails = [str(e).strip().lower() for e in (c.emails or [])]
            companies = [str(x).strip().lower() for x in (c.companies or [])]
            if c.company_name:
                companies.append(c.company_name.strip().lower())
            match = False
            if phone_n and phone_n in phones:
                match = True
            if email_n and email_n in emails:
                match = True
            if company_n and any(company_n in x or x in company_n for x in companies if x):
                match = True
            if match:
                hits.append(
                    {
                        "id": str(c.id),
                        "company_name": c.company_name,
                        "phones": c.phones,
                        "emails": c.emails,
                        "verdict": c.verdict,
                        "risk_score": c.risk_score,
                        "created_at": c.created_at.isoformat() if c.created_at else None,
                    }
                )
            if len(hits) >= limit:
                break
        return {"count": len(hits), "cases": hits}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal lookup case: {e}")


@router.get(
    "/cases/{case_id}",
    summary="Ambil detail kasus berdasarkan ID",
    description="Mengembalikan detail lengkap analisis dari database PostgreSQL untuk case_id tertentu."
)
def get_case_by_id(case_id: UUID, db: Session = Depends(get_db)):
    db_case = db.query(JobCase).filter(JobCase.id == case_id).first()
    if not db_case:
        raise HTTPException(status_code=404, detail="Kasus tidak ditemukan")
    return {
        "id": str(db_case.id),
        "raw_text_hash": db_case.raw_text_hash,
        "source": db_case.source,
        "raw_text_preview": db_case.raw_text_preview,
        "company_name": db_case.company_name,
        "companies": db_case.companies,
        "phones": db_case.phones,
        "emails": db_case.emails,
        "urls": db_case.urls,
        "addresses": db_case.addresses,
        "salaries": db_case.salaries,
        "entities": db_case.entities,
        "verdict": db_case.verdict,
        "risk_score": db_case.risk_score,
        "llm_output": db_case.llm_output,
        "osint_summary": db_case.osint_summary,
        "osint_failed": db_case.osint_failed,
        "created_at": db_case.created_at.isoformat() if db_case.created_at else None,
    }


@router.get(
    "/whitelist",
    summary="Ambil daftar perusahaan yang ter-whitelist",
    description="Mengembalikan seluruh daftar PT/CV resmi Kemenkumham dari database PostgreSQL."
)
def list_whitelist(limit: int = 100, skip: int = 0, db: Session = Depends(get_db)):
    try:
        companies = db.query(AhuWhitelist).offset(skip).limit(limit).all()
        return [
            {
                "id": c.id,
                "company_name": c.company_name,
                "legal_type": c.legal_type,
                "synced_at": c.synced_at.isoformat() if c.synced_at else None
            }
            for c in companies
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal mengambil whitelist: {str(e)}")

