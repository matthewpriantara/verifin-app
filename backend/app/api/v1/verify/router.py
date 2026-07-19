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
    UrlVerifyRequest,
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
    """
    OSINT live paralel: WHOIS/DNS + OSM + Kredibel + Scrapling web + Threads.
    Optimasi latency: asyncio.gather (bukan serial await).
    """
    import asyncio
    from app.services.llm.prompt_builder import FREE_EMAIL_DOMAINS

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
        "timing": {},
    }

    emails = entities.get("emails", []) or []
    addresses = (entities.get("addresses") or [])[:2]
    companies = entities.get("companies") or []
    company_name = companies[0] if companies else None

    # Domain: skip WHOIS/DNS untuk Gmail/Yahoo (netral + buang waktu)
    def _domain_job() -> tuple[dict, dict]:
        if not emails:
            return osint_results["domain"], osint_results["email_security"]
        domain = emails[0].split("@")[-1].lower() if "@" in emails[0] else ""
        if not domain:
            return osint_results["domain"], osint_results["email_security"]
        if domain in FREE_EMAIL_DOMAINS:
            return (
                {
                    "age_years": None,
                    "created_at": "N/A (free email)",
                    "is_new": False,
                    "domain": domain,
                    "skipped": "free_email",
                },
                {"spf_active": False, "dmarc_active": False, "skipped": "free_email"},
            )
        try:
            age_info = check_domain_age(domain)
            if "age_years" not in age_info and age_info.get("age_days", -1) > 0:
                age_info["age_years"] = round(age_info["age_days"] / 365, 2)
            security_info = check_email_security(domain)
            return age_info, security_info
        except Exception as exc:
            return (
                {
                    "error": str(exc),
                    "is_new": True,
                    "age_years": None,
                    "created_at": "Unknown",
                },
                {"spf_active": False, "dmarc_active": False},
            )

    async def _addresses_job() -> list:
        if not addresses:
            return []

        async def one(addr: str):
            try:
                return await validate_address_and_business(addr, company_name)
            except Exception:
                return {
                    "address_input": addr,
                    "address_found": False,
                    "error": "Gagal memvalidasi alamat.",
                }

        return list(await asyncio.gather(*[one(a) for a in addresses]))

    async def _phones_job() -> list:
        try:
            return await check_phones_kredibel(entities.get("contacts") or [], limit=1)
        except Exception as exc:
            return [
                {"source": "kredibel", "found": False, "error": str(exc), "risk_flags": []}
            ]

    async def _web_job() -> dict:
        try:
            return await run_web_evidence(entities)
        except Exception as exc:
            return {
                "enabled": True,
                "websites": [],
                "searches": [],
                "risk_flags": [],
                "safe_flags": [],
                "error": str(exc),
            }

    async def _companies_job() -> list:
        try:
            return await validate_companies(entities, limit=1)
        except Exception as exc:
            return [
                {
                    "checked": False,
                    "error": str(exc),
                    "registry": {"pt_registry_verified": False},
                    "risk_flags": [],
                    "safe_flags": [],
                    "evidence": [],
                }
            ]

    async def _threads_job() -> dict:
        try:
            return await run_threads_osint(entities)
        except Exception as exc:
            return {
                "enabled": True,
                "found": False,
                "posts": [],
                "profiles": [],
                "risk_flags": [],
                "error": str(exc),
            }

    loop = asyncio.get_event_loop()
    t0 = loop.time()
    (
        domain_pair,
        addr_list,
        phones,
        web,
        companies_osint,
        threads,
    ) = await asyncio.gather(
        loop.run_in_executor(None, _domain_job),
        _addresses_job(),
        _phones_job(),
        _web_job(),
        _companies_job(),
        _threads_job(),
    )
    osint_results["timing"]["osint_parallel_sec"] = round(loop.time() - t0, 3)

    osint_results["domain"], osint_results["email_security"] = domain_pair
    osint_results["address_validations"] = addr_list
    osint_results["phones"] = phones
    osint_results["web"] = web
    osint_results["companies"] = companies_osint
    osint_results["threads"] = threads
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


def _get_cached_case_from_db(db: Session, raw_input_str: str) -> VerifyResponse | None:
    """Cek apakah lowongan/URL/gambar ini sudah pernah diuji coba sebelumnya (exact DB cache hit)."""
    import hashlib
    if not raw_input_str or not raw_input_str.strip():
        return None
    try:
        text_hash = hashlib.sha256(raw_input_str.strip().encode("utf-8")).hexdigest()
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
            print(f"[DB Cache Hit] Mengembalikan hasil dari database untuk hash: {text_hash[:10]}")
            return _to_response(analysis, ent, osint)
    except Exception as e:
        print(f"[DB Cache Lookup Warning] {e}")
    return None


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


def _sync_scrapling_fetch(url: str) -> tuple[str, list[str]]:
    import re
    import httpx
    from bs4 import BeautifulSoup

    combined_caption_text = ""
    image_urls = []

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    # Penanganan Khusus Instagram (post / reel / tv)
    ig_match = re.search(r"instagram\.com/(?:p|reel|tv)/([^/?#&]+)", url, re.I)
    if ig_match:
        shortcode = ig_match.group(1)
        # 1. Coba Halaman Embed Instagram (Sangat efektif mengekstrak poster & caption publik tanpa login)
        embed_url = f"https://www.instagram.com/p/{shortcode}/embed/captioned/"
        try:
            res = httpx.get(embed_url, headers=headers, follow_redirects=True, verify=False, timeout=12.0)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                caption_el = soup.find("div", class_="Caption") or soup.find("div", class_="CaptionComments")
                if caption_el:
                    combined_caption_text = caption_el.get_text(separator="\n", strip=True)

                img_els = soup.find_all("img", class_="EmbeddedMediaImage") or soup.find_all("img")
                for img in img_els:
                    src = img.get("src")
                    if src and ("scontent" in src or "cdninstagram.com" in src):
                        image_urls.append(src)

                # Ekstrak URL scontent CDN dari script/raw text HTML embed
                found_scontent = re.findall(r'https://scontent[^"\'\s\\]+', res.text)
                for s_url in found_scontent:
                    clean = s_url.replace("\\u0026", "&").replace("\\/", "/")
                    image_urls.append(clean)
        except Exception as exc:
            print(f"[Instagram Embed Fetch Warning] {exc}")

        # 2. Jika belum dapat gambar, coba oEmbed API
        if not image_urls:
            try:
                oembed_url = f"https://www.instagram.com/api/v1/oembed/?url={url}"
                o_res = httpx.get(oembed_url, headers=headers, follow_redirects=True, verify=False, timeout=8.0)
                if o_res.status_code == 200:
                    data = o_res.json()
                    if data.get("title") and not combined_caption_text:
                        combined_caption_text = data.get("title")
                    if data.get("thumbnail_url"):
                        image_urls.append(data.get("thumbnail_url"))
            except Exception as exc:
                print(f"[Instagram oEmbed Warning] {exc}")

        # 3. Jika gambar belum dapat, coba proxy fixer (vxinstagram / ddinstagram)
        if not image_urls:
            for domain in ["vxinstagram.com", "ddinstagram.com"]:
                try:
                    fix_url = f"https://{domain}/p/{shortcode}/"
                    f_res = httpx.get(fix_url, headers={"User-Agent": "facebookexternalhit/1.1"}, follow_redirects=True, verify=False, timeout=8.0)
                    if f_res.status_code == 200:
                        f_soup = BeautifulSoup(f_res.text, "html.parser")
                        og_i = f_soup.find("meta", property="og:image") or f_soup.find("meta", attrs={"name": "twitter:image"})
                        if og_i and og_i.get("content"):
                            image_urls.append(og_i["content"])
                        og_d = f_soup.find("meta", property="og:description") or f_soup.find("meta", attrs={"name": "description"})
                        if og_d and og_d.get("content") and not combined_caption_text:
                            combined_caption_text = og_d["content"]
                        if image_urls:
                            break
                except Exception:
                    pass

    # Generic Scrapling/HTTPX fetcher (untuk website non-IG atau fallback)
    try:
        from scrapling.fetchers import Fetcher
        page = Fetcher.get(url, headers=headers, verify=False)
        text_parts = []
        if combined_caption_text:
            text_parts.append(combined_caption_text)

        og_title = page.css("meta[property='og:title']::attr(content)").get() or page.css("title::text").get()
        if og_title and og_title.strip() and og_title.strip() not in text_parts:
            text_parts.append(og_title.strip())

        company_meta = (
            page.css("span[data-automation='advertiser-name']::text").get()
            or page.css("span[data-automation*='company']::text").get()
            or page.css("a[data-automation*='company']::text").get()
        )
        if company_meta and company_meta.strip():
            text_parts.append(f"Perusahaan/Pengiklan: {company_meta.strip()}")

        og_desc = (
            page.css("meta[property='og:description']::attr(content)").get() 
            or page.css("meta[name='description']::attr(content)").get()
        )
        if og_desc and og_desc.strip() and og_desc.strip() not in text_parts:
            text_parts.append(og_desc.strip())

        body_texts = [
            t.strip()
            for t in page.css(
                "p::text, h1::text, h2::text, h3::text, li::text, article::text, "
                "div[data-automation*='job']::text, div[class*='description']::text, "
                "div[class*='job']::text, span[dir='auto']::text, span[data-automation*='advertiser']::text"
            ).getall()
            if len(t.strip()) > 15
        ]
        if body_texts:
            seen_b = set()
            unique_body = []
            for b in body_texts:
                if b not in seen_b and not any(x in b.lower() for x in ["cookie", "privacy policy", "terms of service", "log in", "sign up"]):
                    seen_b.add(b)
                    unique_body.append(b)
            text_parts.append(" ".join(unique_body[:30])[:3000])

        combined_caption_text = "\n".join(text_parts).strip()

        og_img = (
            page.css("meta[property='og:image']::attr(content)").get()
            or page.css("meta[name='twitter:image']::attr(content)").get()
        )
        if og_img and og_img.strip():
            image_urls.append(og_img.strip())

    except Exception as exc:
        print(f"[Scrapling Fetch Warning] {exc}")

    if not combined_caption_text:
        try:
            res = httpx.get(url, headers=headers, follow_redirects=True, verify=False, timeout=15.0)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                text_parts = []
                og_title = soup.find("meta", property="og:title") or soup.find("title")
                if og_title:
                    text_parts.append(og_title.get("content") or og_title.get_text())
                og_desc = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
                if og_desc and og_desc.get("content"):
                    text_parts.append(og_desc["content"].strip())
                combined_caption_text = "\n".join(text_parts).strip()
                if not image_urls:
                    og_img = soup.find("meta", property="og:image") or soup.find("meta", attrs={"name": "twitter:image"})
                    if og_img and og_img.get("content"):
                        image_urls.append(og_img["content"].strip())
        except Exception as exc:
            print(f"[HTTPX Scrape Fallback Error] {exc}")

    # Deduplicate preserving order
    seen_urls = set()
    dedup_images = []
    for img_u in image_urls:
        if img_u and img_u not in seen_urls:
            seen_urls.add(img_u)
            dedup_images.append(img_u)

    return combined_caption_text, dedup_images[:3]


async def _fetch_url_content_and_image(url: str) -> tuple[str, list[str]]:
    """
    Scrape teks (caption/description) & daftar image URL poster (termasuk carousel slides) dari URL.
    Returns: (extracted_text, temp_image_paths_list)
    """
    import asyncio
    import httpx

    loop = asyncio.get_event_loop()
    combined_caption_text, image_urls = await loop.run_in_executor(None, _sync_scrapling_fetch, url)

    tmp_img_paths = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.instagram.com/",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    }

    for img_url in image_urls:
        try:
            async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True, verify=False) as client:
                img_res = await client.get(img_url)
                if img_res.status_code == 200 and len(img_res.content) > 1000:
                    ext = ".jpg"
                    if ".png" in img_url.lower():
                        ext = ".png"
                    elif ".webp" in img_url.lower():
                        ext = ".webp"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                        tmp.write(img_res.content)
                        tmp_img_paths.append(tmp.name)
        except Exception as exc:
            print(f"[URL Fetch] Gagal mengunduh gambar poster dari {img_url}: {exc}")

    return combined_caption_text, tmp_img_paths


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
                    print(f"[URL OCR Error] {exc}")

        combined_ocr_text = "\n".join(ocr_texts).strip()

        # FOKUS UTAMA: Jika ada teks dari poster/gambar hasil OCR, letakkan DI POSISI PALING ATAS!
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

        entities = extract_entities_from_text(full_raw_text)
        osint_results = await _run_osint_on_entities(entities)
        analysis = await analyze_with_verifin(
            entities, osint_results, raw_text=full_raw_text
        )
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

