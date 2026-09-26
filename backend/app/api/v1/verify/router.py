"""
Router verifikasi Verifin — Job Trust Infrastructure.

Tiga kanal input: teks, gambar (OCR), URL postingan.
    Pipeline: NER → OSINT → LLM → Fraud Network → Evidence Attribution response.

Modular:
  pipeline.py   — entity extraction, OSINT runner, fraud network, response builder
  db_cache.py   — simpan & ambil JobCase dari PostgreSQL
  web_fetcher.py — Scrapling + Instagram/Threads scraper
"""

import logging
import os
import asyncio
import json
import tempfile
import time
from typing import List
from uuid import UUID, uuid4
from sqlalchemy.orm import Session

from fastapi import APIRouter, Body, File, HTTPException, Query, UploadFile, Depends
from fastapi.responses import StreamingResponse
from app.database.postgres_client import get_db
from app.database.models import JobCase

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
)

# Import helpers dari modul terpisah
from app.api.v1.verify.pipeline import (
    _check_fraud_network,
    _extract_entities_hybrid,
    _run_osint_on_entities,
    _enrich_entities_from_osint,
    _to_response,
    _build_osint_summary,
)
from app.services.db_cache import _save_case_to_db, _get_cached_case_from_db
from app.services.web_fetcher import _fetch_url_content_and_image
from app.config import VERIFIN_DEBUG_RAW_JSON

logger = logging.getLogger(__name__)

router = APIRouter()


def _request_id() -> str:
    return uuid4().hex[:8]


def _entity_counts(entities: dict) -> dict[str, int]:
    return {
        key: len(entities.get(key) or [])
        for key in ("companies", "phones", "emails", "urls", "addresses", "salaries")
    }


def _address_probe_status(addresses: list[dict]) -> str:
    """Map nested address evidence to an honest aggregate log status."""
    if not addresses:
        return "NOT_PROVIDED"

    details = [
        item.get("address_details") or {}
        for item in addresses
        if isinstance(item, dict)
    ]
    if any(detail.get("match_level") == "exact" for detail in details):
        return "EXACT"
    if any(detail.get("match_level") == "street" for detail in details):
        return "STREET_LEVEL"
    if any(detail.get("match_level") == "area" for detail in details):
        return "AREA_ONLY"
    if any(detail.get("probe_status") == "COMPLETED" for detail in details):
        return "COMPLETED_NO_MATCH"
    if any(detail.get("probe_status") == "UNAVAILABLE" for detail in details):
        return "UNAVAILABLE"
    return "NO_RESULT"


def _log_osint_summary(request_id: str, osint_results: dict) -> None:
    timing = osint_results.get("timing") or {}
    probe_statuses = {
        "whois_domain": (
            "SKIPPED_FREE_EMAIL"
            if (osint_results.get("domain") or {}).get("skipped") == "free_email"
            else "COMPLETED"
            if (osint_results.get("domain") or {}).get("domain")
            else "NOT_PROVIDED"
        ),
        "phone_reputation": (osint_results.get("phone_probe") or {}).get("status", "N/A"),
        "address_osm": _address_probe_status(osint_results.get("address_validations") or []),
        "web_evidence": (osint_results.get("web") or {}).get("probe_status", "N/A"),
        "social_media": (osint_results.get("social") or {}).get("probe_status", "N/A"),
        "legal_registry": "NOT_AVAILABLE",
    }
    logger.info(
        "[verify][%s] OSINT done: probes=%d total=%ss statuses=%s timing=%s",
        request_id,
        len(probe_statuses),
        timing.get("osint_parallel_sec", "?"),
        probe_statuses,
        timing,
    )


def _log_end(request_id: str, source: str, started: float, response: VerifyResponse) -> None:
    duration = time.perf_counter() - started
    logger.info(
        "[verify][%s] END source=%s verdict=%s score=%s total=%.2fs model=%s",
        request_id,
        source,
        response.verdict,
        response.risk_score,
        duration,
        response.model_used,
    )


def _log_raw_json(request_id: str, label: str, payload: object) -> None:
    """Dump payload pipeline saat debug lokal diaktifkan; payload dapat berisi PII."""
    if not VERIFIN_DEBUG_RAW_JSON:
        return
    try:
        encoded = json.dumps(
            payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        # Simpan ke file di root backend folder
        import os
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "debug_json")
        os.makedirs(debug_dir, exist_ok=True)
        filename = f"{label}_{request_id}_{timestamp}.json"
        filepath = os.path.join(debug_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(encoded)
        print(f"[verify][{request_id}] {label}_JSON saved to {filepath}", flush=True)
    except Exception as e:
        print(f"[verify][{request_id}] gagal mencetak {label}_JSON: {e}", flush=True)

@router.post(
    "/verify/text",
    response_model=VerifyResponse,
    summary="Verifikasi Lowongan Kerja dari Teks",
)
async def verify_from_text(
    request: TextVerifyRequest = Body(...), 
    db: Session = Depends(get_db)
):
    request_id = _request_id()
    started = time.perf_counter()
    logger.info(
        "[verify][%s] START source=text chars=%d include_raw_text=%s",
        request_id,
        len(request.text or ""),
        request.include_raw_text,
    )

    try:
        cache_started = time.perf_counter()
        cached_resp = await asyncio.to_thread(_get_cached_case_from_db, db, request.text)
        logger.info("[verify][%s] cache lookup hit=%s duration=%.2fs", request_id, bool(cached_resp), time.perf_counter() - cache_started)
        if cached_resp:
            logger.info("[verify][%s] CACHE_HIT source=text", request_id)
            _log_raw_json(request_id, "RESPONSE_CACHE", cached_resp)
            _log_end(request_id, "text-cache", started, cached_resp)
            return cached_resp

        # NLP classifier belum aktif; simpan metadata STUB tanpa menganggapnya
        # sebagai tahap analisis yang menghasilkan sinyal risiko.
        stage_started = time.perf_counter()
        nlp_result = classify_text(request.text)
        logger.info(
            "[verify][%s] NLP skipped status=%s enabled=%s duration=%.2fs",
            request_id, nlp_result.get("status"), nlp_result.get("enabled"),
            time.perf_counter() - stage_started,
        )

        stage_started = time.perf_counter()
        entities = await _extract_entities_hybrid(request.text)
        _log_raw_json(request_id, "ENTITIES", entities)
        logger.info("[verify][%s] NER done counts=%s meta=%s duration=%.2fs", request_id, _entity_counts(entities), entities.get("_ner_meta"), time.perf_counter() - stage_started)

        stage_started = time.perf_counter()
        osint_results = await _run_osint_on_entities(entities)
        _log_osint_summary(request_id, osint_results)
        logger.info("[verify][%s] OSINT duration=%.2fs", request_id, time.perf_counter() - stage_started)

        # OSINT Enrichment: lengkapi entities dengan alamat dari hasil search
        entities = await _enrich_entities_from_osint(entities, osint_results)

        # Layer 5: Fraud Network — case memory (exact-match entity linking)
        stage_started = time.perf_counter()
        network_context = await asyncio.to_thread(_check_fraud_network, db, entities)
        logger.info("[verify][%s] fraud-network done status=%s in_network=%s reports=%s duration=%.2fs", request_id, network_context.get("status"), network_context.get("entity_in_fraud_network"), (network_context.get("community_reports") or {}).get("report_count"), time.perf_counter() - stage_started)

        raw_text = request.text if request.include_raw_text else None
        stage_started = time.perf_counter()
        analysis = await analyze_with_verifin(entities, osint_results, raw_text=raw_text)
        _log_raw_json(request_id, "ANALYSIS", analysis)
        logger.info("[verify][%s] LLM done verdict=%s score=%s model=%s duration=%.2fs", request_id, analysis.get("verdict"), analysis.get("risk_score"), analysis.get("model_used"), time.perf_counter() - stage_started)

        # Attach NLP + network context untuk SHAP explainer
        analysis["nlp_result"] = nlp_result
        analysis["network_context"] = network_context

        response = _to_response(analysis, entities, osint_results)
        save_status = await asyncio.to_thread(
            _save_case_to_db,
            db, request.text, analysis, osint_results, entities=entities, source="text"
        )
        analysis["case_id"] = save_status.get("case_id")
        response = _to_response(analysis, entities, osint_results)
        _log_raw_json(request_id, "RESPONSE", response)
        if response.osint is not None:
            response.osint["persistence_status"] = save_status.get("status")
        _log_end(request_id, "text", started, response)
        return response
    except Exception as e:
        logger.exception("[verify][%s] ERROR source=text after=%.2fs: %s", request_id, time.perf_counter() - started, e)
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
    request_id = _request_id()
    started = time.perf_counter()
    logger.info("[verify][%s] START source=image filename=%s content_type=%s", request_id, file.filename, file.content_type)
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
        ocr_metrics: dict = {}
        # ponytail: request sinkron (tanpa background job) — cukup untuk demo;
        # upgrade ke FastAPI BackgroundTasks + polling job_id kalau latency
        # OSINT/LLM (>2 mnt) butuh progress sejati di FE.
        raw_text = await asyncio.to_thread(extract_text_from_image, tmp_path, ocr_metrics)
        if not raw_text or not raw_text.strip():
            raise HTTPException(
                status_code=422,
                detail="Tidak ada teks yang berhasil dibaca dari gambar. Coba unggah gambar yang lebih jelas.",
            )
        logger.info("[OCR] image metrics=%s", ocr_metrics)
        logger.info("[verify][%s] OCR done chars=%d metrics=%s duration=%.2fs", request_id, len(raw_text), ocr_metrics, time.perf_counter() - started)

        # Cache-check dari hash teks OCR — gambar identik = hasil identik
        cached_resp = await asyncio.to_thread(_get_cached_case_from_db, db, raw_text)
        if cached_resp:
            logger.info("[verify][%s] cache hit source=image", request_id)
            logger.info("[verify][%s] CACHE_HIT source=image", request_id)
            _log_raw_json(request_id, "RESPONSE_CACHE", cached_resp)
            _log_end(request_id, "image-cache", started, cached_resp)
            return cached_resp

        stage_started = time.perf_counter()
        entities = await _extract_entities_hybrid(raw_text)
        _log_raw_json(request_id, "ENTITIES", entities)
        logger.info("[verify][%s] NER done counts=%s meta=%s duration=%.2fs", request_id, _entity_counts(entities), entities.get("_ner_meta"), time.perf_counter() - stage_started)

        # NLP classifier belum aktif; hanya ekspos metadata STUB.
        stage_started = time.perf_counter()
        nlp_result = classify_text(raw_text)
        logger.info("[verify][%s] NLP skipped status=%s enabled=%s duration=%.2fs", request_id, nlp_result.get("status"), nlp_result.get("enabled"), time.perf_counter() - stage_started)

        stage_started = time.perf_counter()
        osint_results = await _run_osint_on_entities(entities)
        _log_osint_summary(request_id, osint_results)
        logger.info("[verify][%s] OSINT duration=%.2fs", request_id, time.perf_counter() - stage_started)

        # OSINT Enrichment: lengkapi entities dengan alamat dari hasil search
        entities = await _enrich_entities_from_osint(entities, osint_results)

        # Layer 5: Fraud Network Check
        stage_started = time.perf_counter()
        network_context = await asyncio.to_thread(_check_fraud_network, db, entities)
        logger.info("[verify][%s] fraud-network done status=%s in_network=%s reports=%s duration=%.2fs", request_id, network_context.get("status"), network_context.get("entity_in_fraud_network"), (network_context.get("community_reports") or {}).get("report_count"), time.perf_counter() - stage_started)

        stage_started = time.perf_counter()
        analysis = await analyze_with_verifin(
            entities, osint_results, raw_text=raw_text
        )
        _log_raw_json(request_id, "ANALYSIS", analysis)
        logger.info("[verify][%s] LLM done verdict=%s score=%s model=%s duration=%.2fs", request_id, analysis.get("verdict"), analysis.get("risk_score"), analysis.get("model_used"), time.perf_counter() - stage_started)
        analysis["nlp_result"] = nlp_result
        analysis["network_context"] = network_context

        response = _to_response(analysis, entities, osint_results)
        save_status = await asyncio.to_thread(
            _save_case_to_db,
            db, raw_text, analysis, osint_results, entities=entities, source="image"
        )
        analysis["case_id"] = save_status.get("case_id")
        response = _to_response(analysis, entities, osint_results)
        _log_raw_json(request_id, "RESPONSE", response)
        if response.osint is not None:
            response.osint.setdefault("timing", {})["ocr"] = ocr_metrics
            response.osint["persistence_status"] = save_status.get("status")
        _log_end(request_id, "image", started, response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[verify][%s] ERROR source=image after=%.2fs: %s", request_id, time.perf_counter() - started, e)
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
    request_id = _request_id()
    started = time.perf_counter()
    logger.info("[verify][%s] START source=url chars=%d", request_id, len(request.url or ""))
    cached_resp = await asyncio.to_thread(_get_cached_case_from_db, db, request.url)
    if cached_resp:
        logger.info("[verify][%s] cache hit source=url", request_id)
        logger.info("[verify][%s] CACHE_HIT source=url", request_id)
        _log_raw_json(request_id, "RESPONSE_CACHE", cached_resp)
        _log_end(request_id, "url-cache", started, cached_resp)
        return cached_resp

    tmp_paths = []
    try:
        caption_text, tmp_paths = await _fetch_url_content_and_image(request.url)
        logger.info("[verify][%s] URL fetch done caption_chars=%d images=%d duration=%.2fs", request_id, len(caption_text or ""), len(tmp_paths), time.perf_counter() - started)
        
        ocr_texts = []
        for p in tmp_paths:
            if p and os.path.exists(p):
                try:
                    t = await asyncio.to_thread(extract_text_from_image, p)
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

        cached_resp_full = await asyncio.to_thread(_get_cached_case_from_db, db, full_raw_text)
        if cached_resp_full:
            return cached_resp_full
        
        if not full_raw_text or len(full_raw_text) < 15:
            raise HTTPException(
                status_code=422,
                detail="Sistem tidak dapat mengambil konten atau teks dari URL tersebut. Pastikan link dapat diakses publik.",
            )

        entities = await _extract_entities_hybrid(full_raw_text)
        _log_raw_json(request_id, "ENTITIES", entities)
        logger.info("[verify][%s] NER done counts=%s meta=%s duration=%.2fs", request_id, _entity_counts(entities), entities.get("_ner_meta"), time.perf_counter() - started)
        stage_started = time.perf_counter()
        osint_results = await _run_osint_on_entities(entities)
        _log_osint_summary(request_id, osint_results)
        logger.info("[verify][%s] OSINT duration=%.2fs", request_id, time.perf_counter() - stage_started)

        # OSINT Enrichment: lengkapi entities dengan alamat dari hasil search
        entities = await _enrich_entities_from_osint(entities, osint_results)

        # Layer 5: Fraud Network Check (case memory + community reports)
        stage_started = time.perf_counter()
        network_context = await asyncio.to_thread(_check_fraud_network, db, entities)
        logger.info("[verify][%s] fraud-network done status=%s in_network=%s reports=%s duration=%.2fs", request_id, network_context.get("status"), network_context.get("entity_in_fraud_network"), (network_context.get("community_reports") or {}).get("report_count"), time.perf_counter() - stage_started)

        stage_started = time.perf_counter()
        analysis = await analyze_with_verifin(
            entities, osint_results, raw_text=full_raw_text
        )
        _log_raw_json(request_id, "ANALYSIS", analysis)
        logger.info("[verify][%s] LLM done verdict=%s score=%s model=%s duration=%.2fs", request_id, analysis.get("verdict"), analysis.get("risk_score"), analysis.get("model_used"), time.perf_counter() - stage_started)
        analysis["network_context"] = network_context
        response = _to_response(analysis, entities, osint_results)
        save_status = await asyncio.to_thread(
            _save_case_to_db,
            db, full_raw_text, analysis, osint_results, entities=entities, source="url"
        )
        analysis["case_id"] = save_status.get("case_id")
        response = _to_response(analysis, entities, osint_results)
        _log_raw_json(request_id, "RESPONSE", response)
        if response.osint is not None:
            response.osint["persistence_status"] = save_status.get("status")
        _log_end(request_id, "url", started, response)
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[verify][%s] ERROR source=url after=%.2fs: %s", request_id, time.perf_counter() - started, e)
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
                "raw_text_preview": c.raw_text_preview,
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
        from sqlalchemy import text as sa_text
        filters = []
        params: dict = {"limit": limit}

        if phone:
            filters.append("phones @> :phone_json::jsonb")
            params["phone_json"] = f'["{phone.strip()}"]'
        if email:
            filters.append("emails @> :email_json::jsonb")
            params["email_json"] = f'["{email.strip().lower()}"]'
        if company:
            # company_name exact-ish: ILIKE (substring ok untuk partial match)
            filters.append("LOWER(company_name) LIKE :company_pat")
            params["company_pat"] = f"%{company.strip().lower()}%"

        where = f"WHERE {' OR '.join(filters)}" if filters else ""
        # ponytail: O(n) scan pada JSONB @> tanpa GIN index; tambah GIN index pada phones/emails kalau > 10k kasus
        sql = sa_text(f"""
            SELECT id, company_name, phones, emails, verdict, risk_score, created_at
            FROM job_cases
            {where}
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        rows = db.execute(sql, params).mappings().all()
        hits = [
            {
                "id": str(r["id"]),
                "company_name": r["company_name"],
                "phones": r["phones"],
                "emails": r["emails"],
                "verdict": r["verdict"],
                "risk_score": r["risk_score"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
        return {"count": len(hits), "cases": hits}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gagal lookup case: {e}")


@router.get(
    "/cases/{case_id}",
    summary="Ambil detail kasus berdasarkan ID",
    description="Mengembalikan detail lengkap analisis dari database PostgreSQL untuk case_id tertentu."
)
def get_case_by_id(case_id: str, db: Session = Depends(get_db)):
    from sqlalchemy import cast, String
    db_case = None
    try:
        uuid_obj = UUID(case_id)
        db_case = db.query(JobCase).filter(JobCase.id == uuid_obj).first()
    except (ValueError, AttributeError):
        db_case = None

    if not db_case:
        # Prefix lookup (misal: "fdd1b836")
        db_case = db.query(JobCase).filter(cast(JobCase.id, String).like(f"{case_id}%")).first()

    if not db_case:
        raise HTTPException(status_code=404, detail="Kasus tidak ditemukan")
    llm_output = db_case.llm_output or {}
    cached_osint = db_case.osint_summary or {}
    osint = cached_osint.get("response_osint") or {}
    stored_entities = db_case.entities or {
        "companies": db_case.companies or [],
        "phones": db_case.phones or [],
        "emails": db_case.emails or [],
        "urls": db_case.urls or [],
        "addresses": db_case.addresses or [],
        "location_candidates": [],
        "salaries": db_case.salaries or [],
    }
    entities = {
        "companies": stored_entities.get("companies") or [],
        "contacts": stored_entities.get("contacts") or stored_entities.get("phones") or [],
        "emails": stored_entities.get("emails") or [],
        "urls": stored_entities.get("urls") or [],
        "addresses": stored_entities.get("addresses") or [],
        "location_candidates": stored_entities.get("location_candidates") or [],
        "salaries": stored_entities.get("salaries") or [],
    }
    return {
        "id": str(db_case.id),
        "case_id": str(db_case.id),
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
        "summary": llm_output.get("summary", ""),
        "risk_factors": llm_output.get("risk_factors", []),
        "safe_factors": llm_output.get("safe_factors", []),
        "recommendations": llm_output.get("recommendations", []),
        "model_used": llm_output.get("model_used"),
        "entities": entities,
        "osint": osint,
        "shap_explanation": llm_output.get("shap_explanation"),
        "llm_output": llm_output,
        "osint_summary": cached_osint,
        "osint_failed": db_case.osint_failed,
        "created_at": db_case.created_at.isoformat() if db_case.created_at else None,
    }


# ── SSE Streaming Endpoint ──────────────────────────────────────────────
# Endpoint ini mengirim event real-time per pipeline stage ke frontend,
# sehingga loading animation di VerifyBox advance berdasarkan progress
# nyata, bukan timer hardcoded.

def _sse_event(event: str, data: dict) -> str:
    """Format SSE event: data: {json}\\n\\n"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _verify_url_stream_generator(url: str, additional_text: str, db_session):
    """
    Generator async yang menjalankan pipeline verifikasi dan yield SSE event
    setelah setiap stage selesai.
    """
    request_id = _request_id()
    started = time.perf_counter()

    yield _sse_event("start", {"request_id": request_id, "message": "Memulai verifikasi..."})

    tmp_paths = []
    try:
        # ── Stage 1: URL Fetch ──────────────────────────────────────────
        yield _sse_event("stage", {"stage": "fetch", "status": "processing", "message": "Mengambil konten dari URL..."})
        caption_text, tmp_paths = await _fetch_url_content_and_image(url)
        logger.info("[verify-stream][%s] URL fetch done duration=%.2fs", request_id, time.perf_counter() - started)

        # ── Stage 1b: OCR ───────────────────────────────────────────────
        yield _sse_event("stage", {"stage": "ocr", "status": "processing", "message": "Mengenali teks dari gambar poster..."})
        ocr_texts = []
        for p in tmp_paths:
            if p and os.path.exists(p):
                try:
                    t = await asyncio.to_thread(extract_text_from_image, p)
                    if t and t.strip():
                        ocr_texts.append(t.strip())
                except Exception as exc:
                    logger.warning("URL OCR Error: %s", exc)

        combined_ocr_text = "\n".join(ocr_texts).strip()
        text_blocks = [f"URL Target: {url}"]
        if combined_ocr_text:
            text_blocks.append(f"[TEKS UTAMA POSTER/GAMBAR LOWONGAN (OCR)]:\n{combined_ocr_text}")
        if caption_text and caption_text.strip():
            text_blocks.append(f"[TEKS CAPTION / DESKRIPSI POSTINGAN]:\n{caption_text.strip()}")
        if additional_text and additional_text.strip():
            text_blocks.append(f"[UTAS BALASAN / TEKS TAMBAHAN]:\n{additional_text.strip()}")

        full_raw_text = "\n\n".join(text_blocks).strip()

        if not full_raw_text or len(full_raw_text) < 15:
            yield _sse_event("error", {"message": "Sistem tidak dapat mengambil konten atau teks dari URL tersebut."})
            return

        # ── Stage 2: NER (Entity Extraction) ────────────────────────────
        yield _sse_event("stage", {"stage": "ner", "status": "processing", "message": "Mengekstrak entitas (perusahaan, kontak, alamat)..."})
        entities = await _extract_entities_hybrid(full_raw_text)
        _log_raw_json(request_id, "ENTITIES", entities)
        logger.info("[verify-stream][%s] NER done counts=%s duration=%.2fs", request_id, _entity_counts(entities), time.perf_counter() - started)
        yield _sse_event("stage", {
            "stage": "ner", "status": "done",
            "message": f"Ditemukan {len(entities.get('companies', []))} perusahaan, {len(entities.get('phones', []))} kontak",
            "entities": {k: v for k, v in entities.items() if k != "_ner_meta"}
        })

        # ── Stage 3: OSINT ──────────────────────────────────────────────
        yield _sse_event("stage", {"stage": "osint", "status": "processing", "message": "Menjalankan OSINT probes (WHOIS, peta, media sosial)..."})
        stage_started = time.perf_counter()
        osint_results = await _run_osint_on_entities(entities)
        _log_osint_summary(request_id, osint_results)
        logger.info("[verify-stream][%s] OSINT done duration=%.2fs", request_id, time.perf_counter() - stage_started)

        # OSINT Enrichment
        entities = await _enrich_entities_from_osint(entities, osint_results)
        yield _sse_event("stage", {"stage": "osint", "status": "done", "message": "OSINT selesai"})

        # ── Stage 4: Fraud Network ─────────────────────────────────────
        yield _sse_event("stage", {"stage": "graph", "status": "processing", "message": "Memeriksa jaringan fraud..."})
        stage_started = time.perf_counter()
        network_context = await asyncio.to_thread(_check_fraud_network, db_session, entities)
        logger.info("[verify-stream][%s] fraud-network done duration=%.2fs", request_id, time.perf_counter() - stage_started)
        yield _sse_event("stage", {"stage": "graph", "status": "done", "message": "Pemeriksaan jaringan selesai"})

        # ── Stage 5: LLM Reasoning ─────────────────────────────────────
        yield _sse_event("stage", {"stage": "ai", "status": "processing", "message": "AI menganalisis dan menyusun verdict..."})
        stage_started = time.perf_counter()
        analysis = await analyze_with_verifin(
            entities, osint_results, raw_text=full_raw_text
        )
        _log_raw_json(request_id, "ANALYSIS", analysis)
        logger.info("[verify-stream][%s] LLM done verdict=%s score=%s duration=%.2fs", request_id, analysis.get("verdict"), analysis.get("risk_score"), time.perf_counter() - stage_started)

        analysis["network_context"] = network_context
        response = _to_response(analysis, entities, osint_results)
        save_status = await asyncio.to_thread(
            _save_case_to_db,
            db_session, full_raw_text, analysis, osint_results, entities=entities, source="url"
        )
        analysis["case_id"] = save_status.get("case_id")
        response = _to_response(analysis, entities, osint_results)
        _log_raw_json(request_id, "RESPONSE", response)
        if response.osint is not None:
            response.osint["persistence_status"] = save_status.get("status")

        # ── Final: kirim response lengkap ──────────────────────────────
        yield _sse_event("done", {
            "message": "Verifikasi selesai",
            "case_id": response.case_id,
            "verdict": response.verdict,
            "risk_score": response.risk_score,
            "response": response.model_dump(),
        })
        _log_end(request_id, "url-stream", started, response)

    except Exception as e:
        logger.exception("[verify-stream][%s] ERROR after=%.2fs: %s", request_id, time.perf_counter() - started, e)
        safe_msg = str(e).encode("ascii", errors="ignore").decode("ascii") or "Terjadi kesalahan internal."
        yield _sse_event("error", {"message": safe_msg})
    finally:
        for p in tmp_paths:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


@router.post(
    "/verify/url/stream",
    summary="Verifikasi URL dengan SSE Streaming (real-time progress)",
    description=(
        "Endpoint SSE yang mengirim event real-time per pipeline stage. "
        "Frontend menggunakan EventSource untuk advance loading animation "
        "berdasarkan progress nyata dari backend."
    ),
)
async def verify_url_stream(
    request: UrlVerifyRequest = Body(...),
    db: Session = Depends(get_db)
):
    return StreamingResponse(
        _verify_url_stream_generator(
            request.url,
            request.additional_text or "",
            db
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
