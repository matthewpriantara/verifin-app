from __future__ import annotations

import asyncio
import logging
import re
from typing import Any
from urllib.parse import quote_plus, urlparse

from app.services.osint.lightpanda_client import lightpanda_fetch, lightpanda_search
from app.services.osint.ai_extractor import ai_extract_and_rank, ai_extract_from_page, merge_extracted_evidence
from app.services.osint.search_intelligence import intelligent_search

logger = logging.getLogger(__name__)

_MAPS_PATTERNS = [r"maps\.google\.com", r"google\.com/maps", r"maps\.app\.goo\.gl"]
_IG_PATTERNS = [r"instagram\.com", r"instagr\.am"]
_FB_PATTERNS = [r"facebook\.com", r"fb\.com", r"m\.facebook\.com"]
_TIKTOK_PATTERNS = [r"tiktok\.com"]
_TWITTER_PATTERNS = [r"(?:twitter|x)\.com"]
_LOKER_PATTERNS = [r"lokerjogja\.id", r"loker\.id", r"karir", r"jobstreet", r"glints"]


def _matches_platforms(url: str, patterns: list[str]) -> bool:
    url_lower = (url or "").lower()
    return any(re.search(p, url_lower) for p in patterns)


def _filter_by_platform(results: list[dict[str, Any]], patterns: list[str]) -> list[dict[str, Any]]:
    return [r for r in results if _matches_platforms(r.get("url", ""), patterns)]


def _search_platform_evidence(
    query: str,
    *,
    platform_suffix: str = "",
    max_results: int = 10,
    search_engine: str = "google",
) -> list[dict[str, Any]]:
    full_query = f"{query} {platform_suffix}".strip() if platform_suffix else query
    result = lightpanda_search(full_query, max_results=max_results, engine=search_engine)
    if not result.get("ok"):
        result = lightpanda_search(full_query, max_results=max_results, engine="duckduckgo")
    return result.get("results", [])


def collect_google_maps_evidence(
    business_name: str,
    location: str = "",
) -> dict[str, Any]:
    query = f"{business_name} {location}".strip()

    results = _search_platform_evidence(
        query,
        platform_suffix="site:maps.google.com OR site:google.com/maps",
        max_results=5,
        search_engine="google",
    )

    if not results:
        all_results = _search_platform_evidence(query, max_results=10, search_engine="google")
        results = _filter_by_platform(all_results, _MAPS_PATTERNS)

    if not results:
        all_results = _search_platform_evidence(query, max_results=10, search_engine="duckduckgo")
        results = _filter_by_platform(all_results, _MAPS_PATTERNS)

    if not results:
        return {
            "ok": False,
            "platform": "google_maps",
            "query": query,
            "results": [],
            "error": "Tidak ada hasil Google Maps ditemukan.",
        }

    page_extractions: list[dict[str, Any]] = []
    for r in results[:3]:
        url = r.get("url", "")
        if not url:
            continue
        fetch_result = lightpanda_fetch(url, output="markdown", wait_ms=4000)
        if fetch_result.get("ok") and fetch_result.get("content"):
            page_extractions.append(
                ai_extract_from_page_sync(url, fetch_result["content"], query)
            )

    search_extraction = _run_ai_extract_sync(query, results)

    merged = merge_extracted_evidence(search_extraction, page_extractions)

    return {
        "ok": True,
        "platform": "google_maps",
        "query": query,
        "results": merged.get("results", []),
        "summary": merged.get("summary", ""),
        "total_found": merged.get("total_results", 0),
        "error": None,
    }


def collect_instagram_evidence(
    business_name: str,
    location: str = "",
) -> dict[str, Any]:
    query = f"{business_name} {location}".strip()

    results = _search_platform_evidence(
        query,
        platform_suffix='site:instagram.com OR "instagram.com"',
        max_results=5,
        search_engine="google",
    )

    if not results:
        all_results = _search_platform_evidence(query, max_results=10, search_engine="google")
        results = _filter_by_platform(all_results, _IG_PATTERNS)

    if not results:
        all_results = _search_platform_evidence(query, max_results=10, search_engine="duckduckgo")
        results = _filter_by_platform(all_results, _IG_PATTERNS)

    if not results:
        return {
            "ok": False,
            "platform": "instagram",
            "query": query,
            "results": [],
            "error": "Tidak ada hasil Instagram ditemukan.",
        }

    page_extractions: list[dict[str, Any]] = []
    for r in results[:3]:
        url = r.get("url", "")
        if not url:
            continue
        if "/p/" in url or "/reel/" in url or "/explore/" in url:
            continue
        fetch_result = lightpanda_fetch(url, output="markdown", wait_ms=4000)
        if fetch_result.get("ok") and fetch_result.get("content"):
            page_extractions.append(
                ai_extract_from_page_sync(url, fetch_result["content"], query)
            )

    search_extraction = _run_ai_extract_sync(query, results)
    merged = merge_extracted_evidence(search_extraction, page_extractions)

    return {
        "ok": True,
        "platform": "instagram",
        "query": query,
        "results": merged.get("results", []),
        "summary": merged.get("summary", ""),
        "total_found": merged.get("total_results", 0),
        "error": None,
    }


def collect_facebook_evidence(
    business_name: str,
    location: str = "",
) -> dict[str, Any]:
    query = f"{business_name} {location}".strip()

    results = _search_platform_evidence(
        query,
        platform_suffix='site:facebook.com OR "facebook.com"',
        max_results=5,
        search_engine="google",
    )

    if not results:
        all_results = _search_platform_evidence(query, max_results=10, search_engine="google")
        results = _filter_by_platform(all_results, _FB_PATTERNS)

    if not results:
        all_results = _search_platform_evidence(query, max_results=10, search_engine="duckduckgo")
        results = _filter_by_platform(all_results, _FB_PATTERNS)

    if not results:
        return {
            "ok": False,
            "platform": "facebook",
            "query": query,
            "results": [],
            "error": "Tidak ada hasil Facebook ditemukan.",
        }

    page_extractions: list[dict[str, Any]] = []
    for r in results[:3]:
        url = r.get("url", "")
        if not url:
            continue
        fetch_result = lightpanda_fetch(url, output="markdown", wait_ms=4000)
        if fetch_result.get("ok") and fetch_result.get("content"):
            page_extractions.append(
                ai_extract_from_page_sync(url, fetch_result["content"], query)
            )

    search_extraction = _run_ai_extract_sync(query, results)
    merged = merge_extracted_evidence(search_extraction, page_extractions)

    return {
        "ok": True,
        "platform": "facebook",
        "query": query,
        "results": merged.get("results", []),
        "summary": merged.get("summary", ""),
        "total_found": merged.get("total_results", 0),
        "error": None,
    }


def collect_all_platform_evidence(
    business_name: str,
    location: str = "",
) -> dict[str, Any]:
    query = f"{business_name} {location}".strip()
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

def _run_ai_extract_sync(query: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(ai_extract_and_rank(query, results))
        finally:
            loop.close()
    except RuntimeError:
        return asyncio.run(ai_extract_and_rank(query, results))


def ai_extract_from_page_sync(url: str, content: str, query: str) -> dict[str, Any]:
    try:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(ai_extract_from_page(url, content, query))
        finally:
            loop.close()
    except RuntimeError:
        return asyncio.run(ai_extract_from_page(url, content, query))


async def run_platform_evidence(
    business_name: str,
    location: str = "",
) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, collect_all_platform_evidence, business_name, location
    )
