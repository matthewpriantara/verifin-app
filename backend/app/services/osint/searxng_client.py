"""
SearXNG Client — multi-engine search aggregator sebagai backbone Search Intelligence Layer.

SearXNG instance: http://localhost:8888 (self-hosted via Docker)
Engines aktif: Bing, Brave, Wikipedia
Format: JSON

Fitur:
1. Multi-engine search via SearXNG (aggregasi hasil dari banyak engine)
2. Engine stats — pantau engine mana yang aktif/gagal
3. Fallback ke Lightpanda bila SearXNG down
"""
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
_SEARXNG_TIMEOUT = 15  # detik

# ── Query result cache (in-memory, TTL) ──────────────────────────────────────
# Satu verifikasi dapat menembak query yang SAMA berkali-kali dari banyak modul
# (web evidence, social search, platform providers, phone/address validator).
# Engine publik (Brave/DDG/Startpage/Mojeek) cepat kena captcha/rate-limit bila
# dibanjiri query identik. Cache ini memastikan query yang sama hanya memanggil
# SearXNG SEKALI dalam window TTL — generik, tidak terikat jenis lowongan.
_QUERY_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SECONDS = 300  # 5 menit — cukup untuk satu siklus verifikasi
_CACHE_MAX_ENTRIES = 256


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
    """Cek apakah SearXNG instance tersedia."""
    try:
        resp = httpx.get(f"{_SEARXNG_BASE}/healthz", timeout=5)
        return resp.status_code == 200
    except Exception:
        # Coba endpoint search langsung
        try:
            resp = httpx.get(
                f"{_SEARXNG_BASE}/search",
                params={"q": "test", "format": "json"},
                timeout=5,
            )
            return resp.status_code == 200
        except Exception:
            return False


def searxng_search(
    query: str,
    *,
    max_results: int = 10,
    engines: str | None = None,
    language: str = "id",
) -> dict[str, Any]:
    """
    Search via SearXNG — aggregasi multi-engine.

    Args:
        query: Query pencarian
        max_results: Maks hasil
        engines: Engine spesifik (misal "bing,brave"), None = semua
        language: Bahasa hasil pencarian

    Returns:
        {
            "ok": bool,
            "query": str,
            "engine": "searxng",
            "results": [{"title", "url", "snippet", "engines", "score"}],
            "raw_result_count": int,
            "engine_stats": {"bing": 3, "brave": 2, ...},
            "unresponsive_engines": [...],
            "error": str | None,
        }
    """
    q = (query or "").strip()
    if not q:
        return {
            "ok": False, "query": q, "engine": "searxng", "results": [],
            "raw_result_count": 0, "engine_stats": {},
            "unresponsive_engines": [], "error": "Query kosong.",
        }

    cache_key = _cache_key(q, max_results, engines, language)
    cached = _cache_get(cache_key)
    if cached is not None:
        logger.debug("[SearXNG] cache hit untuk query: %s", q[:60])
        return {**cached, "cached": True}

    params: dict[str, str] = {
        "q": q,
        "format": "json",
        "language": language,
    }
    if engines:
        params["engines"] = engines

    try:
        with httpx.Client(timeout=_SEARXNG_TIMEOUT) as client:
            resp = client.get(f"{_SEARXNG_BASE}/search", params=params)

            if resp.status_code == 429:
                logger.warning("[SearXNG] Rate limited (429)")
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

            # Parse results
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

            # Sort by SearXNG score (descending)
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
            # Hanya cache hasil yang ada isinya — hasil kosong/error tidak di-cache
            # agar retry setelah engine pulih tetap bisa mencoba ulang.
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
            None,  # semua engine aktif
            "bing,brave",  # western engines
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

    # Re-sort by score
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
