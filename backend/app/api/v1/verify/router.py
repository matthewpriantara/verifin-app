import logging
import os
import asyncio
import json
import re
import tempfile
import time
from uuid import UUID, uuid4
from sqlalchemy.orm import Session

from fastapi import APIRouter, Body, File, Form, HTTPException, Query, UploadFile, Depends
from fastapi.responses import StreamingResponse
from app.database.postgres_client import get_db
from app.database.models import JobCase

from app.api.v1.verify.schema import (
    LlmStatusResponse,
    TextVerifyRequest,
    UrlVerifyRequest,
    VerifyResponse,
)
from app.services.llm.verifin_reasoning import analyze_with_verifin, check_ai_status
from app.services.ocr import extract_text_from_image_async
from app.services.nlp.classifier import classify_text
from app.services.ner import is_multi_employer
from app.services.llm.vision import read_image_with_vision
from app.services.precheck import VISION_MARKER, apply_forced, assess_input
from app.services.osint.whois_handler import (
    check_domain_age,
    check_email_security,
)

from app.api.v1.verify.pipeline import (
    _check_fraud_network,
    _extract_entities_hybrid,
    _run_osint_on_entities,
    _enrich_entities_from_osint,
    _to_response,
    attach_shap_explanation,
)
from app.services.db_cache import _save_case_to_db, _get_cached_case_from_db, _get_cached_case_by_url
from app.services.llm.verifin_reasoning import _soften_summary_claims
from app.services.web_fetcher import _fetch_url_content_and_image
from app.config import RATE_LIMIT_VERIFY_PER_MIN, VERIFIN_DEBUG_RAW_JSON
from app.services.case_search import like_escape

MAX_IMAGE_BYTES = 20 * 1024 * 1024
from app.services.security import RateLimiter, require_admin

logger = logging.getLogger(__name__)

router = APIRouter()
_verify_limit = RateLimiter(RATE_LIMIT_VERIFY_PER_MIN).dependency("verify")


def _request_id() -> str:
    return uuid4().hex[:8]


def _entity_counts(entities: dict) -> dict[str, int]:
    return {
        key: len(entities.get(key) or [])
        for key in ("companies", "phones", "emails", "urls", "addresses", "salaries")
    }


def _address_probe_status(addresses: list[dict]) -> str:
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
    if not VERIFIN_DEBUG_RAW_JSON:
        return
    try:
        encoded = json.dumps(
            payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
        import os
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        debug_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "debug_json")
        os.makedirs(debug_dir, exist_ok=True)
        filename = f"{label}_{request_id}_{timestamp}.json"
        filepath = os.path.join(debug_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(encoded)
        logger.info("[verify][%s] %s_JSON saved to %s", request_id, label, filepath)
    except Exception as e:
        logger.warning("[verify][%s] gagal mencetak %s_JSON: %s", request_id, label, e)

@router.post(
    "/verify/text",
    dependencies=[Depends(_verify_limit)],
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

        stage_started = time.perf_counter()
        entities = await _extract_entities_hybrid(request.text)
        _log_raw_json(request_id, "ENTITIES", entities)
        logger.info("[verify][%s] NER done counts=%s meta=%s duration=%.2fs", request_id, _entity_counts(entities), entities.get("_ner_meta"), time.perf_counter() - stage_started)

        raw_text = request.text
        nlp_result = _classify_text_signals(raw_text, entities)
        source = request.source or "text"
        stop = _precheck(
            request_id, raw_text, entities,
            source=source, source_url=request.source_url,
            intervention=request.intervention, intervention_kind=request.intervention_kind,
        )
        if stop:
            return stop
        if source == "url" and request.source_url:
            entities["urls"] = [request.source_url] + [u for u in entities.get("urls") or [] if u != request.source_url]

        stage_started = time.perf_counter()
        osint_results = await _run_osint_on_entities(entities)
        _log_osint_summary(request_id, osint_results)
        _attach_input_notes(osint_results, entities)
        logger.info("[verify][%s] OSINT duration=%.2fs", request_id, time.perf_counter() - stage_started)

        entities = await _enrich_entities_from_osint(entities, osint_results)

        stage_started = time.perf_counter()
        network_context = await asyncio.to_thread(_check_fraud_network, db, entities, request.text)
        _merge_network(osint_results, network_context)
        logger.info("[verify][%s] fraud-network done status=%s in_network=%s reports=%s duration=%.2fs", request_id, network_context.get("status"), network_context.get("entity_in_fraud_network"), (network_context.get("community_reports") or {}).get("report_count"), time.perf_counter() - stage_started)

        stage_started = time.perf_counter()
        analysis = await analyze_with_verifin(
            entities, osint_results, raw_text=raw_text, text_signals=nlp_result["behavioral_features"]
        )
        _log_raw_json(request_id, "ANALYSIS", analysis)
        logger.info("[verify][%s] LLM done verdict=%s score=%s model=%s duration=%.2fs", request_id, analysis.get("verdict"), analysis.get("risk_score"), analysis.get("model_used"), time.perf_counter() - stage_started)

        analysis["network_context"] = network_context
        analysis["nlp_result"] = nlp_result
        attach_shap_explanation(analysis, entities, osint_results)
        save_status = await asyncio.to_thread(
            _save_case_to_db,
            db, request.text, analysis, osint_results, entities=entities, source=source
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
            status_code=500, detail="Gagal memproses verifikasi teks. Coba lagi sebentar lagi."
        ) from e


@router.post(
    "/verify/image",
    dependencies=[Depends(_verify_limit)],
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
    additional_text: str | None = Form(
        default=None,
        description="Konteks teks tambahan atau catatan dari postingan untuk melengkapi OCR",
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

    # Dibaca bertahap supaya file raksasa ditolak sebelum memenuhi memori.
    contents = await file.read(MAX_IMAGE_BYTES + 1)
    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Ukuran file terlalu besar. Maksimal 20 MB.")

    ext = {"image/png": ".png", "image/webp": ".webp"}.get(file.content_type, ".jpg")
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        ocr_metrics: dict = {}
        raw_text, vision_text = await _read_image(tmp_path, ocr_metrics)
        if not raw_text:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Teks di gambar tidak terbaca. Coba screenshot langsung dari layar (bukan foto layar), "
                    "potong bagian lowongannya saja, atau tempel teksnya."
                ),
            )
        if additional_text and additional_text.strip():
            raw_text = f"{raw_text.strip()}\n\n[Konteks Tambahan]:\n{additional_text.strip()}"
        logger.info("[OCR] image metrics=%s", ocr_metrics)
        logger.info("[verify][%s] OCR done chars=%d metrics=%s duration=%.2fs", request_id, len(raw_text), ocr_metrics, time.perf_counter() - started)

        cached_resp = await asyncio.to_thread(_get_cached_case_from_db, db, raw_text)
        if cached_resp:
            logger.info("[verify][%s] cache hit source=image", request_id)
            logger.info("[verify][%s] CACHE_HIT source=image", request_id)
            _log_raw_json(request_id, "RESPONSE_CACHE", cached_resp)
            _log_end(request_id, "image-cache", started, cached_resp)
            return cached_resp

        analysis_text = _with_vision(raw_text, [vision_text])
        stage_started = time.perf_counter()
        entities = await _extract_entities_hybrid(analysis_text)
        _log_raw_json(request_id, "ENTITIES", entities)
        logger.info("[verify][%s] NER done counts=%s meta=%s vision_chars=%d duration=%.2fs", request_id, _entity_counts(entities), entities.get("_ner_meta"), len(vision_text), time.perf_counter() - stage_started)

        nlp_result = _classify_text_signals(raw_text, entities)
        stop = _precheck(request_id, analysis_text, entities, source="image")
        if stop:
            return stop

        stage_started = time.perf_counter()
        osint_results = await _run_osint_on_entities(entities)
        _log_osint_summary(request_id, osint_results)
        _attach_input_notes(osint_results, entities)
        logger.info("[verify][%s] OSINT duration=%.2fs", request_id, time.perf_counter() - stage_started)

        entities = await _enrich_entities_from_osint(entities, osint_results)

        stage_started = time.perf_counter()
        network_context = await asyncio.to_thread(_check_fraud_network, db, entities, raw_text)
        _merge_network(osint_results, network_context)
        logger.info("[verify][%s] fraud-network done status=%s in_network=%s reports=%s duration=%.2fs", request_id, network_context.get("status"), network_context.get("entity_in_fraud_network"), (network_context.get("community_reports") or {}).get("report_count"), time.perf_counter() - stage_started)

        stage_started = time.perf_counter()
        analysis = await analyze_with_verifin(
            entities, osint_results, raw_text=analysis_text, text_signals=nlp_result["behavioral_features"]
        )
        _log_raw_json(request_id, "ANALYSIS", analysis)
        logger.info("[verify][%s] LLM done verdict=%s score=%s model=%s duration=%.2fs", request_id, analysis.get("verdict"), analysis.get("risk_score"), analysis.get("model_used"), time.perf_counter() - stage_started)
        analysis["network_context"] = network_context
        analysis["nlp_result"] = nlp_result
        attach_shap_explanation(analysis, entities, osint_results)
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
            status_code=500, detail="Gagal memproses verifikasi gambar. Coba lagi sebentar lagi."
        ) from e
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

@router.post(
    "/verify/url",
    dependencies=[Depends(_verify_limit)],
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
    cached_resp = None
    # Teks tambahan mengubah isi yang dianalisis, jadi cache per-URL tidak boleh dipakai.
    if not (request.additional_text and request.additional_text.strip()):
        cached_resp = await asyncio.to_thread(_get_cached_case_by_url, db, request.url)
        if not cached_resp:
            cached_resp = await asyncio.to_thread(_get_cached_case_from_db, db, request.url)
    if cached_resp:
        logger.info("[verify][%s] cache hit source=url", request_id)
        logger.info("[verify][%s] CACHE_HIT source=url", request_id)
        _log_raw_json(request_id, "RESPONSE_CACHE", cached_resp)
        _log_end(request_id, "url-cache", started, cached_resp)
        return cached_resp

    tmp_paths = []
    carousel_meta = {}
    try:
        caption_text, tmp_paths, carousel_meta = await _fetch_url_content_and_image(request.url)
        logger.info(
            "[verify][%s] URL fetch done caption_chars=%d images=%d total_images=%d duration=%.2fs",
            request_id, len(caption_text or ""), len(tmp_paths), carousel_meta.get("total_images", 0), time.perf_counter() - started
        )

        ocr_texts = []
        vision_texts = []
        for p in tmp_paths:
            if p and os.path.exists(p):
                try:
                    t, v = await _read_image(p)
                    if t:
                        ocr_texts.append(t)
                    if v:
                        vision_texts.append(v)
                except Exception as exc:
                    logger.warning("URL OCR Error: %s", exc)

        combined_ocr_text = "\n".join(ocr_texts).strip()

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

        analysis_text = _with_vision(full_raw_text, vision_texts)
        entities = await _extract_entities_hybrid(analysis_text)
        _log_raw_json(request_id, "ENTITIES", entities)
        logger.info("[verify][%s] NER done counts=%s meta=%s duration=%.2fs", request_id, _entity_counts(entities), entities.get("_ner_meta"), time.perf_counter() - started)

        nlp_result = _classify_text_signals(full_raw_text, entities)
        stop = _precheck(request_id, analysis_text, entities, source="url", source_url=request.url)
        if stop:
            return stop

        stage_started = time.perf_counter()
        osint_results = await _run_osint_on_entities(entities)
        _log_osint_summary(request_id, osint_results)
        _attach_input_notes(osint_results, entities)
        logger.info("[verify][%s] OSINT duration=%.2fs", request_id, time.perf_counter() - stage_started)

        entities = await _enrich_entities_from_osint(entities, osint_results)

        stage_started = time.perf_counter()
        network_context = await asyncio.to_thread(_check_fraud_network, db, entities, full_raw_text)
        _merge_network(osint_results, network_context)
        logger.info("[verify][%s] fraud-network done status=%s in_network=%s reports=%s duration=%.2fs", request_id, network_context.get("status"), network_context.get("entity_in_fraud_network"), (network_context.get("community_reports") or {}).get("report_count"), time.perf_counter() - stage_started)

        stage_started = time.perf_counter()
        analysis = await analyze_with_verifin(
            entities, osint_results, raw_text=analysis_text, text_signals=nlp_result["behavioral_features"]
        )
        _log_raw_json(request_id, "ANALYSIS", analysis)
        logger.info("[verify][%s] LLM done verdict=%s score=%s model=%s duration=%.2fs", request_id, analysis.get("verdict"), analysis.get("risk_score"), analysis.get("model_used"), time.perf_counter() - stage_started)
        analysis["network_context"] = network_context
        analysis["nlp_result"] = nlp_result
        if carousel_meta.get("total_images", 0) > carousel_meta.get("processed_images", 0):
            if "recommendations" not in analysis or not isinstance(analysis["recommendations"], list):
                analysis["recommendations"] = []
            analysis["recommendations"].append(
                f"Postingan memuat {carousel_meta['total_images']} gambar (hanya {carousel_meta['processed_images']} slide pertama yang terbaca). Bila kontak atau kualifikasi ada di slide berikutnya, unggah tangkapan layar langsung ke Verifin."
            )
        if request.url:
            if "urls" not in entities or not isinstance(entities["urls"], list):
                entities["urls"] = [request.url]
            elif request.url not in entities["urls"]:
                entities["urls"].insert(0, request.url)
        attach_shap_explanation(analysis, entities, osint_results)
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
        raise HTTPException(
            status_code=500, detail="Gagal memproses verifikasi URL. Coba lagi sebentar lagi."
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


@router.get("/check-domain", dependencies=[Depends(_verify_limit)])
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

@router.get(
    "/cases",
    dependencies=[Depends(require_admin)],
    summary="Ambil semua daftar kasus (khusus admin)",
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
        logger.warning("[Cases] %s", e)
        raise HTTPException(status_code=500, detail="Gagal mengambil kasus.")


@router.get(
    "/cases/lookup/by-entity",
    dependencies=[Depends(require_admin)],
    summary="Cari case history by HP / email / company (khusus admin)",
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
        from sqlalchemy import func, or_, cast, String
        query = db.query(JobCase)
        conditions = []

        if phone:
            digits = "".join(c for c in phone if c.isdigit())
            canon = digits[2:] if digits.startswith("62") else (digits[1:] if digits.startswith("0") else digits)
            if len(canon) < 8:
                raise HTTPException(status_code=400, detail="Nomor terlalu pendek.")
            conditions.append(cast(JobCase.phones, String).like(f"%{like_escape(canon)}%", escape="\\"))
        if email:
            conditions.append(cast(JobCase.emails, String).like(f"%{like_escape(email.strip().lower())}%", escape="\\"))
        if company:
            conditions.append(func.lower(JobCase.company_name).like(f"%{like_escape(company.strip().lower())}%", escape="\\"))

        if conditions:
            query = query.filter(or_(*conditions))

        rows = query.order_by(JobCase.created_at.desc()).limit(limit).all()
        hits = [
            {
                "id": str(r.id),
                "company_name": r.company_name,
                "phones": r.phones,
                "emails": r.emails,
                "verdict": r.verdict,
                "risk_score": r.risk_score,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]
        return {"count": len(hits), "cases": hits}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("[Case Lookup] %s", e)
        raise HTTPException(status_code=500, detail="Gagal mencari kasus.")


@router.get(
    "/cases/search",
    summary="Cari lowongan yang sudah pernah dianalisis",
    description=(
        "Pencarian publik berdasarkan nama perusahaan, nomor HP, email, atau link postingan. "
        "Hanya mengembalikan ringkasan (tanpa teks mentah, nomor, atau email)."
    ),
)
def search_cases_public(
    q: str | None = Query(None, max_length=300, description="Nama PT, nomor HP, email, atau link"),
    verdict: str | None = Query(None, description="AMAN / WASPADA / BAHAYA"),
    limit: int = Query(20, ge=1, le=50),
    skip: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    from app.services.case_search import search_cases

    try:
        return search_cases(db, q, verdict=verdict, limit=limit, skip=skip)
    except Exception as e:
        logger.warning("[Case Search] %s", e)
        raise HTTPException(status_code=500, detail="Gagal mencari riwayat lowongan")


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

    # Awalan ID (mis. "#5E8949DF" di UI) tetap didukung, tapi minimal 8 karakter heksadesimal
    # supaya riwayat tidak bisa ditelusuri dengan menebak satu-dua karakter.
    if not db_case and re.fullmatch(r"[0-9a-fA-F-]{8,36}", case_id or ""):
        db_case = db.query(JobCase).filter(cast(JobCase.id, String).like(f"{case_id.lower()}%")).first()

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
        "source": db_case.source,
        "company_name": db_case.company_name,
        "companies": db_case.companies,
        "phones": db_case.phones,
        "emails": db_case.emails,
        "urls": db_case.urls,
        "addresses": db_case.addresses,
        "salaries": db_case.salaries,
        "verdict": db_case.verdict,
        "risk_score": db_case.risk_score,
        "summary": _soften_summary_claims(llm_output.get("summary", "")),
        "risk_factors": llm_output.get("risk_factors", []),
        "safe_factors": llm_output.get("safe_factors", []),
        "recommendations": llm_output.get("recommendations", []),
        "model_used": llm_output.get("model_used"),
        "entities": entities,
        "osint": osint,
        "shap_explanation": llm_output.get("shap_explanation"),
        "osint_failed": db_case.osint_failed,
        "created_at": db_case.created_at.isoformat() if db_case.created_at else None,
    }


def _merge_network(osint_results: dict, network_context: dict) -> None:
    """Riwayat kasus dan laporan komunitas masuk ke bukti SEBELUM penalaran LLM, supaya ikut
    menentukan skor (bukan hanya ditempel di laporan setelah skor jadi)."""
    if isinstance(osint_results, dict) and isinstance(network_context, dict):
        osint_results["fraud_network"] = {**(osint_results.get("fraud_network") or {}), **network_context}


def _classify_text_signals(raw_text: str, entities: dict) -> dict:
    """Sinyal teks deterministik; nama perusahaan hasil NER ikut dipakai supaya "Kirim CV" atau
    nama hotel tanpa awalan PT tidak salah dibaca."""
    nlp_result = classify_text(raw_text, entities.get("companies"))
    if nlp_result["behavioral_features"].get("has_fee_request"):
        entities["has_fee_request"] = True
    c_meta = nlp_result.get("content_validation") or {}
    if not c_meta.get("is_job_posting"):
        entities["not_a_job_posting"] = True
    if is_multi_employer(entities):
        entities["is_multi_employer"] = True
    return nlp_result


def _precheck(
    request_id: str,
    text: str,
    entities: dict,
    *,
    source: str,
    source_url: str | None = None,
    intervention: str | None = None,
    intervention_kind: str | None = None,
) -> VerifyResponse | None:
    """Tahap "Memeriksa isi". Mengembalikan respons `needs_input` bila proses harus berhenti dan
    bertanya; None bila boleh lanjut ke OSINT. Catatan yang tidak menghentikan proses disimpan di
    entities["_input_notes"]."""
    result = assess_input(text, entities)
    entities["not_a_job_posting"] = result["not_job"]
    notes = list(result["notes"])
    if intervention == "force":
        apply_forced(entities, intervention_kind)
        notes.insert(0, {
            "not_job": "Kamu memilih tetap memeriksa input yang sepertinya bukan lowongan. Hasil ini tidak disimpan ke riwayat dan graf penipuan.",
            "multi_job": "Input berisi lebih dari satu lowongan dan diperiksa sekaligus. Bukti bisa tercampur; hasil ini tidak disimpan ke graf penipuan.",
            "too_short": "Bukti sangat terbatas: teks lowongan terlalu pendek.",
        }.get(intervention_kind or "", "Input diperiksa walau bermasalah."))
    entities["_input_notes"] = notes
    issue = result["issue"]
    if not issue or intervention:
        return None
    logger.info("[verify][%s] PRECHECK stop source=%s issue=%s", request_id, source, issue["id"])
    return VerifyResponse(
        verdict="PERLU_INPUT",
        risk_score=0,
        summary=issue["title"],
        needs_input={"issue": issue, "text": text[:10000], "source": source, "source_url": source_url},
    )


def _attach_input_notes(osint_results: dict, entities: dict) -> None:
    notes = entities.pop("_input_notes", None)
    if notes and isinstance(osint_results, dict):
        osint_results["input_notes"] = notes


async def _read_image(path: str, metrics: dict | None = None) -> tuple[str, str]:
    """OCR dan pembacaan AI vision berjalan bersamaan. OCR tetap sumber bukti kontak."""
    ocr_text, vision_text = await asyncio.gather(
        extract_text_from_image_async(path, metrics),
        read_image_with_vision(path),
    )
    return (ocr_text or "").strip(), (vision_text or "").strip()


def _with_vision(text: str, vision_texts: list[str]) -> str:
    vision = "\n\n".join(t for t in vision_texts if t)
    return f"{text}\n\n{VISION_MARKER}\n{vision}" if vision else text


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _verify_url_stream_generator(url: str, additional_text: str, db_session):
    request_id = _request_id()
    started = time.perf_counter()

    if not (additional_text and additional_text.strip()):
        cached_resp = await asyncio.to_thread(_get_cached_case_by_url, db_session, url)
        if not cached_resp:
            cached_resp = await asyncio.to_thread(_get_cached_case_from_db, db_session, url)
        if cached_resp:
            logger.info("[verify-stream][%s] CACHE_HIT source=url case_id=%s", request_id, cached_resp.case_id)
            yield _sse_event("start", {"request_id": request_id, "message": "Memeriksa riwayat verifikasi..."})
            yield _sse_event("stage", {
                "stage": "ai",
                "status": "done",
                "message": "Ditemukan di riwayat verifikasi (Cache Hit)",
            })
            yield _sse_event("done", {
                "message": "Verifikasi selesai (dari cache)",
                "case_id": cached_resp.case_id,
                "verdict": cached_resp.verdict,
                "risk_score": cached_resp.risk_score,
                "response": cached_resp.model_dump(),
            })
            _log_end(request_id, "url-stream-cache", started, cached_resp)
            return

    yield _sse_event("start", {"request_id": request_id, "message": "Memulai verifikasi..."})

    tmp_paths = []
    carousel_meta = {}
    try:
        yield _sse_event("stage", {"stage": "fetch", "status": "processing", "message": "Mengambil konten dari URL..."})
        caption_text, tmp_paths, carousel_meta = await _fetch_url_content_and_image(url)
        logger.info("[verify-stream][%s] URL fetch done duration=%.2fs", request_id, time.perf_counter() - started)
        if carousel_meta.get("total_images", 0) > carousel_meta.get("processed_images", 0):
            yield _sse_event("stage", {
                "stage": "fetch",
                "status": "processing",
                "message": f"Postingan berisi {carousel_meta['total_images']} gambar; {carousel_meta['processed_images']} gambar pertama dibaca...",
            })

        yield _sse_event("stage", {"stage": "ocr", "status": "processing", "message": "Mengenali teks dari gambar poster..."})
        ocr_texts = []
        vision_texts = []
        for p in tmp_paths:
            if p and os.path.exists(p):
                try:
                    t, v = await _read_image(p)
                    if t:
                        ocr_texts.append(t)
                    if v:
                        vision_texts.append(v)
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

        cached_resp_full = await asyncio.to_thread(_get_cached_case_from_db, db_session, full_raw_text)
        if cached_resp_full:
            logger.info("[verify-stream][%s] CACHE_HIT source=url-content case_id=%s", request_id, cached_resp_full.case_id)
            yield _sse_event("stage", {
                "stage": "ai",
                "status": "done",
                "message": "Konten poster/deskripsi cocok dengan riwayat verifikasi...",
            })
            yield _sse_event("done", {
                "message": "Verifikasi selesai (dari cache)",
                "case_id": cached_resp_full.case_id,
                "verdict": cached_resp_full.verdict,
                "risk_score": cached_resp_full.risk_score,
                "response": cached_resp_full.model_dump(),
            })
            _log_end(request_id, "url-stream-cache", started, cached_resp_full)
            return

        if not full_raw_text or len(full_raw_text) < 15:
            yield _sse_event("error", {"message": "Sistem tidak dapat mengambil konten atau teks dari URL tersebut."})
            return

        yield _sse_event("stage", {"stage": "ner", "status": "processing", "message": "Mengekstrak entitas (perusahaan, kontak, alamat)..."})
        analysis_text = _with_vision(full_raw_text, vision_texts)
        entities = await _extract_entities_hybrid(analysis_text)
        _log_raw_json(request_id, "ENTITIES", entities)
        logger.info("[verify-stream][%s] NER done counts=%s duration=%.2fs", request_id, _entity_counts(entities), time.perf_counter() - started)
        nlp_result = _classify_text_signals(full_raw_text, entities)
        yield _sse_event("stage", {
            "stage": "ner", "status": "done",
            "message": f"Ditemukan {len(entities.get('companies', []))} perusahaan, {len(entities.get('phones', []))} kontak",
            "entities": {k: v for k, v in entities.items() if not k.startswith("_")}
        })
        yield _sse_event("stage", {"stage": "check", "status": "processing", "message": "Memeriksa isi: lowongan atau bukan, berapa lowongan..."})
        stop = _precheck(request_id, analysis_text, entities, source="url", source_url=url)
        if stop:
            yield _sse_event("needs_input", stop.model_dump())
            return
        yield _sse_event("stage", {"stage": "check", "status": "done", "message": "Isi lowongan siap diperiksa"})
        yield _sse_event("stage", {"stage": "osint", "status": "processing", "message": "Menjalankan OSINT probes (WHOIS, peta, media sosial)..."})
        stage_started = time.perf_counter()
        osint_task = asyncio.create_task(_run_osint_on_entities(entities))
        while not osint_task.done():
            done, _ = await asyncio.wait({osint_task}, timeout=3.0)
            if done:
                break
            yield ": keepalive\n\n"
        osint_results = osint_task.result()
        _attach_input_notes(osint_results, entities)
        entities = await _enrich_entities_from_osint(entities, osint_results)
        yield _sse_event("stage", {"stage": "osint", "status": "done", "message": "OSINT selesai"})

        yield _sse_event("stage", {"stage": "graph", "status": "processing", "message": "Memeriksa jaringan fraud..."})
        stage_started = time.perf_counter()
        network_context = await asyncio.to_thread(_check_fraud_network, db_session, entities, full_raw_text)
        _merge_network(osint_results, network_context)
        logger.info("[verify-stream][%s] fraud-network done duration=%.2fs", request_id, time.perf_counter() - stage_started)
        yield _sse_event("stage", {"stage": "graph", "status": "done", "message": "Pemeriksaan jaringan selesai"})

        yield _sse_event("stage", {"stage": "ai", "status": "processing", "message": "AI menganalisis dan menyusun verdict..."})
        stage_started = time.perf_counter()
        llm_task = asyncio.create_task(analyze_with_verifin(
            entities, osint_results, raw_text=analysis_text, text_signals=nlp_result["behavioral_features"]
        ))
        while not llm_task.done():
            done, _ = await asyncio.wait({llm_task}, timeout=3.0)
            if done:
                break
            yield ": keepalive\n\n"
        analysis = llm_task.result()
        _log_raw_json(request_id, "ANALYSIS", analysis)
        logger.info("[verify-stream][%s] LLM done verdict=%s score=%s duration=%.2fs", request_id, analysis.get("verdict"), analysis.get("risk_score"), time.perf_counter() - stage_started)

        if carousel_meta.get("total_images", 0) > carousel_meta.get("processed_images", 0):
            if "recommendations" not in analysis or not isinstance(analysis["recommendations"], list):
                analysis["recommendations"] = []
            analysis["recommendations"].append(
                f"Postingan memuat {carousel_meta['total_images']} gambar (hanya {carousel_meta['processed_images']} slide pertama yang terbaca). Bila kontak atau kualifikasi ada di slide berikutnya, unggah tangkapan layar langsung ke Verifin."
            )

        analysis["network_context"] = network_context
        analysis["nlp_result"] = nlp_result
        if url:
            if "urls" not in entities or not isinstance(entities["urls"], list):
                entities["urls"] = [url]
            elif url not in entities["urls"]:
                entities["urls"].insert(0, url)
        attach_shap_explanation(analysis, entities, osint_results)
        save_status = await asyncio.to_thread(
            _save_case_to_db,
            db_session, full_raw_text, analysis, osint_results, entities=entities, source="url"
        )
        analysis["case_id"] = save_status.get("case_id")
        response = _to_response(analysis, entities, osint_results)
        _log_raw_json(request_id, "RESPONSE", response)
        if response.osint is not None:
            response.osint["persistence_status"] = save_status.get("status")

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
        yield _sse_event("error", {"message": "Verifikasi gagal di tengah jalan. Coba lagi sebentar lagi."})
    finally:
        for p in tmp_paths:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


async def _stream_with_session(url: str, additional_text: str):
    from app.database.postgres_client import SessionLocal
    db = SessionLocal() if SessionLocal else None
    try:
        async for chunk in _verify_url_stream_generator(url, additional_text, db):
            yield chunk
    finally:
        if db is not None:
            db.close()


@router.post(
    "/verify/url/stream",
    dependencies=[Depends(_verify_limit)],
    summary="Verifikasi URL dengan SSE Streaming (real-time progress)",
    description=(
        "Endpoint SSE yang mengirim event real-time per pipeline stage. "
        "Frontend menggunakan EventSource untuk advance loading animation "
        "berdasarkan progress nyata dari backend."
    ),
)
async def verify_url_stream(
    request: UrlVerifyRequest = Body(...),
):
    # Sesi DB dibuka di dalam generator: dependency `get_db` sudah ditutup sebelum
    # StreamingResponse mulai berjalan (FastAPI >= 0.106).
    return StreamingResponse(
        _stream_with_session(request.url, request.additional_text or ""),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
