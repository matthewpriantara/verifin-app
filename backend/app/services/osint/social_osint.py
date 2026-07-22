"""
Social Media OSINT — Scraping jejak rekrutmen/scam di berbagai platform media sosial.
Platform: Threads, Instagram, X (Twitter), TikTok, Facebook.
Menggunakan DuckDuckGo HTML SERP (site: query) untuk setiap platform.
Mendukung cookie session (secrets/threads_cookies.json) untuk Threads langsung.
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

    # 1. Ekstrak handle @ jika ada di dalam teks (misal: @lifeatrokagroup)
    explicit_handles = re.findall(r"@([A-Za-z0-9._]{3,30})", raw)
    out: list[str] = []
    for h in explicit_handles:
        h_clean = h.lower().strip(".")
        if h_clean and h_clean not in out:
            out.append(h_clean)

    # 2. Bersihkan tanda kurung, prefix PT/CV, dan kata pengisi loker
    cleaned = re.sub(r"\([^)]*\)", "", raw)
    cleaned = re.sub(r"^(pt|cv|ud)\.?\s+", "", cleaned, flags=re.I)
    cleaned = re.sub(
        r"\b(saat|ini|membuka|lowongan|rekrutmen|hiring|posisi|sebagai|grup|group)\b",
        "",
        cleaned,
        flags=re.I,
    )
    cleaned = re.sub(r"[^A-Za-z0-9\s]", " ", cleaned).strip()

    words = [w for w in cleaned.split() if len(w) > 1][:4]
    if words:
        joined = "".join(words).lower()
        underscored = "_".join(w.lower() for w in words)
        first_word = words[0].lower()

        for s in (joined, underscored, first_word):
            if s and s not in out and len(s) >= 3:
                out.append(s)

    return out[:4]


def _search_threads_public_serp(query: str) -> list[dict[str, str]]:
    """Fallback: Scrape postingan Threads.net publik via DuckDuckGo HTML SERP."""
    search_q = f'"{query}" threads'
    url = f"https://html.duckduckgo.com/html/?q={quote(search_q)}"
    posts = []
    try:
        page = Fetcher.get(url, stealthy_headers=True)
        results = page.css(".result")
        for r in results[:4]:
            t = (r.css(".result__title::text").get() or "").strip()
            snip = (r.css(".result__snippet::text").get() or "").strip()
            link = (r.css(".result__url::text").get() or "").strip()
            if "uddg=" in link:
                try:
                    from urllib.parse import unquote
                    link = unquote(link.split("uddg=")[1].split("&")[0])
                except Exception:
                    pass
            if t or snip:
                posts.append({
                    "platform": "threads",
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

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            for q in uniq_queries[:2]:
                # 1) Direct Search Threads
                try:
                    url = f"https://www.threads.net/search?q={quote(q)}&serp_type=default"
                    res = await client.get(url, headers=headers_base)
                    if res.status_code == 200 and len(res.text) > 500:
                        texts = re.findall(
                            r'"text"\s*:\s*"((?:\\.|[^"\\]){10,300})"', res.text
                        )
                        for t in texts[:4]:
                            decoded = (
                                t.encode("utf-8")
                                .decode("unicode_escape", errors="ignore")
                                .replace("\\n", " ")
                                .strip()
                            )
                            if decoded and len(decoded) > 15:
                                posts.append({
                                    "platform": "threads",
                                    "source": "threads_direct",
                                    "query": q,
                                    "snippet": decoded[:280],
                                })
                except Exception as exc:
                    errors.append(f"direct search error: {exc}")

                # 2) Profile Slug Check — VALIDASI KETAT
                for slug in _slug_candidates(q)[:2]:
                    try:
                        purl = f"https://www.threads.net/@{slug}"
                        pres = await client.get(purl, headers=headers_base)
                        if pres.status_code == 200:
                            title_m = re.search(r"<title>(.*?)</title>", pres.text, re.I)
                            title_txt = title_m.group(1).strip() if title_m else ""
                            # HANYA terima jika title memuat username real (misal: 'Mark Zuckerberg (@zuck) • Threads')
                            # Abaikan halaman login / generic 'Threads • Log in' / 'Page Not Found'
                            is_generic_login = "Threads • Log in" in title_txt or "Page Not Found" in pres.text or "isn't available" in pres.text
                            if title_txt and not is_generic_login and ("&#064;" in title_txt or "@" in title_txt):
                                profile_hits.append({
                                    "platform": "threads",
                                    "username": slug,
                                    "url": purl,
                                    "title": title_txt[:120],
                                })
                    except Exception as exc:
                        errors.append(f"profile @{slug}: {exc}")

    # Fallback pencarian SERP jika direct post kurang
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

    return {
        "enabled": True,
        "platform": "threads",
        "query": company,
        "queries_tried": uniq_queries[:4],
        "found": found,
        "authenticated": has_cookie,
        "posts": unique_posts[:6],
        "profiles": profile_hits[:4],
        "risk_flags": risk_flags,
        "errors": errors[:4],
    }


async def run_social_osint(entities: dict) -> dict[str, Any]:
    """
    Social Media OSINT — cari jejak perusahaan di berbagai platform.
    Platform: Instagram, Threads, X (Twitter), TikTok, Facebook, Linktree, Portal Loker.
    """
    companies = entities.get("companies") or []

    if not companies:
        return {
            "enabled": True,
            "platform": "social_media",
            "found": False,
            "posts": [],
            "profiles": [],
            "risk_flags": [],
            "note": "Tidak ada nama perusahaan untuk dicari di media sosial.",
        }

    raw_company = str(companies[0])
    # Ambil kata kunci utama perusahaan (strip kata pengisi)
    clean_company = re.sub(r"\([^)]*\)", "", raw_company)
    clean_company = re.sub(r"^(pt|cv|ud)\.?\s+", "", clean_company, flags=re.I).strip()

    # 1. Threads utama (cookie-based jika ada)
    threads_result = await search_threads_for_company(raw_company, extra_queries=[])

    # 2. Multi-platform via Natural DuckDuckGo SERP
    platforms = [
        ("instagram", f"{clean_company} instagram"),
        ("threads",   f"{clean_company} threads"),
        ("tiktok",    f"{clean_company} tiktok"),
        ("facebook",  f"{clean_company} facebook"),
        ("x_twitter", f"{clean_company} twitter"),
    ]
    extra_posts: list[dict[str, str]] = []
    platform_hits: dict[str, bool] = {}

    for platform_key, search_q in platforms:
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote(search_q)}"
            page = Fetcher.get(url, stealthy_headers=True, network_idle=False)
            results_sel = page.css(".result__body")[:3]
            found_platform = False

            for r in results_sel:
                title_el = r.css_first(".result__title")
                snippet_el = r.css_first(".result__snippet")
                url_el = r.css_first(".result__url")
                title = title_el.text.strip() if title_el else ""
                snippet = snippet_el.text.strip() if snippet_el else ""
                link = url_el.text.strip() if url_el else ""

                if "uddg=" in link:
                    try:
                        from urllib.parse import unquote
                        link = unquote(link.split("uddg=")[1].split("&")[0])
                    except Exception:
                        pass

                if link and not link.startswith("http"):
                    link = f"https://{link}"

                # Tentukan platform nyata berdasarkan domain URL
                l_lower = link.lower()
                real_platform = platform_key
                if "instagram.com" in l_lower:
                    real_platform = "instagram"
                elif "threads.net" in l_lower or "threads.com" in l_lower:
                    real_platform = "threads"
                elif "tiktok.com" in l_lower:
                    real_platform = "tiktok"
                elif "facebook.com" in l_lower:
                    real_platform = "facebook"
                elif "twitter.com" in l_lower or "x.com" in l_lower:
                    real_platform = "x_twitter"
                elif "linktr.ee" in l_lower:
                    real_platform = "linktree"

                # Extract handle username dari URL jika ada
                username = ""
                u_match = re.search(r"(?:instagram\.com|threads\.net|tiktok\.com|facebook\.com|x\.com|twitter\.com)/@?([A-Za-z0-9._]{3,30})", link, re.I)
                if u_match:
                    username = u_match.group(1).rstrip("/")

                if title or snippet:
                    extra_posts.append({
                        "platform": real_platform,
                        "title": title,
                        "snippet": snippet,
                        "url": link,
                        "username": username,
                    })
                    found_platform = True

            platform_hits[platform_key] = found_platform
        except Exception:
            platform_hits[platform_key] = False

    # Gabungkan semua posts & dedup berdasarkan URL, set platform dinamis
    seen_urls = set()
    all_posts = []

    raw_posts = extra_posts + list(threads_result.get("posts") or [])
    for p in raw_posts:
        link = (p.get("url") or "").lower()
        if not link or link in seen_urls:
            continue
        seen_urls.add(link)

        # Klasifikasi platform presisi berdasarkan URL domain
        real_plat = p.get("platform") or "social_media"
        if "instagram.com" in link:
            real_plat = "instagram"
        elif "threads.net" in link or "threads.com" in link:
            real_plat = "threads"
        elif "tiktok.com" in link:
            real_plat = "tiktok"
        elif "facebook.com" in link:
            real_plat = "facebook"
        elif "twitter.com" in link or "x.com" in link:
            real_plat = "x_twitter"
        elif "linktr.ee" in link:
            real_plat = "linktree"
        elif any(domain in link for domain in ("lokerjogja", "glints", "jobstreet", "kalibrr", "kitagrad", "karir")):
            real_plat = "portal_loker"

        p["platform"] = real_plat
        all_posts.append(p)

    # Prioritaskan media sosial resmi (Instagram, Threads, TikTok, FB, Linktree) di posisi teratas
    def _post_priority(p: dict) -> int:
        plat = (p.get("platform") or "").lower()
        if plat in ("instagram", "threads", "tiktok", "facebook", "x_twitter", "linktree"):
            return 0
        return 1

    all_posts.sort(key=_post_priority)

    valid_profiles = list(threads_result.get("profiles") or [])
    found = bool(all_posts or valid_profiles)

    # Risk flag analysis — gabungan semua platform
    risk_flags = list(threads_result.get("risk_flags") or [])
    blob = " ".join(
        (p.get("snippet", "") + " " + p.get("title", "")) for p in all_posts
    ).lower()

    if any(w in blob for w in ("penipu", "scam", "tipu", "waspada", "bohong", "palsu")):
        risk_flags.append("Ditemukan postingan medsos yang menyebut indikasi penipuan/scam.")

    return {
        "enabled": True,
        "platform": "social_media",
        "query": raw_company,
        "found": found,
        "authenticated": threads_result.get("authenticated", False),
        "posts": all_posts[:8],
        "profiles": valid_profiles,
        "platform_hits": platform_hits,
        "risk_flags": risk_flags,
        "errors": threads_result.get("errors") or [],
    }


# Backwards compatibility alias
run_threads_osint = run_social_osint
