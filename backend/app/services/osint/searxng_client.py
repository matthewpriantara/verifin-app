from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any
from urllib.parse import quote_plus

import httpx

from app.config import SEARXNG_URL

logger = logging.getLogger(__name__)

_SEARXNG_BASE = SEARXNG_URL or "http://localhost:8888"
_SEARXNG_TIMEOUT = 15
_QUERY_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SECONDS = 600
_CACHE_MAX_ENTRIES = 512
_REQUEST_LOCK = threading.Lock()
_LAST_REQUEST_TIME: float = 0.0
_MIN_REQUEST_INTERVAL: float = 0.8
_RATE_LIMIT_UNTIL: float = 0.0
_AVAILABILITY_CACHE: tuple[float, bool] = (0.0, False)
_AVAILABILITY_TTL: float = 30.0


def _cache_key(query: str, max_results: int, engines: str | None, language: str) -> str:
    return f"{query.strip().lower()}|{max_results}|{engines or ''}|{language}"


def _cache_get(key: str) -> dict[str, Any] | None:
    with _CACHE_LOCK:
        entry = _QUERY_CACHE.get(key)
        if not entry:
            return None
        ts, value = entry
        if time.monotonic() - ts > _CACHE_TTL_SECONDS:
            _QUERY_CACHE.pop(key, None)
            return None
        return value


def _cache_set(key: str, value: dict[str, Any]) -> None:
    with _CACHE_LOCK:
        if len(_QUERY_CACHE) >= _CACHE_MAX_ENTRIES:
            # Evict entri terlama
            oldest = min(_QUERY_CACHE.items(), key=lambda kv: kv[1][0])[0]
            _QUERY_CACHE.pop(oldest, None)
        _QUERY_CACHE[key] = (time.monotonic(), value)


def is_searxng_available() -> bool:
    global _AVAILABILITY_CACHE
    now = time.monotonic()
    last_check, is_avail = _AVAILABILITY_CACHE
    if now - last_check < _AVAILABILITY_TTL:
        return is_avail

    available = False
    try:
        resp = httpx.get(f"{_SEARXNG_BASE}/healthz", timeout=3)
        available = resp.status_code == 200
    except Exception:
        try:
            resp = httpx.get(
                f"{_SEARXNG_BASE}/search",
                params={"q": "test", "format": "json"},
                timeout=4,
            )
            available = resp.status_code == 200
        except Exception:
            available = False

    _AVAILABILITY_CACHE = (now, available)
    return available

def searxng_search(
    query: str,
    *,
    max_results: int = 10,
    engines: str | None = None,
    language: str = "id",
) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {
            "ok": False, "query": q, "engine": "searxng", "results": [],
            "raw_result_count": 0, "engine_stats": {},
            "unresponsive_engines": [], "error": "Query kosong.",
        }

    global _LAST_REQUEST_TIME, _RATE_LIMIT_UNTIL

    cache_key = _cache_key(q, max_results, engines, language)
    cached = _cache_get(cache_key)
    if cached is not None:
        logger.debug("[SearXNG] cache hit untuk query: %s", q[:60])
        return {**cached, "cached": True}

    now = time.monotonic()
    if now < _RATE_LIMIT_UNTIL:
        remain = round(_RATE_LIMIT_UNTIL - now, 1)
        logger.warning("[SearXNG Cooldown] Melewati query '%s' karena masih cooldown rate-limit (%ss tersisa)", q[:40], remain)
        return {
            "ok": False, "query": q, "engine": "searxng", "results": [],
            "raw_result_count": 0, "engine_stats": {},
            "unresponsive_engines": [], "error": f"Rate limited. Cooldown {remain}s.",
        }

    params: dict[str, str] = {
        "q": q,
        "format": "json",
        "language": language,
    }
    if engines:
        params["engines"] = engines

    try:
        with _REQUEST_LOCK:
            cached_after_lock = _cache_get(cache_key)
            if cached_after_lock is not None:
                logger.debug("[SearXNG] in-flight cache hit untuk query: %s", q[:60])
                return {**cached_after_lock, "cached": True}

            now = time.monotonic()
            elapsed = now - _LAST_REQUEST_TIME
            if elapsed < _MIN_REQUEST_INTERVAL:
                time.sleep(_MIN_REQUEST_INTERVAL - elapsed)

            with httpx.Client(timeout=_SEARXNG_TIMEOUT) as client:
                resp = client.get(f"{_SEARXNG_BASE}/search", params=params)
                _LAST_REQUEST_TIME = time.monotonic()

                if resp.status_code == 429:
                    _RATE_LIMIT_UNTIL = time.monotonic() + 30.0
                    logger.warning("[SearXNG] Rate limited (429). Cooldown aktif 30 detik.")
                    return {
                        "ok": False, "query": q, "engine": "searxng", "results": [],
                        "raw_result_count": 0, "engine_stats": {},
                        "unresponsive_engines": [], "error": "Rate limited.",
                    }
                if resp.status_code != 200:
                    return {
                        "ok": False, "query": q, "engine": "searxng", "results": [],
                        "raw_result_count": 0, "engine_stats": {},
                        "unresponsive_engines": [],
                        "error": f"HTTP {resp.status_code}",
                    }

            data = resp.json()
            raw_results = data.get("results", [])
            unresponsive = data.get("unresponsive_engines", [])
            results: list[dict[str, Any]] = []
            engine_stats: dict[str, int] = {}
            for r in raw_results:
                url = r.get("url", "")
                title = r.get("title", "")
                content = r.get("content", "")
                if not url or not title:
                    continue

                engines_found = r.get("engines", [r.get("engine", "")])
                for eng in engines_found:
                    if eng:
                        engine_stats[eng] = engine_stats.get(eng, 0) + 1

                results.append({
                    "title": title[:200],
                    "url": url,
                    "snippet": content[:300],
                    "engines": engines_found,
                    "score": r.get("score", 0),
                    "category": r.get("category", "general"),
                    "published_date": r.get("publishedDate"),
                })

            results.sort(key=lambda x: x.get("score", 0), reverse=True)

            response = {
                "ok": bool(results),
                "query": q,
                "engine": "searxng",
                "results": results[:max_results],
                "raw_result_count": len(raw_results),
                "engine_stats": engine_stats,
                "unresponsive_engines": [
                    {"name": e[0], "reason": e[1]}
                    for e in unresponsive if isinstance(e, (list, tuple)) and len(e) >= 2
                ],
                "suggestions": data.get("suggestions", []),
                "error": None if results else "Tidak ada hasil.",
            }
            if results:
                _cache_set(cache_key, response)
            return response

    except httpx.TimeoutException:
        logger.warning("[SearXNG] Timeout untuk query: %s", q[:50])
        return {
            "ok": False, "query": q, "engine": "searxng", "results": [],
            "raw_result_count": 0, "engine_stats": {},
            "unresponsive_engines": [], "error": "Timeout.",
        }
    except Exception as exc:
        logger.warning("[SearXNG] Error: %s", exc)
        return {
            "ok": False, "query": q, "engine": "searxng", "results": [],
            "raw_result_count": 0, "engine_stats": {},
            "unresponsive_engines": [], "error": str(exc),
        }


def searxng_search_multi(
    query: str,
    *,
    max_results: int = 10,
    engine_groups: list[str] | None = None,
) -> dict[str, Any]:
    """
    Search dengan multiple engine groups — untuk recall maksimal.

    Jalankan search dengan beberapa konfigurasi engine berbeda,
    lalu gabungkan hasilnya (dedup by URL).
    """
    if engine_groups is None:
        engine_groups = [
            None,
            "bing,brave",
        ]

    all_results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    combined_stats: dict[str, int] = {}
    all_unresponsive: list[dict] = []

    for engines in engine_groups:
        result = searxng_search(query, max_results=max_results, engines=engines)
        if result.get("ok"):
            for r in result.get("results", []):
                url_key = (r.get("url") or "").lower().rstrip("/")
                if url_key and url_key not in seen_urls:
                    seen_urls.add(url_key)
                    all_results.append(r)
            for eng, count in result.get("engine_stats", {}).items():
                combined_stats[eng] = combined_stats.get(eng, 0) + count
        all_unresponsive.extend(result.get("unresponsive_engines", []))
    all_results.sort(key=lambda x: x.get("score", 0), reverse=True)

    return {
        "ok": bool(all_results),
        "query": query,
        "engine": "searxng-multi",
        "results": all_results[:max_results],
        "raw_result_count": len(all_results),
        "engine_stats": combined_stats,
        "unresponsive_engines": all_unresponsive,
        "error": None if all_results else "Tidak ada hasil dari semua engine groups.",
    }
