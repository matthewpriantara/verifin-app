"""
OSINT Threads (Meta) — Scraping jejak rekrutmen/scam di Threads.net.
Mendukung cookie session (secrets/threads_cookies.json) dan fallback pencarian publik via DuckDuckGo HTML.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote

import httpx
from scrapling.fetchers import Fetcher

COOKIES_PATH = (
    Path(__file__).resolve().parents[3] / "secrets" / "threads_cookies.json"
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


def _load_cookie_jar() -> dict[str, str]:
    if not COOKIES_PATH.exists():
        return {}
    try:
        data = json.loads(COOKIES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

    jar: dict[str, str] = {}
    if isinstance(data, list):
        for item in data:
            name = item.get("name")
            value = item.get("value")
            if name and value is not None:
                jar[str(name)] = str(value)
    elif isinstance(data, dict):
        jar = {str(k): str(v) for k, v in data.items()}
    return jar


def _cookie_header(jar: dict[str, str]) -> str:
    return "; ".join(f"{k}={v}" for k, v in jar.items())


def _slug_candidates(company: str) -> list[str]:
    raw = company.strip()
    cleaned = re.sub(r"^(pt|cv|ud)\.?\s+", "", raw, flags=re.I)
    cleaned = re.sub(r"[^A-Za-z0-9\s]", " ", cleaned)
    words = [w for w in cleaned.split() if len(w) > 1][:4]
    if not words:
        return []

    joined = "".join(words).lower()
    underscored = "_".join(w.lower() for w in words)
    first_last = (words[0] + words[-1]).lower() if len(words) > 1 else words[0].lower()
    out = []
    for s in (joined, underscored, first_last, words[0].lower()):
        if s and s not in out and len(s) >= 3:
            out.append(s)
    return out[:4]


def _search_threads_public_serp(query: str) -> list[dict[str, str]]:
    """Fallback: Scrape postingan Threads.net publik via DuckDuckGo HTML SERP."""
    search_q = f'site:threads.net "{query}"'
    url = f"https://html.duckduckgo.com/html/?q={quote(search_q)}"
    posts = []
    try:
        page = Fetcher.get(url, stealthy_headers=True)
        results = page.css(".result")
        for r in results[:4]:
            t = (r.css(".result__title::text").get() or "").strip()
            snip = (r.css(".result__snippet::text").get() or "").strip()
            link = (r.css(".result__url::text").get() or "").strip()
            if t or snip:
                posts.append({
                    "source": "threads_serp_fallback",
                    "title": t[:120],
                    "snippet": snip[:280],
                    "url": link if link.startswith("http") else f"https://{link}",
                })
    except Exception:
        pass
    return posts


async def search_threads_for_company(
    company: str,
    *,
    extra_queries: Optional[list[str]] = None,
) -> dict[str, Any]:
    """
    Cari jejak perusahaan di Threads.net via session cookie atau public SERP fallback.
    """
    jar = _load_cookie_jar()
    has_cookie = bool(jar.get("sessionid"))

    queries = [company]
    queries.extend(_slug_candidates(company))
    if extra_queries:
        queries.extend(extra_queries)

    seen_q = set()
    uniq_queries = []
    for q in queries:
        qn = q.strip()
        if qn and qn.lower() not in seen_q:
            seen_q.add(qn.lower())
            uniq_queries.append(qn)

    posts: list[dict[str, str]] = []
    profile_hits: list[dict[str, str]] = []
    errors: list[str] = []

    if has_cookie:
        headers_base = {
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
            "Cookie": _cookie_header(jar),
            "X-CSRFToken": jar.get("csrftoken", ""),
            "X-IG-App-ID": "238260118697367",
            "Referer": "https://www.threads.net/",
            "Origin": "https://www.threads.net",
        }

        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            for q in uniq_queries[:3]:
                # 1) Search page Threads.net
                try:
                    url = f"https://www.threads.net/search?q={quote(q)}&serp_type=default"
                    res = await client.get(url, headers=headers_base)
                    if res.status_code == 200 and len(res.text) > 500:
                        texts = re.findall(
                            r'"text"\s*:\s*"((?:\\.|[^"\\]){10,300})"', res.text
                        )
                        for t in texts[:5]:
                            decoded = (
                                t.encode("utf-8")
                                .decode("unicode_escape", errors="ignore")
                                .replace("\\n", " ")
                                .strip()
                            )
                            if decoded:
                                posts.append({
                                    "source": "threads_direct",
                                    "query": q,
                                    "snippet": decoded[:280],
                                })
                    elif res.status_code in (401, 403):
                        errors.append(f"direct search blocked ({res.status_code}) for q={q}")
                    else:
                        errors.append(f"direct search status {res.status_code} for q={q}")
                except Exception as exc:
                    errors.append(f"direct search error q={q}: {exc}")

                # 2) Profile slug Threads.net
                for slug in _slug_candidates(q)[:2]:
                    try:
                        purl = f"https://www.threads.net/@{slug}"
                        pres = await client.get(purl, headers=headers_base)
                        if pres.status_code == 200 and "Page Not Found" not in pres.text:
                            title = re.search(r"<title>(.*?)</title>", pres.text, re.I)
                            profile_hits.append({
                                "username": slug,
                                "url": purl,
                                "title": (title.group(1).strip() if title else "")[:120],
                            })
                    except Exception as exc:
                        errors.append(f"profile @{slug}: {exc}")

    # Fallback pencarian SERP jika direct post kurang atau tidak ada cookie
    if len(posts) < 2:
        for q in uniq_queries[:2]:
            serp_posts = _search_threads_public_serp(q)
            posts.extend(serp_posts)

    # Dedup snippets
    seen_snip = set()
    unique_posts = []
    for p in posts:
        key = p.get("snippet", "")[:80].lower()
        if key in seen_snip:
            continue
        seen_snip.add(key)
        unique_posts.append(p)

    found = bool(unique_posts or profile_hits)
    risk_flags = []
    if found:
        blob = " ".join((p.get("snippet", "") + " " + p.get("title", "")) for p in unique_posts).lower()
        if any(w in blob for w in ("penipu", "scam", "tipu", "waspada", "bohong", "palsu")):
            risk_flags.append("Ditemukan postingan Threads yang menyebut indikasi penipuan/scam.")
        if any(w in blob for w in ("loker", "lowongan", "kerja", "rekrut", "hrd")):
            risk_flags.append("Ada jejak pembahasan rekrutmen/lowongan di Threads terkait entitas ini.")

    return {
        "enabled": True,
        "platform": "threads",
        "query": company,
        "queries_tried": uniq_queries[:5],
        "found": found,
        "authenticated": has_cookie,
        "posts": unique_posts[:8],
        "profiles": profile_hits[:5],
        "risk_flags": risk_flags,
        "errors": errors[:5],
    }


async def run_threads_osint(entities: dict) -> dict[str, Any]:
    companies = entities.get("companies") or []
    contacts = entities.get("contacts") or []
    emails = entities.get("emails") or []

    if not companies and not contacts and not emails:
        return {
            "enabled": True,
            "platform": "threads",
            "found": False,
            "posts": [],
            "profiles": [],
            "risk_flags": [],
            "note": "Tidak ada entitas untuk dicari di Threads.",
        }

    primary = companies[0] if companies else (emails[0] if emails else contacts[0])
    extra = []
    if emails:
        extra.append(emails[0].split("@")[0])
    return await search_threads_for_company(str(primary), extra_queries=extra)
