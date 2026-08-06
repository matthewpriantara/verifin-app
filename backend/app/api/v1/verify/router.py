"""
Router verifikasi Verifin — Job Trust Infrastructure.

Tiga kanal input: teks, gambar (OCR), URL postingan.
Pipeline 5 layer: NLP → NER → OSINT → LLM → Fraud Network → SHAP response.

Modular:
  pipeline.py   — entity extraction, OSINT runner, fraud network, response builder
  db_cache.py   — simpan & ambil JobCase dari PostgreSQL
  web_fetcher.py — Scrapling + Instagram/Threads scraper
"""

import logging
import os
import tempfile
from typing import List
from uuid import UUID
from sqlalchemy.orm import Session

from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile, Depends
from app.database.postgres_client import get_db
from app.database.models import JobCase, AhuWhitelist

from app.api.v1.verify.schema import (
    ExtractedEntities,
    LlmStatusResponse,
    TextVerifyRequest,
    UrlVerifyRequest,
    VerifyResponse,
)
from app.services.llm.verifin_reasoning import analyze_with_verifin, check_ai_status
from app.services.nlp.classifier import classify_text
from app.services.ocr import extract_text_from_image
from app.services.osint.whois_handler import (
    check_domain_age,
    check_email_security,
    scan_email_osint,
    scan_username_osint,
)

# Import helpers dari modul terpisah
from app.api.v1.verify.pipeline import (
    _check_fraud_network,
    _extract_entities_hybrid,
    _run_osint_on_entities,
    _to_response,
    _build_osint_summary,
)
from app.services.db_cache import _save_case_to_db, _get_cached_case_from_db
from app.services.web_fetcher import _fetch_url_content_and_image

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post(
    "/verify/text",
    response_model=VerifyResponse,
    summary="Verifikasi Lowongan Kerja dari Teks",
)
async def verify_from_text(
    request: TextVerifyRequest = Body(...), 
    db: Session = Depends(get_db)
):
    cached_resp = _get_cached_case_from_db(db, request.text)
    if cached_resp:
        return cached_resp

    try:
        # Layer 1: NLP — TF-IDF behavioral features (paper22 Springer)
        nlp_result = classify_text(request.text)

        entities = await _extract_entities_hybrid(request.text)
        osint_results = await _run_osint_on_entities(entities)

        # Layer 5: Fraud Network — case memory (GAR-HGNN inspired)
        network_context = _check_fraud_network(db, entities)

        raw_text = request.text if request.include_raw_text else None
        analysis = await analyze_with_verifin(entities, osint_results, raw_text=raw_text)

        # Attach NLP + network context untuk SHAP explainer
        analysis["nlp_result"] = nlp_result
        analysis["network_context"] = network_context

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

        # Cache-check dari hash teks OCR — gambar identik = hasil identik
        cached_resp = _get_cached_case_from_db(db, raw_text)
        if cached_resp:
            return cached_resp

        entities = await _extract_entities_hybrid(raw_text)

        # Layer 1: NLP — jalan sebelum OSINT, konsisten dengan text endpoint
        nlp_result = classify_text(raw_text)

        osint_results = await _run_osint_on_entities(entities)

        # Layer 5: Fraud Network Check
        network_context = _check_fraud_network(db, entities)

        analysis = await analyze_with_verifin(
            entities, osint_results, raw_text=raw_text
        )
        analysis["nlp_result"] = nlp_result
        analysis["network_context"] = network_context

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

@router.post(
    "/verify/url",
    response_model=VerifyResponse,
    summary="Verifikasi Lowongan Kerja dari Link / URL Postingan",
    description=(
        "Menerima URL/link postingan lowongan kerja (misal Instagram, JobStreet, LinkedIn, Facebook, atau website). "
        "Sistem akan otomatis mengambil gambar poster & caption, memprioritaskan OCR poster gambar untuk mengekstrak entitas no HP, email, alamat, dll."
    ),
)
async def verify_from_url(
    request: UrlVerifyRequest = Body(...),
    db: Session = Depends(get_db)
):
    cached_resp = _get_cached_case_from_db(db, request.url)
    if cached_resp:
        return cached_resp

    tmp_paths = []
    try:
        caption_text, tmp_paths = await _fetch_url_content_and_image(request.url)
        
        ocr_texts = []
        for p in tmp_paths:
            if p and os.path.exists(p):
                try:
                    t = extract_text_from_image(p)
                    if t and t.strip():
                        ocr_texts.append(t.strip())
                except Exception as exc:
                    logger.warning("URL OCR Error: %s", exc)

        combined_ocr_text = "\n".join(ocr_texts).strip()

        # Prioritaskan teks OCR poster di posisi paling atas
        text_blocks = [f"URL Target: {request.url}"]
        if combined_ocr_text:
            text_blocks.append(f"[TEKS UTAMA POSTER/GAMBAR LOWONGAN (OCR)]:\n{combined_ocr_text}")
        if caption_text and caption_text.strip():
            text_blocks.append(f"[TEKS CAPTION / DESKRIPSI POSTINGAN]:\n{caption_text.strip()}")
        if request.additional_text and request.additional_text.strip():
            text_blocks.append(f"[UTAS BALASAN / TEKS TAMBAHAN]:\n{request.additional_text.strip()}")

        full_raw_text = "\n\n".join(text_blocks).strip()

        cached_resp_full = _get_cached_case_from_db(db, full_raw_text)
        if cached_resp_full:
            return cached_resp_full
        
        if not full_raw_text or len(full_raw_text) < 15:
            raise HTTPException(
                status_code=422,
                detail="Sistem tidak dapat mengambil konten atau teks dari URL tersebut. Pastikan link dapat diakses publik.",
            )

        entities = await _extract_entities_hybrid(full_raw_text)
        osint_results = await _run_osint_on_entities(entities)

        # Layer 5: Fraud Network Check (case memory + community reports)
        network_context = _check_fraud_network(db, entities)

        analysis = await analyze_with_verifin(
            entities, osint_results, raw_text=full_raw_text
        )
        analysis["network_context"] = network_context
        _save_case_to_db(
            db, full_raw_text, analysis, osint_results, entities=entities, source="url"
        )
        return _to_response(analysis, entities, osint_results)

    except HTTPException:
        raise
    except Exception as e:
        safe_msg = str(e).encode("ascii", errors="ignore").decode("ascii") or "Terjadi kesalahan internal."
        raise HTTPException(
            status_code=500, detail=f"Gagal memproses verifikasi URL: {safe_msg}"
        ) from e
    finally:
        for p in tmp_paths:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
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
    categories: list[str] | None = Query(None),
):
    try:
        results = await scan_email_osint(email, categories)
        return {"email": email, "found_count": len(results), "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/osint/scan-username")
async def verify_username_osint(
    username: str = Query(..., description="Username yang dilacak footprint-nya"),
    categories: list[str] | None = Query(None),
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
    phone: str | None = Query(None, description="Nomor E.164 mis. +62812..."),
    email: str | None = Query(None),
    company: str | None = Query(None),
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

