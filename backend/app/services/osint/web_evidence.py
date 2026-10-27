import re
import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

from scrapling.fetchers import Fetcher
from app.services.osint.gform_inspector import inspect_gform, is_gform_url
from app.services.constants import FREE_EMAIL_DOMAINS
from app.services.osint.query_builder import build_search_queries
from app.services.osint.searxng_client import searxng_search, is_searxng_available
from app.services.status_contract import COMPLETED, FOUND, NO_RESULTS, NO_RELEVANT_RESULTS, UNAVAILABLE
from app.services.url_guard import resolve_public_url
from app.services.osint.search_intelligence import ordered_match_count

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
    "linktree": ("linktr.ee",),
}

def _url_matches_domains(url: str, target_domains: tuple[str, ...] | list[str]) -> bool:
    try:
        from urllib.parse import urlparse
        host = urlparse(url or "").netloc.lower().removeprefix("www.")
        return any(host == d or host.endswith("." + d) for d in target_domains)
    except Exception:
        return False


def _public_source_type(url: str, title: str = "", snippet: str = "") -> str:
    url_title = f"{url} {title}".lower()
    if any(domain in url.lower() for domain in ("tokopedia.com", "shopee.co.id")):
        return "marketplace"
    if any(domain in url.lower() for domain in ("loker", "jobstreet", "glints", "kalibrr", "linkedin.com/jobs", "karir")):
        return "job_portal"
    if any(token in url_title for token in _SOCIAL_AGGREGATOR_TOKENS):
        return "social_aggregator"
    if _url_matches_domains(url, ("instagram.com", "facebook.com", "tiktok.com", "threads.net", "threads.com", "x.com", "twitter.com")):
        return "social_platform"
    return "web"

def _result_matches_query(query: str, url: str, title: str, snippet: str) -> bool:
    hay = re.sub(r"[^a-z0-9]+", " ", f"{url} {title} {snippet}".lower()).strip()
    hay_compact = hay.replace(" ", "")
    emails = re.findall(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", query.lower())
    if emails:
        return any(email in f"{url} {title} {snippet}".lower() for email in emails)
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
        hay_words = hay.split()
        matched = {token for token in set(tokens) if token in hay_words}
        if len(tokens) == 1 and len(matched) == 1:
            if re.search(rf"(?:^|[./@_-]){re.escape(tokens[0])}(?:$|[./@_-])", url.lower()):
                return True
            continue
        # Minimal dua kata cocok, dan kata yang cocok harus berurutan seperti di query:
        # nama dengan kata sama tetapi tertukar adalah entitas lain.
        if len(tokens) >= 2 and len(matched) >= 2:
            swapped = False
            for f in (url, title, snippet):
                words = re.sub(r"[^a-z0-9]+", " ", f.lower()).split()
                present = [t for t in dict.fromkeys(tokens) if t in words]
                if len(present) >= 2 and ordered_match_count(tokens, words) < len(present):
                    swapped = True
                    break
            if not swapped:
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
    # Cuplikan berisi selector CSS (mis. ".elementor-26052 .elementor-element > .x"), bukan teks halaman.
    if re.search(r"(?:\.[\w-]+\s*(?:>|,|\s)\s*){4,}|:not\(|var\(--|\{[^}]*:[^}]*;", t):
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


_CHALLENGE_MARKERS = ("just a moment", "attention required", "_cf_chl", "cf-browser-verification", "enable javascript and cookies")


def _host_resolves(url: str) -> bool:
    import socket
    try:
        socket.getaddrinfo(urlparse(url).hostname or "", None)
        return True
    except socket.gaierror:
        return False


def fetch_company_website(url_or_domain: str) -> dict[str, Any]:
    """Buka situs yang disebut lowongan.

    Status situs:
    - AVAILABLE: halaman terbuka (< 400).
    - HTTP_ERROR: server menjawab 4xx/5xx (bukan tantangan anti-bot). Situs mati: sinyal risiko.
    - NOT_FOUND: nama domain tidak terdaftar di DNS. Sinyal risiko.
    - BLOCKED: halaman tantangan anti-bot (Cloudflare dsb.). Netral: situs mungkin aktif.
    - UNREACHABLE: timeout/gangguan dari sisi Verifin. Netral.
    - SKIPPED: alamat internal/privat, tidak dibuka (perlindungan SSRF).
    """
    url = _normalize_url(url_or_domain)
    if not url:
        if re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", (url_or_domain or "").strip(), re.I):
            url = "https://" + url_or_domain.strip()
        else:
            return {
                "type": "website",
                "url": url_or_domain,
                "ok": False,
                "website_status": "SKIPPED",
                "error": "URL/domain tidak valid",
                "risk_flags": [],
                "safe_flags": [],
            }

    base = {"type": "website", "url": url, "risk_flags": [], "safe_flags": []}
    try:
        final_url = resolve_public_url(url)
    except ValueError as exc:
        return {
            **base,
            "ok": False,
            "probe_status": "SKIPPED",
            "website_status": "SKIPPED",
            "evidence_status": NO_RESULTS,
            "error": str(exc),
            "neutral_notes": ["Tautan menuju alamat internal atau privat, tidak dibuka sistem."],
        }

    try:
        page = Fetcher.get(final_url, stealthy_headers=True, follow_redirects=False, timeout=12)
        status = getattr(page, "status", None) or getattr(page, "status_code", None)
        title = ""
        try:
            title = (page.css("title::text").get() or "").strip()
        except Exception:
            pass
        snippet = _snippet_from_page(page)
        low = (title + " " + snippet).lower()
        try:
            body_low = str(getattr(page, "html_content", "") or "")[:4000].lower()
        except Exception:
            body_low = ""
        if any(m in low or m in body_low for m in _CHALLENGE_MARKERS):
            return {
                **base,
                "ok": None,
                "probe_status": "COMPLETED",
                "website_status": "BLOCKED",
                "evidence_status": NO_RESULTS,
                "status": status,
                "title": "",
                "snippet": "",
                "neutral_notes": ["Situs memakai perlindungan anti-bot sehingga isinya tidak bisa dibaca otomatis; ini bukan tanda situs mati."],
            }
        ok = status is None or int(status) < 400
        risk_flags: list[str] = []
        safe_flags: list[str] = []
        if ok and any(
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
        if ok and any(
            w in low
            for w in ("karir", "career", "lowongan", "about", "tentang", "kontak", "contact")
        ):
            safe_flags.append("Website memuat indikasi halaman perusahaan/karir.")
        fraud_matches = _fraud_site_matches(title, snippet) if ok else []
        if fraud_matches:
            risk_flags.append(
                "Isi website memuat pola penipuan tugas/komisi: " + ", ".join(fraud_matches[:3])
            )
        if not ok:
            risk_flags.append(f"Website menjawab HTTP {status}.")
        return {
            **base,
            "ok": ok,
            "probe_status": "COMPLETED",
            "website_status": "AVAILABLE" if ok else "HTTP_ERROR",
            "evidence_status": FOUND if ok else NO_RESULTS,
            "status": status,
            "title": title[:200] if ok else "",
            "snippet": snippet if ok else "",
            "risk_flags": risk_flags,
            "safe_flags": safe_flags,
            "fraud_content_matches": fraud_matches,
        }
    except Exception as exc:
        resolves = _host_resolves(final_url)
        social = _check_social_profile_fallback(url_or_domain)
        if social.get("social_found"):
            return {
                **base,
                "ok": False,
                "probe_status": "COMPLETED",
                "website_status": "UNREACHABLE" if resolves else "NOT_FOUND",
                "evidence_status": "FOUND",
                "social_profile_found": True,
                "title": social.get("title"),
                "snippet": f"Web korporat tidak terbuka, tetapi terdeteksi akun medsos/toko publik: {social.get('url')}",
                "safe_flags": social.get("safe_flags", []),
            }
        if not resolves:
            return {
                **base,
                "ok": False,
                "probe_status": "COMPLETED",
                "website_status": "NOT_FOUND",
                "evidence_status": NO_RESULTS,
                "error": str(exc),
                "risk_flags": ["Nama domain website tidak terdaftar (DNS tidak ditemukan)."],
            }
        return {
            **base,
            "ok": False,
            "probe_status": UNAVAILABLE,
            "website_status": "UNREACHABLE",
            "evidence_status": NO_RESULTS,
            "error": str(exc),
            "neutral_notes": ["Situs tidak bisa dibuka dari server Verifin saat pemeriksaan (timeout/gangguan jaringan)."],
        }


def search_web_evidence(
    query: str,
    max_results: int = 5,
    *,
    skip_relevance_filter: bool = False,
) -> dict[str, Any]:
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
                engine_used = "searxng"
                search_status = NO_RELEVANT_RESULTS
                search_error = None
        elif sx_result.get("empty"):
            engine_used = "searxng"
            search_status = NO_RESULTS
        else:
            search_error = sx_result.get("error", "SearXNG tidak ada hasil.")
    else:
        search_error = "Mesin pencari (SearXNG) tidak dapat dihubungi."
    if not results and not search_error and engine_used == "none":
        search_error = "Pencarian tidak mengembalikan hasil."

    risk_flags = []
    relevant_results = []
    for r in results:
        t_s = f"{r.get('title', '')} {r.get('snippet', '')}".lower()
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
        "status": FOUND if relevant_results else search_status,
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
            if _url_matches_domains(item.get("url") or "", domains)
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
    ul = url.lower()
    generic_bits = ("/signin", "/signup", "/login", "/accounts/", "/home",
                    "/explore/", "/p/signin", "/?hl=", "sharer", "/share")
    return any(b in ul for b in generic_bits)


def _is_relevant(url: str, text: str, ent_tokens: list[str]) -> bool:
    if not ent_tokens:
        return True
    hay = f"{url} {text}".lower().replace("-", "").replace("_", "").replace(".", "").replace(" ", "")
    for tok in ent_tokens:
        t = tok.replace(" ", "").replace(".", "")
        if t and t in hay:
            return True
    return False


def _has_maps_evidence(platform_evidence: dict) -> bool:
    if not platform_evidence or not platform_evidence.get("ok"):
        return False
    maps_data = platform_evidence.get("platforms", {}).get("google_maps", {})
    return maps_data.get("count", 0) > 0


_OPEN_REGISTRATION_TLDS = (
    ".my.id",
    ".web.id",
    ".biz.id",
    ".store",
    ".boutique",
    ".shop",
    ".online",
    ".site",
    ".xyz",
    ".top",
)

_OPEN_REGISTRATION_HOSTS = (
    "blogspot.com",
    "blogspot.co.id",
    "wixsite.com",
    "wordpress.com",
    "github.io",
    "vercel.app",
    "netlify.app",
    "web.app",
    "firebaseapp.com",
    "weebly.com",
    "000webhostapp.com",
    "r2.dev",
)

# Isi website penipuan rekrutmen (masukan LokerJogja.id): halaman "Akun Kerja", tugas/komisi,
# deposit, lalu tautan Telegram. Satu frasa kuat sudah cukup; frasa lemah butuh dua.
_STRONG_SITE_SCAM_PHRASES = (
    "akun kerja",
    "selesaikan tugas",
    "isi saldo",
    "deposit",
    "rajin menonton",
    "tugas komisi",
)
_WEAK_SITE_SCAM_PHRASES = (
    "komisi",
    "tugas harian",
    "tugas vip",
    "raih keuntungan",
    "t.me/",
    "telegram.me/",
)

# Kota besar Indonesia untuk mendeteksi profil usaha yang ditemukan di kota lain dari alamat
# poster (kasus Roemah Boenga: toko asli di Aceh, poster menulis Jakarta).
_KNOWN_CITIES = (
    "jakarta", "bogor", "depok", "tangerang", "bekasi", "bandung", "semarang", "surabaya",
    "yogyakarta", "sleman", "bantul", "magelang", "solo", "surakarta", "malang", "denpasar",
    "medan", "palembang", "pekanbaru", "padang", "banda aceh", "aceh", "lampung",
    "balikpapan", "samarinda", "banjarmasin", "pontianak", "makassar", "manado", "kendari",
    "ambon", "jayapura", "mataram", "kupang", "cirebon", "tasikmalaya", "purwokerto",
    "tegal", "pekalongan", "kudus", "jember", "kediri", "madiun", "sidoarjo", "gresik",
    "serang", "cilegon", "batam", "bandar lampung", "jambi", "bengkulu", "palangkaraya",
)


def is_open_registration_domain(host: str) -> str | None:
    """Domain yang bisa didaftarkan siapa saja tanpa verifikasi badan usaha."""
    host = (host or "").lower().removeprefix("www.")
    if not host:
        return None
    for suffix in _OPEN_REGISTRATION_TLDS:
        if host.endswith(suffix) and host.count(".") >= 2:
            return host
    for free_host in _OPEN_REGISTRATION_HOSTS:
        # Domain induknya sendiri (mis. vercel.app) bukan situs milik pengguna.
        if host.endswith("." + free_host):
            return host
    return None


def _fraud_site_matches(title: str, snippet: str) -> list[str]:
    low = f"{title} {snippet}".lower()
    strong = [p for p in _STRONG_SITE_SCAM_PHRASES if p in low]
    weak = [p for p in _WEAK_SITE_SCAM_PHRASES if p in low]
    if strong:
        return strong + weak[:2]
    if len(weak) >= 2:
        return weak
    return []


def _cities_in(text: str) -> set[str]:
    low = f" {(text or '').lower()} "
    found = set()
    for city in _KNOWN_CITIES:
        if f" {city} " in low or f" {city}," in low or f"kota {city}" in low or f"kabupaten {city}" in low:
            found.add(city)
    # "banda aceh" juga cocok dengan "aceh"; simpan nama kota terpanjang saja.
    return {city for city in found if not any(city != other and f" {city} " in f" {other} " for other in found)}


def collect_web_evidence(entities: dict) -> dict[str, Any]:
    emails = entities.get("emails") or []
    urls = entities.get("urls") or []
    companies = entities.get("companies") or []
    addresses = entities.get("addresses") or []

    website_checks: list[dict[str, Any]] = []
    domains: list[str] = []

    seen_urls = set()
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
            if is_gform_url(clean_url):
                continue
            _ALL_SOCIAL_HOSTS = {"instagram.com", "facebook.com", "fb.com", "tiktok.com", "threads.net", "threads.com", "x.com", "twitter.com", "linkedin.com", "youtube.com", "wa.me", "api.whatsapp.com", "chat.whatsapp.com", "t.me"}
            if clean_host and clean_host not in domains and clean_host not in _FREE_WEB_DOMAINS and clean_host not in _ALL_SOCIAL_HOSTS:
                domains.append(clean_host)
            if clean_host in {"wa.me", "api.whatsapp.com", "chat.whatsapp.com", "t.me"}:
                continue  # tautan chat, bukan situs perusahaan
            website_checks.append(fetch_company_website(clean_url))

    for d in domains[:1]:
        if is_gform_url(d):
            continue
        if any(d.lower() in (c.get("url") or "").lower() for c in website_checks):
            continue
        website_checks.append(fetch_company_website(d))

    searches: list[dict[str, Any]] = []
    intelligence_signals: dict[str, Any] = {}
    cached_si_results: list[dict[str, Any]] | None = None
    if companies or emails:
        from app.services.osint.search_intelligence import intelligent_search
        from app.services.ner import primary_employer_name

        primary_company = primary_employer_name(companies)
        # Tanpa alamat, kota penempatan tetap dipakai sebagai konteks agar nama pendek ("PACC")
        # tidak tertukar dengan organisasi lain bernama sama di luar negeri.
        primary_address = str(addresses[0] if addresses else (entities.get("location_candidates") or [""])[0])

        si_result = intelligent_search(
            primary_company,
            primary_address,
            max_results=10,
            official_domains=tuple(domains),
        )
        if si_result.get("ok") and si_result.get("results"):
            cached_si_results = si_result.get("results")
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
            searches.extend(_search_with_fallbacks(entities, "", include_email=False))

    elif domains:
        searches.append(search_web_evidence(f"{domains[0]} penipuan OR scam"))

    social_searches = _collect_social_searches(entities, searches)

    scam_check: dict[str, Any] = {"status": "SKIPPED", "query": "", "results": [], "warnings": 0}
    if companies:
        from app.services.osint.search_intelligence import scam_report_search
        try:
            scam_check = scam_report_search(str(companies[0]))
        except Exception as exc:
            logger.warning("[ScamCheck] gagal: %s", exc)
            scam_check = {"status": "UNAVAILABLE", "query": "", "results": [], "warnings": 0, "error": str(exc)}

    platform_evidence: dict[str, Any] = {}
    if companies:
        from app.services.osint.platform_providers import collect_all_platform_evidence
        company_name = companies[0] if isinstance(companies[0], str) else str(companies[0])
        loc = ""
        if addresses:
            loc = addresses[0] if isinstance(addresses[0], str) else str(addresses[0])
        try:
            platform_evidence = collect_all_platform_evidence(company_name, loc, search_results=cached_si_results)
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
        neutral_notes.extend(w.get("neutral_notes") or [])
        if w.get("website_status") in ("NOT_FOUND", "HTTP_ERROR") and not has_any_working_web_or_social:
            risk_flags.append(f"Website tidak dapat diakses: {w.get('url')}")
    for s in searches:
        risk_flags.extend(s.get("risk_flags") or [])

    found_social: list[str] = []
    total_public_results = 0
    source_counts: dict[str, int] = {}
    addresses = entities.get("addresses") or []
    companies = entities.get("companies") or []

    _ENT_TOKENS = _entity_tokens(companies, domains)
    location_hits = 0

    for s in searches:
        for r in s.get("results") or []:
            u = r.get("url") or ""
            title = r.get("title") or ""
            snippet = r.get("snippet") or ""
            combined_text = f"{title} {snippet}".lower()
            if not _is_relevant(u, combined_text, _ENT_TOKENS):
                continue
            total_public_results += 1
            source_type = r.get("source_type") or _public_source_type(u, title, snippet)
            source_counts[source_type] = source_counts.get(source_type, 0) + 1
            for addr in addresses:
                loc_words = [
                    w for w in re.split(r"[^\w]+", addr.lower())
                    if len(w) > 3 and w not in ("jalan", "gang", "nomor", "penempatan", "burger", "bangor")
                ]
                matched_words = [w for w in loc_words if w in combined_text]
                if len(set(matched_words)) >= 2 and companies:
                    location_hits += 1
                    break

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

    # Kecocokan nama jalan/wilayah bukan sinyal aman: penipu sering memakai alamat kantor
    # pusat asli perusahaan yang dicatut. Dicatat sekali sebagai keterangan netral.
    if location_hits:
        neutral_notes.append(
            f"Nama jalan/wilayah di lowongan juga muncul di {location_hits} hasil web; "
            "nomor bangunan belum dipastikan."
        )
    if total_public_results:
        safe_flags.append(f"Pencarian web menemukan {total_public_results} hasil yang menyebut perusahaan ini.")
    if intelligence_signals:
        risk_flags.extend(intelligence_signals.get("risk_flags") or [])
        safe_flags.extend(intelligence_signals.get("safe_flags") or [])

    # R5: isi website lamaran yang memuat pola penipuan tugas/komisi.
    fraud_site_content: dict[str, Any] = {}
    for w in website_checks:
        matches = w.get("fraud_content_matches") or []
        if matches:
            fraud_site_content = {"url": w.get("url"), "matches": matches}
            break

    # R4: domain bebas daftar yang dipakai atas nama badan usaha/merek.
    open_registration_domain: dict[str, Any] = {}
    legal_form = re.compile(r"\b(?:pt|cv|ud|pd|yayasan|koperasi|persero|tbk)\b\.?", re.I)
    brand_claim = re.compile(r"\b(?:bumn|persero|tbk)\b", re.I)
    company_forms = [str(c) for c in companies if c]
    claims_business = any(legal_form.search(c) or brand_claim.search(c) for c in company_forms)
    for w in website_checks:
        host = urlparse(w.get("url") or "").netloc
        matched = is_open_registration_domain(host)
        if not matched:
            continue
        label = host.split(".")[0].replace("-", "")
        token_hit = any(
            len(tok) >= 4 and tok in label
            for c in company_forms
            for tok in re.findall(r"[a-z0-9]+", c.lower())
            if len(re.findall(r"[a-z0-9]+", c.lower())) >= 2
        )
        if claims_business or token_hit:
            open_registration_domain = {"domain": matched, "url": w.get("url")}
            risk_flags.append(
                f"Domain `{matched}` bisa didaftarkan siapa saja tanpa verifikasi badan usaha, "
                "padahal lowongan mengatasnamakan badan usaha/merek."
            )
            break

    # R6: profil publik usaha dengan nama sama berada di kota lain dari alamat poster.
    location_mismatch: dict[str, Any] = {}
    posting_city = ""
    for source in list(addresses or []) + list(entities.get("location_candidates") or []):
        cities = _cities_in(str(source))
        if cities:
            posting_city = sorted(cities)[0]
            break
    if posting_city and companies:
        company_tokens = {
            t for c in company_forms
            for t in re.findall(r"[a-z0-9]+", c.lower())
            if len(t) >= 4
        }
        for s in searches:
            for r in s.get("results") or []:
                blob = f"{r.get('title') or ''} {r.get('snippet') or ''}".lower()
                if len(company_tokens & set(re.findall(r"[a-z0-9]+", blob))) < min(2, len(company_tokens) or 2):
                    continue
                other_cities = _cities_in(blob) - {posting_city}
                if other_cities:
                    profile_city = sorted(other_cities)[0]
                    location_mismatch = {
                        "posting_city": posting_city,
                        "profile_city": profile_city,
                        "source_url": r.get("url"),
                    }
                    neutral_notes.append(
                        f"Profil publik dengan nama sama ditemukan di {profile_city}, sedangkan lowongan menulis "
                        f"{posting_city}. Ini petunjuk, bukan bukti penipuan: usaha bisa punya cabang."
                    )
                    break
            if location_mismatch:
                break

    def uniq(xs: list[str]) -> list[str]:
        return list(dict.fromkeys(xs))

    return {
        "enabled": True,
        "engine": "searxng",
        "websites": website_checks,
        "probe_status": "COMPLETED",
        "gform_inspections": gform_inspections,
        "searches": searches,
        "scam_check": scam_check,
        "social_searches": social_searches,
        "evidence_counts": {
            "relevant_results": total_public_results,
            "by_source_type": source_counts,
            "successful_requests": sum(1 for s in searches if s.get("request_status") == COMPLETED),
            "empty_searches": sum(1 for s in searches if s.get("status") == NO_RESULTS),
            "no_relevant_searches": sum(1 for s in searches if s.get("status") == "NO_RELEVANT_RESULTS"),
            "unavailable_searches": sum(1 for s in searches if s.get("status") == "UNAVAILABLE"),
            "scam_warnings": scam_check.get("warnings", 0),
            "digital_footprint": intelligence_signals.get("digital_footprint", "unknown"),
            "official_presence": intelligence_signals.get("official_presence", False),
            "marketplace_presence": intelligence_signals.get("marketplace_presence", False),
            "social_presence": intelligence_signals.get("social_presence", False),
            "maps_presence": intelligence_signals.get("maps_presence", False) or _has_maps_evidence(platform_evidence),
        },
        "risk_flags": uniq(risk_flags),
        "safe_flags": uniq(safe_flags),
        "neutral_notes": uniq(neutral_notes),
        "platform_evidence": platform_evidence,
        "search_intelligence": intelligence_signals,
        "fraud_site_content": fraud_site_content,
        "open_registration_domain": open_registration_domain,
        "location_mismatch": location_mismatch,
    }


async def run_web_evidence(entities: dict) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, collect_web_evidence, entities)
