"""
AI-powered search evidence extraction & ranking.

Mengambil raw search results dari Lightpanda (DuckDuckGo/Google/Bing render),
lalu dikirim ke LLM untuk:
1. Extract data terstruktur (nama, alamat, telepon, Instagram, Facebook, Google Maps, dll)
2. Ranking relevansi tiap hasil terhadap query
3. Klasifikasi jenis evidence (social_media, business_listing, news, scam_report, dll)
4. Dedup cross-source (Instagram + Facebook + Google Maps = satu entity)

Output: structured evidence mirip hasil pencarian manual Google.
"""
from __future__ import annotations

import logging
import json
from typing import Any

from app.services.llm.client import chat_completion, extract_json_from_response

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
Kamu adalah analis OSINT ahli. Tugasmu: ekstrak informasi terstruktur dari hasil pencarian web.

Untuk setiap hasil pencarian yang relevan dengan query, ekstrak:
- title: judul hasil
- url: URL asli
- snippet: ringkasan singkat
- result_type: salah satu dari "social_media" | "business_listing" | "news_article" | "scam_report" | "job_portal" | "official_website" | "review" | "map_listing" | "other"
- platform: platform spesifik (instagram, facebook, google_maps, twitter, tiktok, website, lokerjogja, dll)
- extracted_data: objek berisi data yang ditemukan:
    - name: nama bisnis/orang
    - address: alamat
    - phone: nomor telepon
    - email: email
    - social_links: array URL social media
    - website: URL website resmi
    - followers: jumlah pengikut (jika ada)
    - rating: rating ulasan (jika ada)
    - reviews_count: jumlah ulasan (jika ada)
    - business_category: kategori bisnis
    - extra_notes: catatan tambahan
- relevance_score: 0-100, seberapa relevan hasil ini dengan query
- is_scam_indicator: boolean, apakah hasil ini mengindikasikan penipuan/scam
- is_verification: boolean, apakah hasil ini memverifikasi keabsahan bisnis

Filter: HANYA sertakan hasil dengan relevance_score >= 30.
Dedup: Jika multiple hasil merujuk ke entity yang sama, gabungkan datanya.
Sort: Urutkan dari relevance_score tertinggi."""

def _build_user_prompt(query: str, results: list[dict[str, Any]]) -> str:
    """Build prompt dari search results."""
    lines = [f"Query pencarian: {query}", "", "Hasil pencarian mentah:"]
    for i, r in enumerate(results, 1):
        lines.append(f"--- Hasil {i} ---")
        lines.append(f"Title: {r.get('title', '')}")
        lines.append(f"URL: {r.get('url', '')}")
        lines.append(f"Snippet: {r.get('snippet', '')}")
        lines.append("")
    lines.append("Ekstrak dan rangking hasil di atas. Output JSON dengan format:")
    lines.append("""{
  "query": "<query asli>",
  "extracted_count": <jumlah hasil relevan>,
  "results": [
    {
      "title": "...",
      "url": "...",
      "snippet": "...",
      "result_type": "...",
      "platform": "...",
      "extracted_data": {
        "name": "...",
        "address": "...",
        "phone": "...",
        "email": "...",
        "social_links": [],
        "website": "...",
        "followers": "...",
        "rating": null,
        "reviews_count": null,
        "business_category": "...",
        "extra_notes": "..."
      },
      "relevance_score": 0,
      "is_scam_indicator": false,
      "is_verification": false
    }
  ],
  "summary": "Ringkasan singkat temuan utama",
  "entities_found": ["nama entitas/bisnis yang ditemukan"],
  "has_strong_verification": false,
  "has_scam_indicators": false
}""")
    return "\n".join(lines)


async def ai_extract_and_rank(
    query: str,
    raw_results: list[dict[str, Any]],
    *,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """
    Kirim raw search results ke LLM untuk extraction + ranking.

    Returns structured evidence dengan format:
    {
        "ok": bool,
        "query": str,
        "results": [...],  # ranked & extracted
        "summary": str,
        "entities_found": list[str],
        "has_strong_verification": bool,
        "has_scam_indicators": bool,
        "error": str | None,
    }
    """
    if not raw_results:
        return {
            "ok": False,
            "query": query,
            "results": [],
            "summary": "",
            "entities_found": [],
            "has_strong_verification": False,
            "has_scam_indicators": False,
            "error": "Tidak ada raw results untuk diproses.",
        }

    user_prompt = _build_user_prompt(query, raw_results)

    try:
        raw_response = await chat_completion(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=max_tokens,
        )

        parsed = extract_json_from_response(raw_response)

        results = parsed.get("results", [])
        # Pastikan relevance_score adalah int dan sort descending
        for r in results:
            try:
                r["relevance_score"] = int(r.get("relevance_score", 0))
            except (ValueError, TypeError):
                r["relevance_score"] = 0
        results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

        return {
            "ok": True,
            "query": query,
            "results": results,
            "summary": parsed.get("summary", ""),
            "entities_found": parsed.get("entities_found", []),
            "has_strong_verification": parsed.get("has_strong_verification", False),
            "has_scam_indicators": parsed.get("has_scam_indicators", False),
            "raw_count": len(raw_results),
            "extracted_count": len(results),
            "error": None,
        }

    except Exception as exc:
        logger.error("[AI Extract] gagal: %s", exc)
        return {
            "ok": False,
            "query": query,
            "results": [],
            "summary": "",
            "entities_found": [],
            "has_strong_verification": False,
            "has_scam_indicators": False,
            "error": str(exc),
        }


async def ai_extract_from_page(
    url: str,
    page_content: str,
    query: str,
    *,
    max_tokens: int = 4096,
) -> dict[str, Any]:
    """
    Extract structured data dari konten halaman yang sudah di-render Lightpanda.

    Berguna untuk halaman Instagram, Facebook, Google Maps, dll yang
    kontennya heavy JS dan perlu parsing cerdas.
    """
    # Truncate content terlalu panjang
    max_content = 8000
    truncated = page_content[:max_content]
    if len(page_content) > max_content:
        truncated += "\n... [konten dipotong]"

    system_prompt = """\
Kamu adalah extractor data terstruktur dari halaman web yang sudah di-render.
Ekstrak informasi bisnis/personal dari konten halaman.

Output JSON:
{
  "url": "<url>",
  "page_type": "instagram_profile | facebook_page | google_maps | website | job_portal | other",
  "extracted_data": {
    "name": "...",
    "address": "...",
    "phone": "...",
    "email": "...",
    "social_links": [],
    "website": "...",
    "followers": "...",
    "rating": null,
    "reviews_count": null,
    "business_category": "...",
    "description": "...",
    "extra_notes": "..."
  },
  "is_business_verified": false,
  "confidence_score": 0
}"""

    user_prompt = f"""URL: {url}
Query konteks: {query}

Konten halaman (HTML/Markdown yang sudah di-render):
---
{truncated}
---

Ekstrak semua data terstruktur yang tersedia."""

    try:
        raw_response = await chat_completion(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=max_tokens,
        )

        parsed = extract_json_from_response(raw_response)
        return {
            "ok": True,
            "url": url,
            "page_type": parsed.get("page_type", "other"),
            "extracted_data": parsed.get("extracted_data", {}),
            "is_business_verified": parsed.get("is_business_verified", False),
            "confidence_score": parsed.get("confidence_score", 0),
            "error": None,
        }
    except Exception as exc:
        logger.error("[AI Page Extract] gagal untuk %s: %s", url, exc)
        return {
            "ok": False,
            "url": url,
            "page_type": "other",
            "extracted_data": {},
            "is_business_verified": False,
            "confidence_score": 0,
            "error": str(exc),
        }


def merge_extracted_evidence(
    search_extraction: dict[str, Any],
    page_extractions: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Gabungkan hasil AI extraction dari search results + individual page fetches.

    Dedup berdasarkan URL dan nama entitas.
    """
    merged_results: list[dict[str, Any]] = list(search_extraction.get("results", []))

    # Index by URL untuk dedup
    url_index: dict[str, int] = {}
    for i, r in enumerate(merged_results):
        url = (r.get("url") or "").lower().rstrip("/")
        if url:
            url_index[url] = i

    for pe in page_extractions:
        if not pe.get("ok"):
            continue
        url = pe.get("url", "").lower().rstrip("/")
        page_data = pe.get("extracted_data", {})

        if url in url_index:
            # Merge ke result yang sudah ada
            idx = url_index[url]
            existing = merged_results[idx].get("extracted_data", {})
            # Fill missing fields
            for key, val in page_data.items():
                if not existing.get(key) and val:
                    existing[key] = val
            merged_results[idx]["extracted_data"] = existing
            # Update page_type
            if pe.get("page_type") and pe["page_type"] != "other":
                merged_results[idx]["result_type"] = pe["page_type"]
        else:
            # Tambah sebagai result baru
            merged_results.append({
                "title": page_data.get("name", ""),
                "url": pe.get("url", ""),
                "snippet": page_data.get("description", ""),
                "result_type": pe.get("page_type", "other"),
                "platform": pe.get("page_type", "other").split("_")[0],
                "extracted_data": page_data,
                "relevance_score": pe.get("confidence_score", 50),
                "is_scam_indicator": False,
                "is_verification": pe.get("is_business_verified", False),
            })

    # Sort by relevance
    merged_results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    return {
        "ok": True,
        "query": search_extraction.get("query", ""),
        "results": merged_results,
        "summary": search_extraction.get("summary", ""),
        "entities_found": search_extraction.get("entities_found", []),
        "has_strong_verification": search_extraction.get("has_strong_verification", False),
        "has_scam_indicators": search_extraction.get("has_scam_indicators", False),
        "total_results": len(merged_results),
    }
