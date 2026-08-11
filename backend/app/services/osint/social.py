"""
Social Media OSINT — Scraping jejak rekrutmen/scam di berbagai platform media sosial.
Platform: Threads, Instagram, X (Twitter), TikTok, Facebook.
Menggunakan Lightpanda browser untuk render JS penuh (menggantikan SearXNG).
"""

import re
from typing import Any
from urllib.parse import quote, unquote
from urllib.parse import urlsplit, urlunsplit
from collections import Counter

from scrapling.fetchers import Fetcher

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
_SOCIAL_PLATFORMS = tuple(_PLATFORM_SITE_HINTS)

_PLATFORM_DOMAINS = {
    "instagram": ("instagram.com",),
    "threads": ("threads.net", "threads.com"),
    "tiktok": ("tiktok.com",),
    "facebook": ("facebook.com",),
    "x_twitter": ("x.com", "twitter.com"),
}


# Token generik yang tidak membuktikan identitas brand — match token ini
# tidak boleh menaikkan match_confidence (false positive: "Group", "Store",
# "Solution", nama kota). Token identitas tersisa tetap dipakai sebagai sinyal.
_COMPANY_GENERIC_TOKENS = {
    "group", "store", "official", "solution", "solutions", "service", "services",
    "center", "network", "indonesia", "internasional", "international",
    "aksesoris", "accessories", "collection", "collections", "jaya", "sejahtera",
    "makmur", "abadi", "sentosa", "mandiri", "global", "media", "studio",
    "design", "digital", "karya", "maju", "bersama", "sukses", "utama",
    "online", "shop", "multi", "prima", "indah", "sari", "agung", "mulia",
    "berkah", "karunia", "persada", "nusantara", "jakarta", "yogyakarta",
    "bandung", "surabaya", "medan", "semarang", "solo", "depok", "bekasi",
    "tangerang", "bogor", "malang", "makassar", "palembang",
    # English stopwords yang tidak boleh jadi token identitas
    "the", "and", "for", "with", "from", "that", "this", "are", "was", "were",
    "but", "not", "you", "all", "can", "had", "her", "has", "how", "its",
    "may", "our", "out", "see", "way", "who", "did", "let", "say", "own",
    "just", "get", "got",
}


def _token_in_blob(token: str, blob: str) -> bool:
    """Token boundary match — 'art' tidak boleh match 'partner'/'article'."""
    return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", blob) is not None


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


# Segmen path yang menandakan konten (post/video), BUKAN halaman profil/brand.
_SOCIAL_CONTENT_SEGMENTS = {
    "p", "reel", "reels", "popular", "explore", "accounts",  # instagram
    "videos", "photos", "photo", "posts", "watch", "story.php", "permalink.php",  # facebook
    "status", "video",  # x / tiktok / umum
}


def _profile_only_url(url: str) -> str | None:
    """Kembalikan URL halaman PROFIL/brand saja; None bila URL mengarah ke
    konten spesifik (post/reel/video/status) — konten bukan bukti kepemilikan akun.
    Generik lintas platform, bukan hardcode satu situs."""
    parts = urlsplit((url or "").strip())
    host = parts.netloc.lower().removeprefix("www.")
    segments = [s for s in parts.path.split("/") if s]
    if not segments:
        return None
    first = segments[0].lower()
    if first in _SOCIAL_CONTENT_SEGMENTS:
        return None
    # Facebook profile.php?id=... → anggap profil (ada query id), terima.
    if host == "facebook.com" and first == "profile.php":
        return urlunsplit(("https", host, parts.path, parts.query, ""))
    # Kedalaman > 1 biasanya konten (facebook.com/Page/videos/..., /posts/...)
    if len(segments) > 1 and segments[1].lower() in _SOCIAL_CONTENT_SEGMENTS:
        return None
    # Normal: ambil segmen pertama sebagai handle profil
    if host in ("instagram.com", "threads.net", "threads.com", "tiktok.com", "x.com", "twitter.com"):
        return urlunsplit(("https", host, f"/{segments[0]}", "", ""))
    if host == "facebook.com":
        return urlunsplit(("https", host, f"/{segments[0]}", "", ""))
    return None


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


def run_social_osint(
    entities: dict,
    web_evidence: dict | None = None,
) -> dict[str, Any]:
    """
    Social Media OSINT — cari jejak perusahaan di berbagai platform.
    Platform: Instagram, Threads, X (Twitter), TikTok, Facebook, Linktree, Portal Loker.
    """
    companies = entities.get("companies") or []

    if not companies:
        return {
            "enabled": True,
            "probe_status": "COMPLETED",
            "evidence_status": "NO_RESULTS",
            "platform": "social_media",
            "found": False,
            "posts": [],
            "profiles": [],
            "platform_hits": {platform: False for platform in _SOCIAL_PLATFORMS},
            "social_searches": [],
            "search_diagnostics": {
                "platforms_requested": list(_SOCIAL_PLATFORMS),
            },
            "risk_flags": [],
            "note": "Tidak ada nama perusahaan untuk dicari di media sosial.",
        }

    raw_company = str(companies[0])
    # Ambil kata kunci utama perusahaan (strip kata pengisi)
    clean_company = re.sub(r"\([^)]*\)", "", raw_company)
    clean_company = re.sub(r"^(pt|cv|ud)\.?\s+", "", clean_company, flags=re.I).strip()

    web_evidence = web_evidence if isinstance(web_evidence, dict) else {}
    # Platform requests are owned by web_evidence.py. Consume their results.
    extra_posts: list[dict[str, str]] = []
    platform_hits: dict[str, bool] = {
        platform: False for platform in _SOCIAL_PLATFORMS
    }
    for search in web_evidence.get("social_searches") or []:
        platform_key = search.get("platform") or "social_media"
        hits = [
            {
                "platform": _classify_platform(
                    result.get("url", ""), default=platform_key
                ),
                "source": "serp",
                "title": result.get("title", "")[:120],
                "snippet": result.get("snippet", "")[:280],
                "url": result.get("url", ""),
                "fallback_kind": search.get("fallback_kind"),
            }
            for result in search.get("results") or []
            if result.get("title") or result.get("snippet")
        ]
        extra_posts.extend(hits)
        platform_hits[platform_key] = platform_hits.get(platform_key, False) or bool(hits)

    # Hanya social_searches yang boleh masuk ke social.posts. Hasil web biasa
    # tetap berada di web.searches dan tidak boleh menjadi social_media.
    seen_urls: set[str] = set()
    all_posts = []

    # Token identitas nama perusahaan (buang token generik yang false-positive)
    _comp_tokens = {
        t for t in re.sub(r"[^\w]", " ", raw_company.lower()).split()
        if len(t) >= 3
        and t not in _COMPANY_GENERIC_TOKENS
        and t not in {"yang", "untuk", "dari", "dengan", "adalah", "dan", "atau"}
    } - {"pt", "cv", "ud", "tb"}

    raw_posts = extra_posts
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
        if real_plat not in _SOCIAL_PLATFORMS:
            continue

        p["platform"] = real_plat
        p["is_official"] = False
        p["source_type"] = "social_aggregator" if _is_aggregator_post(p) else "public_search_result"

        # Skor relevansi — token identitas (boundary match, bukan substring)
        if _comp_tokens:
            blob = f"{p.get('title', '')} {p.get('snippet', '')}".lower()
            matched = {t for t in _comp_tokens if _token_in_blob(t, blob)}
            p["match_confidence"] = round(len(matched) / len(_comp_tokens), 2)
            p["matched_tokens"] = sorted(matched)
            p["matched_email"] = bool(re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", blob))
            p["matched_reason"] = (
                "email" if p["matched_email"] and not matched
                else "exact_tokens" if matched else "none"
            )
        else:
            p["match_confidence"] = 0.0
            p["matched_tokens"] = []
            p["matched_email"] = False
            p["matched_reason"] = "generic_only"

        # Buang post yang tidak mengandung token nama perusahaan yang cukup
        # Threshold lebih ketat: 0.34 untuk semua platform — butuh ≥1/2 atau
        # ≥2/3 token identitas match, bukan sekadar 1 token generic seperti "biker"
        min_conf = 0.34
        if p["match_confidence"] < min_conf:
            continue

        # Single-token match (mis. hanya "biker") hanya valid bila token
        # eksplisit ada di URL/handle — bukan sekadar di title/snippet global.
        # Netflix "Watch Biker" tidak boleh match "The Biker Shop".
        # Tapi "biker" di "thebikershopdjokomotorgroup" tetap valid (compact match).
        if len(p.get("matched_tokens") or []) == 1 and _comp_tokens:
            token = p["matched_tokens"][0]
            url_lower = (p.get("url") or "").lower()
            # Cek boundary match ATAU compact match (token sebagai substring di path/handle)
            path_match = re.search(rf"(?:^|[./@_-]){re.escape(token)}(?:$|[./@_-])", url_lower)
            compact_match = token in re.sub(r"[^a-z0-9]", "", url_lower.split("//")[-1].split("?")[0])
            if not path_match and not compact_match:
                continue

        all_posts.append(p)

    # Hasil SERP belum membuktikan kepemilikan akun. Jangan menyebutnya resmi.
    _SOCIAL_PRIORITY = {"instagram", "threads", "tiktok", "facebook", "x_twitter", "linktree"}
    all_posts.sort(key=lambda p: 0 if (p.get("platform") or "").lower() in _SOCIAL_PRIORITY else 1)

    # ── Sinkronisasi dengan web.searches ──────────────────────────────────────
    # web_evidence.py (intelligent_search) menemukan URL media sosial yang
    # relevan (mis. profil Instagram resmi), tetapi social_searches per-platform
    # bisa kosong. Agar social.profiles tidak kosong palsu, derivasikan profil
    # dari hasil web yang URL-nya platform sosial DAN lolos filter relevansi
    # token perusahaan yang sama dengan posts.
    derived_profiles: list[dict[str, Any]] = []
    if web_evidence:
        web_results = [
            r
            for search in (web_evidence.get("searches") or [])
            for r in (search.get("results") or [])
            if isinstance(r, dict)
        ]
        for r in web_results:
            url = (r.get("url") or "").strip()
            if not url:
                continue
            plat = _classify_platform(url, default="")
            if plat not in _SOCIAL_PLATFORMS:
                continue
            # Hanya halaman profil/brand — bukan post/reel/video — yang menjadi
            # bukti "profil". Konten spesifik tetap masuk social.posts.
            canonical = _profile_only_url(url)
            if not canonical:
                continue
            # Relevansi: token perusahaan muncul di title/snippet/url
            blob = f"{r.get('title', '')} {r.get('snippet', '')}".lower()
            url_compact = re.sub(r"[^a-z0-9]", "", canonical.lower())
            matched = {
                t for t in _comp_tokens
                if _token_in_blob(t, blob) or t in url_compact
            }
            if _comp_tokens and not matched:
                continue
            profile = {
                "platform": plat,
                "url": canonical,
                "title": (r.get("title") or "")[:120],
                "snippet": (r.get("snippet") or "")[:280],
                "source": "web_search",
                "is_official": False,
                "matched_tokens": sorted(matched),
                "match_confidence": (
                    round(len(matched) / len(_comp_tokens), 2) if _comp_tokens else 0.0
                ),
            }
            if not any(p.get("url") == canonical for p in derived_profiles):
                derived_profiles.append(profile)

    valid_profiles: list = derived_profiles
    social_found = bool(
        any(_is_social_platform_post(post) and not _is_aggregator_post(post) for post in all_posts)
        or valid_profiles
    )
    public_footprint_found = social_found
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
    platform_hits = {key: False for key in _SOCIAL_PLATFORMS}
    for p in all_posts:
        plat = p.get("platform", "")
        if plat in platform_hits:
            platform_hits[plat] = True
    for p in valid_profiles:
        plat = p.get("platform", "")
        if plat in platform_hits:
            platform_hits[plat] = True

    platform_counts = Counter(p.get("platform") or "other" for p in all_posts)
    profile_counts = Counter(p.get("platform") or "other" for p in valid_profiles)
    known_platforms = (*platform_hits.keys(),)
    by_platform = {
        platform: platform_counts.get(platform, 0) + profile_counts.get(platform, 0)
        for platform in known_platforms
    }
    by_platform["other"] = sum(
        count for platform, count in platform_counts.items()
        if platform not in by_platform
    )

    return {
        "enabled": True,
        "probe_status": "COMPLETED",
        "evidence_status": "FOUND" if public_footprint_found else "NO_RELEVANT_RESULTS",
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
        "public_platform_hits": platform_hits.copy(),
        "evidence_counts": {
            "public_posts": len(all_posts),
            "public_profiles": len(valid_profiles),
            "official_posts": sum(1 for p in all_posts if p.get("is_official")),
            "by_platform": by_platform,
        },
        "search_diagnostics": {
            "platforms_requested": list(_PLATFORM_SITE_HINTS),
            "search_engine": "lightpanda",
            "note": "Hasil sosial diklasifikasikan terpisah dari portal loker dan aggregator.",
        },
        "social_searches": web_evidence.get("social_searches") or [],
        "risk_flags": risk_flags,
        "errors": [],
    }

