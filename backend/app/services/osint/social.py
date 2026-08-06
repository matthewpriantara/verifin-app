"""
Social Media OSINT — Scraping jejak rekrutmen/scam di berbagai platform media sosial.
Platform: Threads, Instagram, X (Twitter), TikTok, Facebook.
Menggunakan SearXNG self-hosted untuk semua SERP query.
"""

import re
from typing import Any
from urllib.parse import quote, unquote

from scrapling.fetchers import Fetcher
from app.services.osint.web_evidence import search_web_evidence


def _classify_platform(url: str, default: str = "social_media") -> str:
    """Klasifikasi platform dari URL domain."""
    u = url.lower()
    if "instagram.com" in u: return "instagram"
    if "threads.net" in u or "threads.com" in u: return "threads"
    if "tiktok.com" in u: return "tiktok"
    if "facebook.com" in u: return "facebook"
    if "twitter.com" in u or "x.com" in u: return "x_twitter"
    if "linktr.ee" in u: return "linktree"
    return default


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


def _search_platform_serp(query: str, platform: str = "") -> list[dict[str, str]]:
    """Cari postingan sosmed via search_web_evidence (DDG/Yahoo/Bing)."""
    site_hint = f" site:{platform}" if platform else ""
    result = search_web_evidence(f'"{query}"{site_hint}', max_results=4)
    return [
        {
            "platform": _classify_platform(r.get("url", ""), default="social_media"),
            "source": "serp",
            "title": r.get("title", "")[:120],
            "snippet": r.get("snippet", "")[:280],
            "url": r.get("url", ""),
        }
        for r in result.get("results", [])
        if r.get("title") or r.get("snippet")
    ]


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

    # 1. SERP via slug candidates (all platform via search_web_evidence)
    serp_queries = list(dict.fromkeys([raw_company] + _slug_candidates(raw_company)))
    serp_posts: list[dict] = []
    for q in serp_queries[:2]:
        serp_posts.extend(_search_platform_serp(q))
    # Dedup snippet
    _seen_snip: set[str] = set()
    initial_posts = []
    for p in serp_posts:
        key = p.get("snippet", "")[:80].lower()
        if key not in _seen_snip:
            _seen_snip.add(key)
            initial_posts.append(p)

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
            page = Fetcher().get(url, stealthy_headers=True, network_idle=False)
            results_sel = page.css(".result__body")[:3]
            found_platform = False

            for r in results_sel:
                title_el = r.css(".result__title")
                snippet_el = r.css(".result__snippet")
                url_el = r.css(".result__url")
                title = title_el[0].text.strip() if title_el else ""
                snippet = snippet_el[0].text.strip() if snippet_el else ""
                link = url_el[0].text.strip() if url_el else ""

                if "uddg=" in link:
                    try:
                        link = unquote(link.split("uddg=")[1].split("&")[0])
                    except Exception:
                        pass

                if link and not link.startswith("http"):
                    link = f"https://{link}"

                # Tentukan platform nyata berdasarkan domain URL
                real_platform = _classify_platform(link, default=platform_key)

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
    seen_urls: set[str] = set()
    all_posts = []

    # Token unik nama perusahaan untuk scoring relevansi
    _comp_tokens = {
        t for t in re.sub(r"[^\w]", " ", raw_company.lower()).split()
        if len(t) >= 3 and t not in {"yang", "untuk", "dari", "dengan", "adalah", "dan", "atau"}
    } - {"pt", "cv", "ud", "tb"}

    raw_posts = extra_posts + initial_posts
    for p in raw_posts:
        link = (p.get("url") or "").lower()
        if not link or link in seen_urls:
            continue
        seen_urls.add(link)

        # Klasifikasi platform presisi berdasarkan URL domain
        real_plat = _classify_platform(link, default=p.get("platform") or "social_media")
        if any(domain in link for domain in ("lokerjogja", "glints", "jobstreet", "kalibrr", "kitagrad", "karir")):
            real_plat = "portal_loker"

        p["platform"] = real_plat

        # Skor relevansi — berapa token nama perusahaan match di snippet/title
        if _comp_tokens:
            blob = f"{p.get('title', '')} {p.get('snippet', '')}".lower()
            matched = {t for t in _comp_tokens if t in blob}
            p["match_confidence"] = round(len(matched) / len(_comp_tokens), 2)
        else:
            p["match_confidence"] = 0.0

        # Buang post yang tidak mengandung token nama perusahaan yang cukup
        # instagram/threads: threshold 0.25 (bukan 0.0) — partial match generic seperti
        # "solution", "internasional" di domain lain harus dibuang
        min_conf = 0.26 if real_plat in ("instagram", "threads") else 0.01
        if p["match_confidence"] < min_conf:
            continue

        # Filter post luar negeri yang tidak relevan (bukan Indonesia)
        # Hanya berlaku untuk platform social_media, bukan portal_loker/instagram
        if real_plat == "social_media" and p["match_confidence"] < 1.0:
            link_lower = (p.get("url") or "").lower()
            snippet_lower = (p.get("snippet") or "").lower()
            title_lower = (p.get("title") or "").lower()
            blob_lower = f"{link_lower} {snippet_lower} {title_lower}"
            _id_signals = ("indonesia", " indo ", "jogja", "jakarta", "surabaya",
                           "bandung", "semarang", ".co.id", "lowongan", "loker",
                           "gaji", "pelamar", "rekrutmen")
            has_id_context = any(w in blob_lower for w in _id_signals)
            # domain .com tanpa konteks Indonesia = buang juga
            is_foreign = not has_id_context and (
                any(tld in link_lower for tld in (".com.my", ".sg", ".au", ".uk", ".us", ".ph"))
                or (
                    not any(tld in link_lower for tld in (".co.id", ".id/", "instagram.com",
                                                           "facebook.com", "tiktok.com"))
                    and p["match_confidence"] <= 0.75
                )
            )
            if is_foreign:
                continue

        all_posts.append(p)

    # Prioritaskan media sosial resmi di posisi teratas
    _SOCIAL_PRIORITY = {"instagram", "threads", "tiktok", "facebook", "x_twitter", "linktree"}
    all_posts.sort(key=lambda p: 0 if (p.get("platform") or "").lower() in _SOCIAL_PRIORITY else 1)

    valid_profiles: list = []
    found = bool(all_posts or valid_profiles)

    # Risk flag analysis — gabungan semua platform
    risk_flags: list[str] = []
    blob = " ".join(
        (p.get("snippet", "") + " " + p.get("title", "")) for p in all_posts
    ).lower()

    if any(w in blob for w in ("penipu", "scam", "tipu", "waspada", "bohong", "palsu")):
        risk_flags.append("Ditemukan postingan medsos yang menyebut indikasi penipuan/scam.")

    # Update platform_hits dari all_posts yang sudah di-merge (SERP posts termasuk)
    for p in all_posts:
        plat = p.get("platform", "")
        if plat == "instagram":
            platform_hits["instagram"] = True
        elif plat == "threads":
            platform_hits["threads"] = True
        elif plat == "tiktok":
            platform_hits["tiktok"] = True
        elif plat == "facebook":
            platform_hits["facebook"] = True
        elif plat in ("x_twitter", "twitter"):
            platform_hits["x_twitter"] = True

    return {
        "enabled": True,
        "platform": "social_media",
        "query": raw_company,
        "found": found,
        "authenticated": False,
        "posts": all_posts[:8],
        "profiles": valid_profiles,
        "platform_hits": platform_hits,
        "risk_flags": risk_flags,
        "errors": [],
    }


# Backwards compatibility alias
run_threads_osint = run_social_osint
