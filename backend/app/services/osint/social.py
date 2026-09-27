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
    "the", "and", "for", "with", "from", "that", "this", "are", "was", "were",
    "but", "not", "you", "all", "can", "had", "her", "has", "how", "its",
    "may", "our", "out", "see", "way", "who", "did", "let", "say", "own",
    "just", "get", "got",
}


def _token_in_blob(token: str, blob: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", blob) is not None


def _classify_platform(url: str, default: str = "social_media") -> str:
    try:
        from urllib.parse import urlparse
        host = urlparse(url or "").netloc.lower().removeprefix("www.")
        if host == "instagram.com" or host.endswith(".instagram.com"):
            return "instagram"
        if host in {"threads.net", "threads.com"} or host.endswith(".threads.net"):
            return "threads"
        if host == "tiktok.com" or host.endswith(".tiktok.com"):
            return "tiktok"
        if host in {"facebook.com", "fb.com"} or host.endswith(".facebook.com"):
            return "facebook"
        if host in {"twitter.com", "x.com"} or host.endswith(".twitter.com") or host.endswith(".x.com"):
            return "x_twitter"
        if host == "linktr.ee" or host.endswith(".linktr.ee"):
            return "linktree"
        if host == "linkedin.com" or host.endswith(".linkedin.com"):
            return "linkedin"
    except Exception:
        pass
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


_SOCIAL_CONTENT_SEGMENTS = {
    "p", "reel", "reels", "popular", "explore", "accounts",
    "videos", "photos", "photo", "posts", "watch", "story.php", "permalink.php",
    "status", "video",
}


def _profile_only_url(url: str) -> str | None:
    parts = urlsplit((url or "").strip())
    host = parts.netloc.lower().removeprefix("www.")
    segments = [s for s in parts.path.split("/") if s]
    if not segments:
        return None
    first = segments[0].lower()
    if first in _SOCIAL_CONTENT_SEGMENTS:
        return None
    if host == "facebook.com" and first == "profile.php":
        return urlunsplit(("https", host, parts.path, parts.query, ""))
    if len(segments) > 1 and segments[1].lower() in _SOCIAL_CONTENT_SEGMENTS:
        return None
    if host in ("instagram.com", "threads.net", "threads.com", "tiktok.com", "x.com", "twitter.com"):
        return urlunsplit(("https", host, f"/{segments[0]}", "", ""))
    if host == "facebook.com":
        return urlunsplit(("https", host, f"/{segments[0]}", "", ""))
    return None


def _slug_candidates(company: str) -> list[str]:
    raw = company.strip()

    explicit_handles = re.findall(r"@([A-Za-z0-9._]{3,30})", raw)
    out: list[str] = []
    for h in explicit_handles:
        h_clean = h.lower().strip(".")
        if h_clean and h_clean not in out:
            out.append(h_clean)

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
    clean_company = re.sub(r"\([^)]*\)", "", raw_company)
    clean_company = re.sub(r"^(pt|cv|ud)\.?\s+", "", clean_company, flags=re.I).strip()

    web_evidence = web_evidence if isinstance(web_evidence, dict) else {}
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
    seen_urls: set[str] = set()
    all_posts = []
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

        real_plat = _classify_platform(link, default=p.get("platform") or "social_media")
        if real_plat not in _SOCIAL_PLATFORMS:
            continue

        p["platform"] = real_plat
        p["is_official"] = False
        p["source_type"] = "social_aggregator" if _is_aggregator_post(p) else "public_search_result"

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
        min_conf = 0.34
        if p["match_confidence"] < min_conf:
            continue
        if len(p.get("matched_tokens") or []) == 1 and _comp_tokens:
            token = p["matched_tokens"][0]
            url_lower = (p.get("url") or "").lower()
            path_match = re.search(rf"(?:^|[./@_-]){re.escape(token)}(?:$|[./@_-])", url_lower)
            compact_match = token in re.sub(r"[^a-z0-9]", "", url_lower.split("//")[-1].split("?")[0])
            if not path_match and not compact_match:
                continue

        all_posts.append(p)
    _SOCIAL_PRIORITY = {"instagram", "threads", "tiktok", "facebook", "x_twitter", "linktree"}
    all_posts.sort(key=lambda p: 0 if (p.get("platform") or "").lower() in _SOCIAL_PRIORITY else 1)
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
            canonical = _profile_only_url(url)
            if not canonical:
                continue
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

