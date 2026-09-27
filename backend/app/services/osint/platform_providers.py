from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from app.services.osint.ai_extractor import ai_extract_and_rank, merge_extracted_evidence
from app.services.osint.search_intelligence import intelligent_search

logger = logging.getLogger(__name__)

def _run_ai_extract_sync(query: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(ai_extract_and_rank(query, results))
        finally:
            loop.close()
    except RuntimeError:
        return asyncio.run(ai_extract_and_rank(query, results))

def collect_all_platform_evidence(
    business_name: str,
    location: str = "",
    *,
    search_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    query = f"{business_name} {location}".strip()
    if search_results is not None:
        general_results = search_results
    else:
        si_result = intelligent_search(business_name, location, max_results=10)
        general_results = si_result.get("results", [])

    maps_results = [r for r in general_results if "maps.google" in (r.get("url") or "").lower() or "google.com/maps" in (r.get("url") or "").lower()]
    ig_results = [r for r in general_results if "instagram.com" in (r.get("url") or "").lower()]
    fb_results = [r for r in general_results if "facebook.com" in (r.get("url") or "").lower()]
    tiktok_results = [r for r in general_results if "tiktok.com" in (r.get("url") or "").lower()]
    twitter_results = [r for r in general_results if "twitter.com" in (r.get("url") or "").lower() or re.search(r"(?:^|[\/\.])x\.com(?:\/|$)", (r.get("url") or "").lower())]
    loker_results = [r for r in general_results if any(p in (r.get("url") or "").lower() for p in ("lokerjogja", "loker.id", "karir", "jobstreet", "glints"))]
    other_results = [r for r in general_results if r not in maps_results + ig_results + fb_results + tiktok_results + twitter_results + loker_results]

    if not general_results:
        from app.services.osint.searxng_client import searxng_search
        maps_search = searxng_search(f"{business_name} {location} Google Maps", max_results=5)
        if maps_search.get("ok") and maps_search.get("results"):
            maps_results = [r for r in maps_search["results"] if "maps.google" in (r.get("url") or "").lower() or "google.com/maps" in (r.get("url") or "").lower()]
        ig_search = searxng_search(f"{business_name} Instagram", max_results=5)
        if ig_search.get("ok") and ig_search.get("results"):
            ig_results = [r for r in ig_search["results"] if "instagram.com" in (r.get("url") or "").lower()]

    search_extraction = _run_ai_extract_sync(query, general_results)
    merged = merge_extracted_evidence(search_extraction, [])

    platforms = {
        "google_maps": {
            "count": len(maps_results),
            "results": maps_results,
        },
        "instagram": {
            "count": len(ig_results),
            "results": ig_results,
        },
        "facebook": {
            "count": len(fb_results),
            "results": fb_results,
        },
        "tiktok": {
            "count": len(tiktok_results),
            "results": tiktok_results,
        },
        "twitter": {
            "count": len(twitter_results),
            "results": twitter_results,
        },
        "job_portal": {
            "count": len(loker_results),
            "results": loker_results,
        },
        "web_search": {
            "count": len(other_results),
            "results": other_results,
        },
    }

    return {
        "ok": True,
        "query": query,
        "platforms": platforms,
        "merged_evidence": merged,
        "verification_summary": merged.get("summary", ""),
        "entities_found": merged.get("entities_found", []),
        "has_strong_verification": merged.get("has_strong_verification", False),
        "has_scam_indicators": merged.get("has_scam_indicators", False),
        "total_raw_results": len(general_results),
        "total_extracted": merged.get("total_results", 0),
    }
