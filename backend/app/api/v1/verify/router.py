"""
Router utama untuk endpoint verifikasi lowongan kerja Verifin.
Pipeline: Input (Gambar/Teks) → OCR → NER → OSINT → LLM (Hermes) → Verdict JSON
"""

import os
import tempfile
from fastapi import APIRouter, Query, HTTPException, UploadFile, File, Body
from typing import List, Optional

from app.services.osint.whois_handler import check_domain_age, check_email_security, scan_email_osint, scan_username_osint
from app.services.ner import extract_entities_from_text
from app.services.ocr import extract_text_from_image
from app.services.llm.hermes_reasoner import analyze_with_hermes, check_ollama_status
from app.api.v1.verify.schema import TextVerifyRequest, VerifyResponse, ExtractedEntities, OllamaStatusResponse

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────────────

async def _run_osint_on_entities(entities: dict) -> dict:
    """
    Menjalankan pengecekan OSINT (domain, email security) pada entitas yang ditemukan.
    Saat ini hanya mencek domain pertama dari daftar email jika ada.
    Modul OSINT lain (GetContact, AHU, dll.) akan ditambahkan di sini nanti.
    """
    osint_results = {
        "domain": {
            "age_years": None,
            "created_at": "Tidak diketahui",
            "is_new": False
        },
        "email_security": {
            "spf_active": False,
            "dmarc_active": False
        }
    }

    emails = entities.get("emails", [])
    if emails:
        first_email = emails[0]
        domain = first_email.split("@")[-1] if "@" in first_email else None
        if domain:
            try:
                age_info = check_domain_age(domain)
                security_info = check_email_security(domain)
                osint_results["domain"] = age_info
                osint_results["email_security"] = security_info
            except Exception:
                pass  # Jika OSINT gagal, lanjutkan dengan mock data

    return osint_results


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT 1: Verifikasi dari Teks
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/verify/text",
    response_model=VerifyResponse,
    summary="Verifikasi Lowongan Kerja dari Teks",
    description="Menerima teks lowongan kerja, mengekstrak entitas, menjalankan OSINT, dan menganalisis risiko penipuan menggunakan AI (Hermes)."
)
async def verify_from_text(request: TextVerifyRequest = Body(...)):
    try:
        # Step 1: Ekstraksi entitas dari teks
        entities = extract_entities_from_text(request.text)

        # Step 2: Jalankan OSINT pada entitas yang ditemukan
        osint_results = await _run_osint_on_entities(entities)

        # Step 3: Kirim ke Hermes LLM untuk analisis akhir
        raw_text = request.text if request.include_raw_text else None
        analysis = await analyze_with_hermes(entities, osint_results, raw_text=raw_text)

        return VerifyResponse(
            verdict=analysis.get("verdict", "ERROR"),
            risk_score=analysis.get("risk_score", 0),
            corrected_company_name=analysis.get("corrected_company_name"),
            summary=analysis.get("summary", ""),
            risk_factors=analysis.get("risk_factors", []),
            safe_factors=analysis.get("safe_factors", []),
            recommendations=analysis.get("recommendations", []),
            entities=ExtractedEntities(**entities),
            model_used=analysis.get("model_used")
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memproses verifikasi teks: {str(e)}")


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT 2: Verifikasi dari Gambar (Poster Loker)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/verify/image",
    response_model=VerifyResponse,
    summary="Verifikasi Lowongan Kerja dari Gambar/Poster",
    description="Menerima file gambar poster lowongan kerja, menjalankan OCR, mengekstrak entitas, menjalankan OSINT, dan menganalisis risiko penipuan menggunakan AI (Hermes)."
)
async def verify_from_image(file: UploadFile = File(..., description="File gambar poster lowongan kerja (JPG/PNG, maks 4000x4000px)")):
    # Validasi tipe file
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Tipe file tidak didukung: {file.content_type}. Gunakan JPG, PNG, atau WEBP."
        )

    # Validasi ukuran file (maks 20MB)
    MAX_SIZE_BYTES = 20 * 1024 * 1024
    contents = await file.read()
    if len(contents) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Ukuran file terlalu besar. Maksimal 20MB."
        )

    # Simpan ke file sementara untuk diproses OpenCV
    suffix = os.path.splitext(file.filename)[-1] if file.filename else ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        # Step 1: OCR — Baca teks dari gambar
        raw_text = extract_text_from_image(tmp_path)

        if not raw_text.strip():
            raise HTTPException(
                status_code=422,
                detail="Tidak ada teks yang berhasil dibaca dari gambar. Pastikan gambar memiliki kualitas yang cukup."
            )

        # Step 2: NER — Ekstrak entitas dari teks
        entities = extract_entities_from_text(raw_text)

        # Step 3: OSINT — Cek domain dan keamanan email
        osint_results = await _run_osint_on_entities(entities)

        # Step 4: LLM — Analisis risiko penipuan
        analysis = await analyze_with_hermes(entities, osint_results, raw_text=raw_text)

        return VerifyResponse(
            verdict=analysis.get("verdict", "ERROR"),
            risk_score=analysis.get("risk_score", 0),
            corrected_company_name=analysis.get("corrected_company_name"),
            summary=analysis.get("summary", ""),
            risk_factors=analysis.get("risk_factors", []),
            safe_factors=analysis.get("safe_factors", []),
            recommendations=analysis.get("recommendations", []),
            entities=ExtractedEntities(**entities),
            model_used=analysis.get("model_used")
        )

    except HTTPException:
        raise
    except ValueError as e:
        # Resolusi gambar terlalu besar (dari ocr.py)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal memproses verifikasi gambar: {str(e)}")
    finally:
        # Selalu hapus file sementara meskipun terjadi error
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT 3: Health Check Ollama & Hermes
# ─────────────────────────────────────────────────────────────────────────────

@router.get(
    "/verify/status",
    response_model=OllamaStatusResponse,
    summary="Cek Status Ollama & Model Hermes",
    description="Mengecek apakah Ollama sedang berjalan dan model Hermes tersedia. Gunakan untuk diagnostik sebelum menggunakan endpoint verifikasi."
)
def check_ai_status():
    return check_ollama_status()


# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINT LAMA (Tetap dipertahankan)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/check-domain")
def verify_domain(domain: str = Query(..., description="Domain email yang akan diperiksa (misal: pertamina.com)")):
    age_info = check_domain_age(domain)
    security_info = check_email_security(domain)
    
    risk_score = 0
    reasons = []
    
    if age_info.get("is_new"):
        risk_score += 50
        reasons.append(f"Domain email sangat baru (dibuat pada {age_info.get('created_at')})")
        
    if not security_info["spf_active"]:
        risk_score += 25
        reasons.append("Domain tidak mengaktifkan proteksi SPF (Rentan spoofing/pemalsuan email)")
        
    if not security_info["dmarc_active"]:
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
        "details": {
            "age": age_info,
            "security": security_info
        }
    }


@router.get("/osint/scan-email")
async def verify_email_osint(
    email: str = Query(..., description="Email yang akan dilacak footprint-nya"),
    categories: Optional[List[str]] = Query(None, description="Kategori platform (misal: social, dev, jobs, shopping)")
):
    try:
        results = await scan_email_osint(email, categories)
        return {
            "email": email,
            "found_count": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/osint/scan-username")
async def verify_username_osint(
    username: str = Query(..., description="Username yang akan dilacak footprint-nya"),
    categories: Optional[List[str]] = Query(None, description="Kategori platform (misal: social, dev, finance, community)")
):
    try:
        results = await scan_username_osint(username, categories)
        return {
            "username": username,
            "found_count": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
