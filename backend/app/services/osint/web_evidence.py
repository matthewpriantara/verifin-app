"""
Web evidence via SearXNG (primary) + Lightpanda Browser (fallback) + Scrapling:
1) Fetch website dari domain email / URL di loker (Lightpanda render JS penuh)
2) Search evidence lewat SearXNG multi-engine (Bing/Brave/Wikipedia)
   Fallback ke Lightpanda (render DuckDuckGo/Google HTML) jika SearXNG down
3) Search Intelligence Layer untuk query planning + entity resolution + re-ranking
"""

import base64
import re
import asyncio
import logging
from typing import Any
from urllib.parse import quote_plus, urlparse

from scrapling.fetchers import Fetcher
from app.services.osint.gform_inspector import inspect_gform, is_gform_url
from app.services.constants import FREE_EMAIL_DOMAINS
from app.services.osint.query_builder import build_search_queries
from app.services.osint.searxng_client import searxng_search, is_searxng_available
from app.services.status_contract import COMPLETED, FOUND, NO_RESULTS, NO_RELEVANT_RESULTS, UNAVAILABLE

logger = logging.getLogger(__name__)

_SOCIAL_AGGREGATOR_TOKENS = (
    "lokerjogja", "loker jogja", "lokerterbaru", "loker terbaru",
    "loker indonesia", "lowongan kerja", "pusat loker", "info loker",
)

_ENTITY_QUERY_STOPWORDS = {
    "pt", "cv", "ud", "tbk", "firma", "yayasan", "lowongan", "penipuan",
    "penipu", "scam", "instagram", "website", "toko", "or", "dan",
}

_SOCIAL_PLATFORM_DOMAINS = {
    "instagram": ("instagram.com",),
    "threads": ("threads.net", "threads.com"),
    "tiktok": ("tiktok.com",),
    "facebook": ("facebook.com",),
    "x_twitter": ("x.com", "twitter.com"),
}


def _public_source_type(url: str, title: str = "", snippet: str = "") -> str:
    url_title = f"{url} {title}".lower()
    if any(domain in url.lower() for domain in ("tokopedia.com", "shopee.co.id")):
        return "marketplace"
    if any(domain in url.lower() for domain in ("loker", "jobstreet", "glints", "kalibrr", "linkedin.com/jobs", "karir")):
        return "job_portal"
    if any(token in url_title for token in _SOCIAL_AGGREGATOR_TOKENS):
        return "social_aggregator"
    if any(domain in url.lower() for domain in ("instagram.com", "facebook.com", "tiktok.com", "threads.net", "x.com", "twitter.com")):
        return "social_platform"
    return "web"


def _result_matches_query(query: str, url: str, title: str, snippet: str) -> bool:
    """Return True bila result (url+title+snippet) menyebutkan entitas dari query.

    Query tanpa quote: ekstrak token identitas (≥3 char, bukan stopword).
    Butuh ≥2 token match (atau 1 token yang eksplisit di URL/handle) untuk
    menghindari false positive dari snippet ambigu.
    """
    hay = re.sub(r"[^a-z0-9]+", " ", f"{url} {title} {snippet}".lower()).strip()
    hay_compact = hay.replace(" ", "")
    emails = re.findall(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", query.lower())
    if emails:
        return any(email in f"{url} {title} {snippet}".lower() for email in emails)

    # Ekstrak phrase dari quote (legacy) ATAU gunakan query natural sebagai phrase
    quoted = re.findall(r'"([^"]+)"', query or "")
    phrases = list(quoted) if quoted else []
    if not phrases:
        natural = re.sub(r"[^a-z0-9]+", " ", (query or "").lower()).strip()
        if natural:
            phrases = [natural]

    if not phrases:
        return True

    for phrase in phrases:
        phrase_clean = re.sub(r"[^a-z0-9]+", " ", phrase.lower()).strip()
        tokens = [
            token for token in phrase_clean.split()
            if len(token) >= 3 and token not in _ENTITY_QUERY_STOPWORDS
        ]
        if not tokens:
            continue
        phrase_compact = phrase_clean.replace(" ", "")
        if len(tokens) >= 2 and phrase_compact in hay_compact:
            return True
        matched = {token for token in set(tokens) if token in hay.split()}
        if len(tokens) == 1 and len(matched) == 1:
            # Single token hanya valid bila eksplisit di URL/handle (domain,
            # subdomain, atau segmen path) — bukan sekadar muncul di snippet
            # global yang ambigu ("Bangor", nama brand umum).
            if re.search(rf"(?:^|[./@_-]){re.escape(tokens[0])}(?:$|[./@_-])", url.lower()):
                return True
            continue
        if len(tokens) >= 2 and len(matched) >= 2:
            # Dua token identitas cukup; satu token ("Bangor") tidak.
            return True
    return False


def _domain_from_email(email: str) -> str | None:
    if not email or "@" not in email:
        return None
    domain = email.split("@")[-1].strip().lower()
    if domain in FREE_EMAIL_DOMAINS:
        return None
    return domain


def _normalize_url(url: str) -> str | None:
    u = (url or "").strip()
    if not u:
        return None
    if u.startswith("www."):
        u = "https://" + u
    if not re.match(r"^https?://", u, re.I):
        if re.match(r"^[a-z0-9.-]+\.[a-z]{2,}", u, re.I):
            u = "https://" + u
        else:
            return None
    return u



def _is_script_or_ad_junk(t: str) -> bool:
    if not t or not t.strip():
        return True
    low = t.lower()
    junk_patterns = (
        "adsbygoogle",
        "function timer",
        "clearinterval",
        "setinterval",
        "window.location",
        "document.getelementbyid",
        "document.queryselector",
        "targetnode",
        "mutationobserver",
        "you are being redirected",
        "intipxads",
        "var count =",
        "var counter =",
        '{"require":',
        "maybedisableanimations",
        "qpltagserverjs",
        "cometssrmergedcontentinjector",
        "window.adsbygoogle",
        "const targetnode",
        "clearinterval( counter )",
    )
    if any(p in low for p in junk_patterns):
        return True
    if re.search(r"function\s+\w+\s*\(|var\s+count\s*=|window\.location\.href\s*=|document\.getElementById\(|MutationObserver\(|\(adsbygoogle\s*=", t, re.I):
        return True
    return False


def _snippet_from_page(page, max_len: int = 500) -> str:
    try:
        texts = [t.strip() for t in page.css("body *::text").getall() if t and t.strip()]
    except Exception:
        texts = []
    cleaned = [
        t for t in texts
        if len(t) > 20 and not _is_script_or_ad_junk(t)
    ]
    blob = re.sub(r"\s+", " ", " ".join(cleaned[:40])).strip()
    return blob[:max_len]


def _snippet_from_soup(soup, max_len: int = 500) -> str:
    """Extract snippet dari BeautifulSoup soup (untuk output Lightpanda HTML)."""
    try:
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "template", "iframe"]):
            tag.decompose()
        texts = [
            t.strip() for t in soup.stripped_strings
            if len(t.strip()) > 20 and not _is_script_or_ad_junk(t.strip())
        ]
        blob = re.sub(r"\s+", " ", " ".join(texts[:40])).strip()
        return blob[:max_len]
    except Exception:
        return ""


def _check_social_profile_fallback(domain_or_handle: str) -> dict[str, Any]:
    raw_name = re.sub(r"^https?://", "", (domain_or_handle or "").strip()).strip("/")
    q = f'"{raw_name}" site:instagram.com OR site:facebook.com OR site:tiktok.com OR site:tokopedia.com OR site:shopee.co.id'
    res = search_web_evidence(q, max_results=3)
    results = res.get("results") or []
    if results:
        top = results[0]
        # Hasil pertama aggregator/artikel global bukan bukti profil terkait.
        if _result_matches_query(q, top.get("url", ""), top.get("title", ""), top.get("snippet", "")):
            title = top.get("title", "")
            profile_url = top.get("url", "")
            return {
                "social_found": True,
                "title": title,
                "url": profile_url,
                "safe_flags": [f"Terdeteksi profil sosial media / toko online publik aktif: {title} ({profile_url})"],
            }
    return {"social_found": False}


def fetch_company_website(url_or_domain: str) -> dict[str, Any]:
    url = _normalize_url(url_or_domain)
    if not url:
        if re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", (url_or_domain or "").strip(), re.I):
            url = "https://" + url_or_domain.strip()
        else:
            return {
                "type": "website",
                "url": url_or_domain,
                "ok": False,
                "error": "URL/domain tidak valid",
                "risk_flags": [],
                "safe_flags": [],
            }

    try:
        from app.services.osint.lightpanda_client import lightpanda_fetch, is_lightpanda_available
        if is_lightpanda_available():
            # Pakai Lightpanda — render JS penuh
            lp_result = lightpanda_fetch(url, output="html", wait_ms=3000)
            if lp_result.get("ok") and lp_result.get("content"):
                soup_page = __import__("bs4").BeautifulSoup(lp_result["content"], "html.parser")
                title = lp_result.get("title", "") or ""
                if not title and soup_page.title:
                    title = soup_page.title.get_text(strip=True)
                snippet = _snippet_from_soup(soup_page)
                ok = True
                risk_flags: list[str] = []
                safe_flags: list[str] = []
                low = (title + " " + snippet).lower()
                if any(w in low for w in ("under construction", "domain for sale", "is for sale", "parked", "coming soon", "hugedomains", "godaddy", "sedo.com")):
                    risk_flags.append("Website terlihat parked / domain dijual / belum aktif.")
                if any(w in low for w in ("karir", "career", "lowongan", "about", "tentang", "kontak", "contact")):
                    safe_flags.append("Website memuat indikasi halaman perusahaan/karir.")
                return {
                    "type": "website",
                    "url": url,
                    "ok": ok,
                    "probe_status": "COMPLETED",
                    "website_status": "AVAILABLE",
                    "evidence_status": "FOUND",
                    "title": title[:200],
                    "snippet": snippet,
                    "risk_flags": risk_flags,
                    "safe_flags": safe_flags,
                    "engine": "lightpanda",
                }
            # Lightpanda gagal, fallback ke Scrapling
        # Fallback: Scrapling Fetcher
        page = Fetcher.get(url, stealthy_headers=True)
        status = getattr(page, "status", None) or getattr(page, "status_code", None)
        title = ""
        try:
            title = (page.css("title::text").get() or "").strip()
        except Exception:
            pass
        snippet = _snippet_from_page(page)
        ok = status is None or int(status) < 400
        risk_flags: list[str] = []
        safe_flags: list[str] = []
        low = (title + " " + snippet).lower()
        if any(
            w in low
            for w in (
                "under construction",
                "domain for sale",
                "is for sale",
                "parked",
                "coming soon",
                "hugedomains",
                "godaddy",
                "sedo.com",
            )
        ):
            risk_flags.append("Website terlihat parked / domain dijual / belum aktif.")
        if any(
            w in low
            for w in ("karir", "career", "lowongan", "about", "tentang", "kontak", "contact")
        ):
            safe_flags.append("Website memuat indikasi halaman perusahaan/karir.")
        return {
            "type": "website",
            "url": url,
            "ok": ok,
            "probe_status": "COMPLETED",
            "website_status": "AVAILABLE" if ok else "UNAVAILABLE",
            "evidence_status": "FOUND" if ok else "NO_RESULTS",
            "status": status,
            "title": title[:200],
            "snippet": snippet,
            "risk_flags": risk_flags,
            "safe_flags": safe_flags,
        }
    except Exception as exc:
        social = _check_social_profile_fallback(url_or_domain)
        if social.get("social_found"):
            return {
                "type": "website",
                "url": url,
                "ok": False,
                "probe_status": "COMPLETED",
                "website_status": "UNAVAILABLE",
                "evidence_status": "FOUND",
                "social_profile_found": True,
                "title": social.get("title"),
                "snippet": f"Web korporat tidak aktif, tetapi terdeteksi akun medsos/toko publik: {social.get('url')}",
                "risk_flags": [],
                "safe_flags": social.get("safe_flags", []),
            }
        return {
            "type": "website",
            "url": url,
            "ok": False,
            "probe_status": "UNAVAILABLE",
            "website_status": "UNAVAILABLE",
            "evidence_status": "NO_RESULTS",
            "error": str(exc),
            "risk_flags": ["Gagal membuka website perusahaan."],
            "safe_flags": [],
        }


def search_web_evidence(
    query: str,
    max_results: int = 5,
    *,
    skip_relevance_filter: bool = False,
) -> dict[str, Any]:
    """Search web evidence — SearXNG (primary) → Lightpanda (fallback).

    Args:
        query: Query pencarian
        max_results: Maksimal hasil yang dikembalikan
        skip_relevance_filter: True untuk social search — ambil semua hasil
            tanpa filter _result_matches_query (terlalu strict untuk platform
            search yang butuh semua hasil untuk domain filtering)
    """
    from app.services.osint.lightpanda_client import lightpanda_search, is_lightpanda_available

    q = (query or "").strip()
    if not q:
        return {
            "type": "search", "query": q, "results": [], "ok": False,
            "engine": "none", "status": "INVALID_QUERY", "error": "Query kosong.",
            "risk_flags": [],
        }

    results: list[dict[str, str]] = []
    engine_used = "none"
    search_status = "UNAVAILABLE"
    search_error = None

    # ── Primary: SearXNG (multi-engine aggregator) ──
    if is_searxng_available():
        sx_result = searxng_search(q, max_results=max_results * 2)
        if sx_result.get("ok") and sx_result.get("results"):
            candidate: list[dict[str, str]] = []
            for item in sx_result["results"]:
                url = item.get("url", "")
                title = (item.get("title") or "").strip()
                snippet = (item.get("snippet") or "").strip()
                if url and title:
                    candidate.append({
                        "title": title[:160],
                        "url": url,
                        "snippet": snippet[:240],
                        "source_type": _public_source_type(url, title, snippet),
                    })
            # Relevance guard (generik, bukan hardcode domain): bila engine
            # degraded (mis. hanya Bing yang aktif dan mengembalikan hasil tak
            # relevan), jangan terima mentah — filter dulu. Bila tersisa terlalu
            # sedikit, jatuh ke Lightpanda fallback di bawah.
            if skip_relevance_filter:
                relevant = candidate
            else:
                relevant = [
                    c for c in candidate
                    if _result_matches_query(q, c["url"], c["title"], c["snippet"])
                ]
            if relevant:
                engine_used = "searxng"
                search_status = FOUND
                results = relevant[:max_results]
            elif candidate:
                # Ada hasil tapi 0 relevan → engine degraded; biarkan kosong agar
                # fallback Lightpanda di bawah mencoba.
                search_error = (
                    f"SearXNG mengembalikan {len(candidate)} hasil tetapi 0 relevan "
                    "dengan query — kemungkinan engine degraded."
                )
        else:
            search_error = sx_result.get("error", "SearXNG tidak ada hasil.")

    # ── Fallback: Lightpanda (render DuckDuckGo/Bing/Google) ──
    if not results:
        if not is_lightpanda_available():
            search_error = "Lightpanda container tidak running. Jalankan: docker run -d --name lightpanda -p 127.0.0.1:9222:9222 lightpanda/browser:nightly"
        else:
            for eng in ("duckduckgo", "bing", "google"):
                search_result = lightpanda_search(q, max_results=max_results, engine=eng)
                if search_result.get("ok") and search_result.get("results"):
                    engine_used = search_result.get("engine", f"lightpanda-{eng}")
                    search_status = FOUND
                    for item in search_result["results"]:
                        url = item.get("url", "")
                        title = (item.get("title") or "").strip()
                        snippet = (item.get("snippet") or "").strip()
                        if url and title:
                            results.append({
                                "title": title[:160],
                                "url": url,
                                "snippet": snippet[:240],
                                "source_type": _public_source_type(url, title, snippet),
                            })
                    if results:
                        break
                else:
                    search_error = search_result.get("error", "Tidak ada hasil.")

    risk_flags = []
    # Extract target entity keywords from query (e.g. '"Kedai Nonggo"' -> ['kedai', 'nonggo'])
    quoted = re.findall(r'"([^"]+)"', q)
    target_words: list[str] = []
    if quoted:
        target_words = [w.lower() for w in quoted[0].split() if len(w) >= 3 and w.lower() not in ("pt", "cv", "ud", "pd", "tbk", "lowongan", "penipuan", "penipu", "scam")]
    else:
        target_words = [w.lower() for w in q.split()[:2] if len(w) >= 3 and w.lower() not in ("pt", "cv", "ud", "pd", "tbk", "lowongan", "penipuan", "penipu", "scam")]

    relevant_results = []
    for r in results:
        t_s = f"{r.get('title', '')} {r.get('snippet', '')}".lower()
        # Untuk social search: skip relevance filter — ambil semua hasil
        # karena platform filtering dilakukan di caller (_collect_social_searches)
        if not skip_relevance_filter:
            if not _result_matches_query(q, r.get("url", ""), r.get("title", ""), r.get("snippet", "")):
                continue
        relevant_results.append(r)

        if any(
            w in t_s
            for w in (
                "korban penipuan",
                "laporan penipuan",
                "loker palsu",
                "penipu loker",
                "scam loker",
                "terbukti menipu",
            )
        ) and not any(
            adv in t_s for adv in (
                "cara cek", "tips", "mengenali penipuan", "menghindari",
                "ciri-ciri", "10 ciri", "8 tips", "seputar",
                # boilerplate disclaimer portal loker — bukan laporan nyata
                "waspada terhadap segala penipuan",
                "hati hati juga apabila ada penawaran",
                "jangan memberikan jaminan uang berapapun",
                "pelamar tidak dipungut biaya",
            )
        ):
            risk_flags.append(
                "Hasil pencarian memuat indikasi laporan penipuan/loker palsu terkait query."
            )
            break

    return {
        "type": "search",
        "query": q,
        "ok": bool(results),
        "request_status": COMPLETED if engine_used != "none" else UNAVAILABLE,
        "engine": engine_used,
        "status": (
            FOUND if relevant_results else
            (NO_RELEVANT_RESULTS if results else search_status)
        ),
        "results": relevant_results[:max_results],
        "raw_result_count": len(results),
        "relevant_result_count": len(relevant_results),
        "error": search_error,
        "risk_flags": risk_flags,
    }


def _search_with_fallbacks(
    entities: dict,
    suffix: str,
    *,
    include_email: bool = True,
    max_results: int = 5,
) -> list[dict[str, Any]]:
    attempts = []
    candidates = build_search_queries(entities, include_email=include_email)
    for index, candidate in enumerate(candidates):
        result = search_web_evidence(
            f"{candidate['query']} {suffix}".strip(),
            max_results=max_results,
        )
        result["fallback_kind"] = candidate["kind"]
        result["fallback_index"] = index
        attempts.append(result)
        if result.get("status") == "FOUND" and result.get("relevant_result_count", 0) > 0:
            break
    return attempts


def _collect_social_searches(entities: dict, searches: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Klasifikasikan hasil intelligent_search (web.searches) yang SUDAH ADA
    menjadi bucket per-platform — TANPA request tambahan.

    Ini meniru cara pencarian manual: 1 query nama → langsung dapat IG/FB/Maps
    sekaligus. Versi lama menembak (5 platform × N query) ke SearXNG, yang
    memicu rate-limit/captcha engine. Karena intelligent_search sudah menemukan
    URL sosial dalam satu pencarian, kita cukup memfilternya di sini.
    """
    if not (entities.get("companies") or entities.get("emails")):
        return []

    from app.services.osint.search_intelligence import (
        resolve_entity,
        extract_location_tokens,
        rerank_results,
    )

    companies = entities.get("companies") or []
    addresses = entities.get("addresses") or []
    primary_company = str(companies[0]) if companies else ""
    primary_address = str(addresses[0]) if addresses else ""
    _entity = resolve_entity(primary_company) if primary_company else {}
    _loc_tokens = extract_location_tokens(primary_address) if primary_address else []

    # Kumpulkan semua hasil dari searches yang sudah ada (intelligent_search).
    all_results: list[dict[str, Any]] = []
    source_query = ""
    for s in searches or []:
        if not source_query:
            source_query = s.get("query") or ""
        for item in (s.get("results") or []):
            if isinstance(item, dict) and (item.get("url") or item.get("title")):
                all_results.append(item)

    searches_out: list[dict[str, Any]] = []
    for platform, domains in _SOCIAL_PLATFORM_DOMAINS.items():
        domain_filtered = [
            item for item in all_results
            if any(domain in (item.get("url") or "").lower() for domain in domains)
        ]
        platform_results = rerank_results(
            domain_filtered, _entity, _loc_tokens, max_results=15,
        ) if domain_filtered and _entity else domain_filtered

        if not platform_results:
            continue
        searches_out.append(
            {
                "platform": platform,
                "query": source_query or primary_company,
                "ok": True,
                "request_status": COMPLETED,
                "engine": "searxng-intelligent",
                "status": "FOUND",
                "results": platform_results,
                "raw_result_count": len(domain_filtered),
                "relevant_result_count": len(platform_results),
                "error": None,
                "fallback_kind": "intelligent_search_derived",
                "fallback_index": 0,
                "attempt_count": 1,
                "attempts": [],
            }
        )
    return searches_out


_FREE_WEB_DOMAINS = FREE_EMAIL_DOMAINS  


def _entity_tokens(companies: list, domains: list) -> list[str]:
    """Bangun token unik dari nama perusahaan + domain untuk relevance filter."""
    toks: set[str] = set()
    for comp in companies:
        c = (comp or "").strip()
        if not c:
            continue
        for m in re.findall(r"\(([^)]+)\)", c):
            m = m.strip().lower()
            if len(m) >= 3:
                toks.add(m)
        base = re.sub(r"\b(pt\.?|cv\.?|ud\.?|tbk\.?|lembaga|konsultasi|bimbingan|belajar|group|indonesia)\b", " ", c.lower())
        base = re.sub(r"\s+", " ", base).strip()
        if len(base) >= 4:
            toks.add(base)
        for w in re.split(r"[^\w]+", c.lower()):
            if len(w) >= 5 and w not in ("international", "solution", "sejahtera"):
                toks.add(w)
    for d in domains:
        host = d.split(".")[0].lower()
        if len(host) >= 4:
            toks.add(host)
    return sorted(toks, key=len, reverse=True)


def _is_generic_social_url(url: str) -> bool:
    """True jika URL adalah halaman generik platform (login/home), bukan profil spesifik."""
    ul = url.lower()
    generic_bits = ("/signin", "/signup", "/login", "/accounts/", "/home",
                    "/explore/", "/p/signin", "/?hl=", "sharer", "/share")
    return any(b in ul for b in generic_bits)


def _is_relevant(url: str, text: str, ent_tokens: list[str]) -> bool:
    """True jika hasil SERP relevan dengan entitas."""
    if not ent_tokens:
        return True
    hay = f"{url} {text}".lower().replace("-", "").replace("_", "").replace(".", "").replace(" ", "")
    for tok in ent_tokens:
        t = tok.replace(" ", "").replace(".", "")
        if t and t in hay:
            return True
    return False


def _has_maps_evidence(platform_evidence: dict) -> bool:
    """True jika platform_evidence mengandung hasil Google Maps."""
    if not platform_evidence or not platform_evidence.get("ok"):
        return False
    maps_data = platform_evidence.get("platforms", {}).get("google_maps", {})
    return maps_data.get("count", 0) > 0


def collect_web_evidence(entities: dict) -> dict[str, Any]:
    """
    Web evidence (Multi-engine) — dipangkas untuk latency:
    - skip fetch website domain gratisan (gmail.com dll)
    - max 3 query search (company presence + scam + email scam)
    """
    emails = entities.get("emails") or []
    urls = entities.get("urls") or []
    companies = entities.get("companies") or []
    addresses = entities.get("addresses") or []

    website_checks: list[dict[str, Any]] = []
    domains: list[str] = []

    seen_urls = set()
    # Hanya domain dari URL website nyata / email korporat (bukan Gmail).
    # URL form dan shortlink ditangani khusus oleh gform_inspections.
    for em in emails[:1]:
        d = _domain_from_email(em)
        if d and d not in _FREE_WEB_DOMAINS and d not in domains:
            domains.append(d)
    for u in urls[:2]:
        nu = _normalize_url(u)
        if nu:
            parsed = urlparse(nu)
            clean_host = parsed.netloc.lower().removeprefix("www.")
            clean_url = f"{parsed.scheme}://{clean_host}{parsed.path}".rstrip("/")
            if clean_url in seen_urls:
                continue
            seen_urls.add(clean_url)
            # Form/shortlink hanya diproses oleh gform_inspections di bawah;
            # jangan masukkan host-nya ke website/domain probe.
            if is_gform_url(clean_url):
                continue
            if clean_host and clean_host not in domains and clean_host not in _FREE_WEB_DOMAINS:
                domains.append(clean_host)
            website_checks.append(fetch_company_website(clean_url))

    for d in domains[:1]:
        if is_gform_url(d):
            continue
        if any(d.lower() in (c.get("url") or "").lower() for c in website_checks):
            continue
        website_checks.append(fetch_company_website(d))

    searches: list[dict[str, Any]] = []
    intelligence_signals: dict[str, Any] = {}
    if companies or emails:
        # ── Search Intelligence Layer: SATU pencarian pintar ────────────────
        # Hanya SATU query ditembak ke SearXNG (brand + lokasi). Hasilnya
        # dipakai bersama oleh web evidence, social, platform, dan deteksi scam
        # (via keyword di snippet) — menghindari rate-limit engine publik.
        from app.services.osint.search_intelligence import intelligent_search

        primary_company = str(companies[0]) if companies else ""
        primary_address = str(addresses[0] if addresses else "")

        si_result = intelligent_search(
            primary_company,
            primary_address,
            max_results=10,
        )
        if si_result.get("ok") and si_result.get("results"):
            intelligence_signals = si_result.get("signals", {})
            searches.append({
                "type": "search",
                "query": si_result.get("query_used", primary_company),
                "ok": True,
                "request_status": COMPLETED,
                "engine": "searxng-intelligent",
                "status": FOUND,
                "results": [
                    {
                        "title": r.get("title", "")[:160],
                        "url": r.get("url", ""),
                        "snippet": r.get("snippet", "")[:240],
                        "source_type": r.get("_category", "web"),
                        "_final_score": r.get("_final_score", 0),
                        "_entity_score": r.get("_entity_score", 0),
                    }
                    for r in si_result["results"]
                ],
                "raw_result_count": len(si_result.get("results", [])),
                "relevant_result_count": len(si_result.get("results", [])),
                "error": None,
                "risk_flags": [],
                "fallback_kind": "intelligent_search",
                "fallback_index": 0,
            })
        else:
            # Fallback ke query_builder loop hanya bila pencarian pintar gagal total
            searches.extend(_search_with_fallbacks(entities, "", include_email=False))

        # Catatan: query scam/email terpisah DIHILANGKAN untuk meminimalkan
        # request. Indikasi scam dideteksi dari snippet hasil pencarian pintar
        # (keyword "penipuan/scam/penipu") oleh risk-analyzer di prompt layer.
    elif domains:
        searches.append(search_web_evidence(f"{domains[0]} penipuan OR scam"))

    # Email: 1 query scam (cukup); skip local-part medsos (lambat + noise)
    # Email scam search dihilangkan — meminimalkan request ke SearXNG.
    # Indikasi scam pada email terdeteksi dari snippet pencarian pintar.

    social_searches = _collect_social_searches(entities, searches)

    # ── AI-powered platform evidence (Google Maps, Instagram, Facebook) ──
    # Mirip pencarian manual Google: cari nama bisnis → ketemu Maps, IG, FB, website
    platform_evidence: dict[str, Any] = {}
    if companies:
        from app.services.osint.platform_providers import collect_all_platform_evidence
        company_name = companies[0] if isinstance(companies[0], str) else str(companies[0])
        # Ambil lokasi dari alamat jika ada
        loc = ""
        if addresses:
            loc = addresses[0] if isinstance(addresses[0], str) else str(addresses[0])
        try:
            platform_evidence = collect_all_platform_evidence(company_name, loc)
        except Exception as exc:
            logger.warning("[Platform Evidence] gagal: %s", exc)
            platform_evidence = {"ok": False, "error": str(exc)}

    gform_inspections: list[dict[str, Any]] = []
    for u in urls[:2]:
        if is_gform_url(u):
            gform_inspections.append(inspect_gform(u))

    risk_flags: list[str] = []
    safe_flags: list[str] = []
    neutral_notes: list[str] = []
    for gf in gform_inspections:
        risk_flags.extend(gf.get("risk_flags") or [])
        safe_flags.extend(gf.get("safe_flags") or [])
        if gf.get("verification_note"):
            neutral_notes.append(gf["verification_note"])

    has_any_working_web_or_social = any(
        w.get("website_status") == "AVAILABLE"
        for w in website_checks
    ) or any(
        gf.get("is_gform") for gf in gform_inspections
    )
    for w in website_checks:
        risk_flags.extend(w.get("risk_flags") or [])
        safe_flags.extend(w.get("safe_flags") or [])
        if w.get("ok") is False and not has_any_working_web_or_social:
            risk_flags.append(f"Website tidak dapat diakses: {w.get('url')}")
    for s in searches:
        risk_flags.extend(s.get("risk_flags") or [])

    # Deteksi akun medsos & cross-reference lokasi dari hasil pencarian web
    found_social: list[str] = []
    total_public_results = 0
    source_counts: dict[str, int] = {}
    addresses = entities.get("addresses") or []
    companies = entities.get("companies") or []

    # ── Relevance filter: bangun token entitas ─────────
    _ENT_TOKENS = _entity_tokens(companies, domains)

    for s in searches:
        for r in s.get("results") or []:
            u = r.get("url") or ""
            title = r.get("title") or ""
            snippet = r.get("snippet") or ""
            combined_text = f"{title} {snippet}".lower()

            # Hanya hitung jejak digital yang RELEVAN dengan entitas — buang
            # hasil SERP acak/iklan yang tidak mengandung token entitas.
            if not _is_relevant(u, combined_text, _ENT_TOKENS):
                continue
            total_public_results += 1
            source_type = r.get("source_type") or _public_source_type(u, title, snippet)
            source_counts[source_type] = source_counts.get(source_type, 0) + 1

            # Cross-reference alamat: Cek apakah nama kota/jalan dari loker muncul di snippet pencarian bisnis
            for addr in addresses:
                # Ambil keyword lokasi kunci (misal: Kaliurang, Sleman, Umbulharjo, Yogyakarta)
                loc_words = [
                    w for w in re.split(r"[^\w]+", addr.lower())
                    if len(w) > 3 and w not in ("jalan", "gang", "nomor", "penempatan", "burger", "bangor")
                ]
                matched_words = [w for w in loc_words if w in combined_text]
                if len(set(matched_words)) >= 2 and companies:
                    safe_flags.append(
                        f"Location candidate match: hasil web memuat token lokasi '{', '.join(sorted(set(matched_words)))}'; belum membuktikan alamat exact."
                    )

            is_aggregator = any(token in combined_text or token in u.lower() for token in _SOCIAL_AGGREGATOR_TOKENS)
            if "instagram.com" in u and u not in found_social and not is_aggregator and _is_relevant(u, combined_text, _ENT_TOKENS) and not _is_generic_social_url(u):
                found_social.append(u)
                safe_flags.append(
                    f"Terdeteksi hasil Instagram publik (status resmi belum terverifikasi): {title} ({u})"
                )
            elif (
                any(soc in u for soc in ("facebook.com", "linkedin.com", "tiktok.com"))
                and u not in found_social
                and not is_aggregator
                and _is_relevant(u, combined_text, _ENT_TOKENS)
                and not _is_generic_social_url(u)
            ):
                found_social.append(u)
                safe_flags.append(f"Terdeteksi hasil media sosial publik (status resmi belum terverifikasi): {u}")

    source_labels = {
        "marketplace": "listing marketplace publik",
        "social_platform": "hasil platform sosial publik",
        "social_aggregator": "posting aggregator publik",
        "job_portal": "listing portal lowongan publik",
        "web": "hasil web publik",
    }
    for source_type, count in source_counts.items():
        safe_flags.append(f"Ditemukan {count} {source_labels.get(source_type, 'jejak publik')}.")

    # Gabungkan signals dari Search Intelligence Layer (jika ada)
    if intelligence_signals:
        risk_flags.extend(intelligence_signals.get("risk_flags") or [])
        safe_flags.extend(intelligence_signals.get("safe_flags") or [])

    def uniq(xs: list[str]) -> list[str]:
        return list(dict.fromkeys(xs))

    return {
        "enabled": True,
        # SearXNG multi-engine (primary) → Lightpanda headless browser (fallback)
        # Lightpanda render JS penuh untuk fetch website; Scrapling fallback terakhir.
        "engine": "searxng + lightpanda fallback",
        "websites": website_checks,
        "probe_status": "COMPLETED",
        "gform_inspections": gform_inspections,
        "searches": searches,
        "social_searches": social_searches,
        "evidence_counts": {
            "relevant_results": total_public_results,
            "by_source_type": source_counts,
            "successful_requests": sum(1 for s in searches if s.get("request_status") == COMPLETED),
            "empty_searches": sum(1 for s in searches if s.get("status") == "NO_RESULTS"),
            "no_relevant_searches": sum(1 for s in searches if s.get("status") == "NO_RELEVANT_RESULTS"),
            "unavailable_searches": sum(1 for s in searches if s.get("status") == "UNAVAILABLE"),
            # Search Intelligence Layer signals
            "digital_footprint": intelligence_signals.get("digital_footprint", "unknown"),
            "official_presence": intelligence_signals.get("official_presence", False),
            "marketplace_presence": intelligence_signals.get("marketplace_presence", False),
            "social_presence": intelligence_signals.get("social_presence", False),
            "maps_presence": intelligence_signals.get("maps_presence", False) or _has_maps_evidence(platform_evidence),
        },
        "risk_flags": uniq(risk_flags),
        "safe_flags": uniq(safe_flags),
        "neutral_notes": uniq(neutral_notes),
        # AI-powered platform evidence (Google Maps, Instagram, Facebook, dll)
        "platform_evidence": platform_evidence,
        # Search Intelligence Layer full signals (untuk prompt_builder & observability)
        "search_intelligence": intelligence_signals,
    }


async def run_web_evidence(entities: dict) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, collect_web_evidence, entities)
