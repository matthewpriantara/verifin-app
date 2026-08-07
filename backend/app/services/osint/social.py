"""
Social Media OSINT — Scraping jejak rekrutmen/scam di berbagai platform media sosial.
Platform: Threads, Instagram, X (Twitter), TikTok, Facebook.
Menggunakan SearXNG self-hosted untuk semua SERP query.
"""

import re
from typing import Any
from urllib.parse import quote, unquote
from urllib.parse import urlsplit, urlunsplit
from collections import Counter

from scrapling.fetchers import Fetcher
from app.services.osint.web_evidence import search_web_evidence
from app.services.osint.query_builder import build_search_queries

_SOCIAL_AGGREGATOR_TOKENS = (
    "lokerjogja", "loker jogja", "lokerterbaru", "loker terbaru",
    "loker indonesia", "lowongan kerja", "pusat loker", "info loker",
)

_PLATFORM_SITE_HINTS = {
    "instagram": "site:instagram.com",
    "threads": "site:threads.net OR site:threads.com",
    "tiktok": "site:tiktok.com",
    "facebook": "site:facebook.com",
    "x_twitter": "site:x.com OR site:twitter.com",
}

_PLATFORM_DOMAINS = {
    "instagram": ("instagram.com",),
    "threads": ("threads.net", "threads.com"),
    "tiktok": ("tiktok.com",),
    "facebook": ("facebook.com",),
    "x_twitter": ("x.com", "twitter.com"),
}


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


def _is_aggregator_post(post: dict[str, str]) -> bool:
    url_title = " ".join((post.get("url") or "", post.get("title") or "")).lower()
    return any(token in url_title for token in _SOCIAL_AGGREGATOR_TOKENS)


def _is_social_platform_post(post: dict[str, str]) -> bool:
    return post.get("platform") in {"instagram", "threads", "tiktok", "facebook", "x_twitter"}


def _canonical_social_url(url: str) -> str | None:
    parts = urlsplit((url or "").strip())
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/")
    if host == "instagram.com":
        segments = [segment for segment in path.split("/") if segment]
        if not segments or segments[0].lower() in {"p", "reel", "reels", "popular", "explore", "accounts"}:
            return None
        return urlunsplit(("https", host, f"/{segments[0]}", "", ""))
    return urlunsplit((parts.scheme or "https", host, path, "", ""))


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
    """Cari platform via broad SERP, lalu filter domain di aplikasi."""
    query_text = query.strip()
    quoted_query = query_text if query_text.startswith('"') else f'"{query_text}"'
    result = search_web_evidence(
        quoted_query,
        max_results=8,
    )
    domains = _PLATFORM_DOMAINS.get(platform)
    return [
        {
            "platform": _classify_platform(r.get("url", ""), default="social_media"),
            "source": "serp",
            "title": r.get("title", "")[:120],
            "snippet": r.get("snippet", "")[:280],
            "url": r.get("url", ""),
        }
        for r in result.get("results", [])
        if not domains or any(domain in (r.get("url") or "").lower() for domain in domains)
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

    serp_posts: list[dict] = []
    query_candidates = build_search_queries(entities, include_email=True)
    for candidate in query_candidates:
        hits = _search_platform_serp(candidate["query"])
        for hit in hits:
            hit["fallback_kind"] = candidate["kind"]
        serp_posts.extend(hits)
        if any(_is_social_platform_post(hit) and not _is_aggregator_post(hit) for hit in hits):
            break
    # Dedup snippet
    _seen_snip: set[str] = set()
    initial_posts = []
    for p in serp_posts:
        key = p.get("snippet", "")[:80].lower()
        if key not in _seen_snip:
            _seen_snip.add(key)
            initial_posts.append(p)

    # 2. Multi-platform via SearXNG (reuse _search_platform_serp)
    platforms = [
        ("instagram", f"{clean_company} instagram"),
        ("threads",   f"{clean_company} threads"),
        ("tiktok",    f"{clean_company} tiktok"),
        ("facebook",  f"{clean_company} facebook"),
        ("x_twitter", f"{clean_company} twitter"),
    ]
    extra_posts: list[dict[str, str]] = []
    platform_hits: dict[str, bool] = {}

    fallback_candidates = query_candidates or [{"query": raw_company}]
    for platform_key, search_q in platforms:
        hits = []
        for candidate in fallback_candidates:
            hits = _search_platform_serp(f"{candidate['query']} {platform_key}", platform_key)
            for hit in hits:
                hit["fallback_kind"] = candidate.get("kind")
            if hits:
                break
        extra_posts.extend(hits)
        platform_hits[platform_key] = bool(hits)

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
        canonical_url = _canonical_social_url(p.get("url") or "")
        if not canonical_url:
            continue
        p["url"] = canonical_url
        link = canonical_url.lower()
        if not link or link in seen_urls:
            continue
        seen_urls.add(link)

        # Klasifikasi platform presisi berdasarkan URL domain
        real_plat = _classify_platform(link, default=p.get("platform") or "social_media")
        if any(domain in link for domain in ("lokerjogja", "glints", "jobstreet", "kalibrr", "kitagrad", "karir")):
            real_plat = "portal_loker"

        p["platform"] = real_plat
        p["is_official"] = False
        p["source_type"] = "social_aggregator" if _is_aggregator_post(p) else "public_search_result"

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

    # Hasil SERP belum membuktikan kepemilikan akun. Jangan menyebutnya resmi.
    _SOCIAL_PRIORITY = {"instagram", "threads", "tiktok", "facebook", "x_twitter", "linktree"}
    all_posts.sort(key=lambda p: 0 if (p.get("platform") or "").lower() in _SOCIAL_PRIORITY else 1)

    valid_profiles: list = []
    social_found = bool(
        any(_is_social_platform_post(post) and not _is_aggregator_post(post) for post in all_posts)
        or valid_profiles
    )
    public_footprint_found = bool(all_posts or valid_profiles)
    found = social_found

    # Risk flag analysis — gabungan semua platform
    risk_flags: list[str] = []
    blob = " ".join(
        (p.get("snippet", "") + " " + p.get("title", "")) for p in all_posts
    ).lower()

    hard_scam_phrases = (
        "laporan penipuan", "korban penipuan", "loker palsu", "penipu loker",
        "scam loker", "terbukti menipu", "ditipu", "modus penipuan",
    )
    if any(phrase in blob for phrase in hard_scam_phrases):
        risk_flags.append("Ditemukan postingan publik dengan frasa indikasi penipuan spesifik.")

    # Hitung ulang hanya dari profil/post yang memang ditandai resmi.
    platform_hits = {key: False for key in platform_hits}
    for p in all_posts:
        plat = p.get("platform", "")
        if plat == "instagram" and p.get("is_official"):
            platform_hits["instagram"] = True
        elif plat == "threads" and p.get("is_official"):
            platform_hits["threads"] = True
        elif plat == "tiktok" and p.get("is_official"):
            platform_hits["tiktok"] = True
        elif plat == "facebook" and p.get("is_official"):
            platform_hits["facebook"] = True
        elif plat in ("x_twitter", "twitter") and p.get("is_official"):
            platform_hits["x_twitter"] = True

    platform_counts = Counter(p.get("platform") or "other" for p in all_posts)
    known_platforms = (*platform_hits.keys(), "portal_loker", "linktree", "social_media")
    by_platform = {
        platform: platform_counts.get(platform, 0)
        for platform in known_platforms
    }
    by_platform["other"] = sum(
        count for platform, count in platform_counts.items()
        if platform not in by_platform
    )
    assert sum(by_platform.values()) == len(all_posts)

    return {
        "enabled": True,
        "platform": "social_media",
        "query": raw_company,
        "found": found,
        "social_found": social_found,
        "official_social_found": bool(valid_profiles or any(p.get("is_official") for p in all_posts)),
        "public_footprint_found": public_footprint_found,
        "authenticated": False,
        "posts": all_posts[:8],
        "profiles": valid_profiles,
        "platform_hits": platform_hits,
        "official_platform_hits": platform_hits.copy(),
        "public_platform_hits": {
            platform: any(p.get("platform") == platform for p in all_posts)
            for platform in ("instagram", "threads", "tiktok", "facebook", "x_twitter", "portal_loker")
        },
        "evidence_counts": {
            "public_posts": len(all_posts),
            "public_profiles": len(valid_profiles),
            "official_posts": sum(1 for p in all_posts if p.get("is_official")),
            "by_platform": by_platform,
        },
        "search_diagnostics": {
            "platforms_requested": list(_PLATFORM_SITE_HINTS),
            "search_engine": "searxng",
            "note": "Hasil sosial diklasifikasikan terpisah dari portal loker dan aggregator.",
        },
        "risk_flags": risk_flags,
        "errors": [],
    }


# Backwards compatibility alias
run_threads_osint = run_social_osint
