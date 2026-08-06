"""
Web evidence via Scrapling:
1) Fetch website dari domain email / URL di loker
2) Search evidence lewat DuckDuckGo HTML
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

from scrapling.fetchers import Fetcher
from app.services.osint.gform_inspector import inspect_gform, is_gform_url

FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "yahoo.co.id",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "ymail.com",
    "icloud.com",
    "protonmail.com",
    "mail.com",
}


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


def _unwrap_ddg_href(href: str) -> str:
    if not href:
        return ""
    if "/RU=" in href:
        try:
            ru = href.split("/RU=")[1].split("/")[0]
            return unquote(ru)
        except Exception:
            pass
    if "uddg=" in href:
        try:
            return unquote(href.split("uddg=")[1].split("&")[0])
        except Exception:
            pass
    if "u=a1" in href:
        try:
            import base64

            b64 = href.split("u=a1")[1].split("&")[0]
            b64 += "=" * ((4 - len(b64) % 4) % 4)
            return base64.b64decode(b64).decode("utf-8", errors="ignore")
        except Exception:
            pass
    if href.startswith("//"):
        href = "https:" + href
    return href


def _snippet_from_page(page, max_len: int = 500) -> str:
    try:
        texts = [t.strip() for t in page.css("body *::text").getall() if t and t.strip()]
    except Exception:
        texts = []
    cleaned = [t for t in texts if len(t) > 20]
    blob = re.sub(r"\s+", " ", " ".join(cleaned[:40])).strip()
    return blob[:max_len]


def _check_social_profile_fallback(domain_or_handle: str) -> dict[str, Any]:
    raw_name = re.sub(r"^https?://", "", (domain_or_handle or "").strip()).strip("/")
    q = f'"{raw_name}" site:instagram.com OR site:facebook.com OR site:tiktok.com OR site:tokopedia.com OR site:shopee.co.id'
    res = search_web_evidence(q, max_results=3)
    results = res.get("results") or []
    if results:
        top = results[0]
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
                "ok": True,
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
            "error": str(exc),
            "risk_flags": ["Gagal membuka website perusahaan."],
            "safe_flags": [],
        }


def search_web_evidence(query: str, max_results: int = 5) -> dict[str, Any]:
    """
    Search web evidence multi-engine:
    1) DuckDuckGo HTML (timeout 2s via curl_cffi, no retry delay)
    2) Yahoo Search ID (id.search.yahoo.com)
    3) Bing Search (bing.com)
    """
    q = (query or "").strip()
    if not q:
        return {"type": "search", "query": q, "results": [], "ok": False, "risk_flags": []}

    results: list[dict[str, str]] = []
    engine_used = "none"

    # 1. Try DuckDuckGo — httpx dulu (lebih stabil SSL), curl_cffi sebagai fallback
    ddg_url = f"https://html.duckduckgo.com/html/?q={quote_plus(q)}"
    ddg_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
    }
    try:
        import httpx as _httpx
        from bs4 import BeautifulSoup

        with _httpx.Client(timeout=5.0, follow_redirects=True) as _hc:
            _r = _hc.get(ddg_url, headers=ddg_headers)
        if _r.status_code == 200:
            soup = BeautifulSoup(_r.text, "html.parser")
            for a in soup.select("a.result__a")[:max_results]:
                href = _unwrap_ddg_href(a.get("href", ""))
                title = a.text.strip()
                if href and title:
                    results.append({"title": title[:160], "url": href, "snippet": ""})
            snips = soup.select(".result__snippet")
            for i, sn in enumerate(snips[: len(results)]):
                results[i]["snippet"] = sn.text.strip()[:240]
            if results:
                engine_used = "duckduckgo"
    except Exception:
        # Fallback curl_cffi jika httpx juga gagal
        try:
            from bs4 import BeautifulSoup
            from curl_cffi import requests as cffi_req

            s = cffi_req.Session(impersonate="chrome120")
            r = s.get(ddg_url, timeout=4.0)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.select("a.result__a")[:max_results]:
                    href = _unwrap_ddg_href(a.get("href", ""))
                    title = a.text.strip()
                    if href and title:
                        results.append({"title": title[:160], "url": href, "snippet": ""})
                snips = soup.select(".result__snippet")
                for i, sn in enumerate(snips[: len(results)]):
                    results[i]["snippet"] = sn.text.strip()[:240]
                if results:
                    engine_used = "duckduckgo"
        except Exception:
            pass

    # 2. Fallback: Yahoo Search Indonesia
    if not results:
        try:
            from bs4 import BeautifulSoup
            from curl_cffi import requests as cffi_req

            s = cffi_req.Session(impersonate="chrome120")
            y_url = f"https://id.search.yahoo.com/search?p={quote_plus(q)}"
            r = s.get(y_url, timeout=4.0)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for div in soup.find_all("div", class_="algo"):
                    h3 = div.find("h3")
                    a = h3.find("a") if h3 else None
                    p = div.find("p") or div.find("div", class_="compText")
                    if a:
                        title = a.text.strip()
                        raw_href = a.get("href", "")
                        clean_url = _unwrap_ddg_href(raw_href)
                        snip = p.text.strip() if p else ""
                        if clean_url:
                            results.append(
                                {
                                    "title": title[:160],
                                    "url": clean_url,
                                    "snippet": snip[:240],
                                }
                            )
                if results:
                    engine_used = "yahoo_id"
        except Exception:
            pass

    # 3. Fallback: Bing Search
    if not results:
        try:
            from bs4 import BeautifulSoup
            from curl_cffi import requests as cffi_req

            s = cffi_req.Session(impersonate="chrome120")
            b_url = f"https://www.bing.com/search?q={quote_plus(q)}&mkt=id-ID"
            r = s.get(b_url, timeout=4.0)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for li in soup.select("li.b_algo"):
                    a = li.select_one("h2 a")
                    p = li.select_one("div.b_caption p, p")
                    if a:
                        title = a.text.strip()
                        clean_url = _unwrap_ddg_href(a.get("href", ""))
                        snip = p.text.strip() if p else ""
                        if clean_url:
                            results.append(
                                {
                                    "title": title[:160],
                                    "url": clean_url,
                                    "snippet": snip[:240],
                                }
                            )
                if results:
                    engine_used = "bing"
        except Exception:
            pass

    risk_flags = []
    # Extract target entity keywords from query (e.g. '"Kedai Nonggo"' -> ['kedai', 'nonggo'])
    quoted = re.findall(r'"([^"]+)"', q)
    target_words: list[str] = []
    if quoted:
        target_words = [w.lower() for w in quoted[0].split() if len(w) >= 3 and w.lower() not in ("pt", "cv", "ud", "pd", "tbk", "lowongan", "penipuan", "penipu", "scam")]
    else:
        target_words = [w.lower() for w in q.split()[:2] if len(w) >= 3 and w.lower() not in ("pt", "cv", "ud", "pd", "tbk", "lowongan", "penipuan", "penipu", "scam")]

    for r in results:
        t_s = f"{r.get('title', '')} {r.get('snippet', '')}".lower()
        # Jika hasil pencarian tidak menyebutkan kata kunci entitas sama sekali (artikel umum), abaikan
        if target_words and not any(tw in t_s for tw in target_words):
            continue

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
            adv in t_s for adv in ("cara cek", "tips", "mengenali penipuan", "menghindari", "ciri-ciri", "10 ciri", "8 tips", "seputar")
        ):
            risk_flags.append(
                "Hasil pencarian memuat indikasi laporan penipuan/loker palsu terkait query."
            )
            break

    return {
        "type": "search",
        "query": q,
        "ok": bool(results),
        "engine": engine_used,
        "results": results[:max_results],
        "risk_flags": risk_flags,
    }


_FREE_WEB_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "yahoo.co.id",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "ymail.com",
    "icloud.com",
    "protonmail.com",
    "mail.com",
}


def collect_web_evidence(entities: dict) -> dict[str, Any]:
    """
    Web evidence (Multi-engine) — dipangkas untuk latency:
    - skip fetch website domain gratisan (gmail.com dll)
    - max 3 query search (company presence + scam + email scam)
    """
    emails = entities.get("emails") or []
    urls = entities.get("urls") or []
    companies = entities.get("companies") or []

    website_checks: list[dict[str, Any]] = []
    domains: list[str] = []

    seen_urls = set()
    # Hanya domain dari URL poster / email korporat (bukan Gmail)
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
            if clean_host and clean_host not in domains and clean_host not in _FREE_WEB_DOMAINS:
                domains.append(clean_host)
            if not is_gform_url(clean_url):
                website_checks.append(fetch_company_website(clean_url))

    for d in domains[:1]:
        if any(d.lower() in (c.get("url") or "").lower() for c in website_checks):
            continue
        website_checks.append(fetch_company_website(d))

    # Search minimal berprioritas. Nama perusahaan diapit tanda kutip agar search
    # engine mencari frasa persis (mengurangi hasil generik/tak relevan).
    searches: list[dict[str, Any]] = []
    if companies:
        company = companies[0]
        clean_comp = re.sub(r"\s+cab(?:ang)?\s+.*$", "", company, flags=re.I).strip()
        searches.append(search_web_evidence(f'"{clean_comp}" instagram OR website OR toko'))
        searches.append(search_web_evidence(f'"{clean_comp}" penipu OR scam'))
    elif domains:
        searches.append(search_web_evidence(f'"{domains[0]}" penipuan OR scam'))

    # Email: 1 query scam (cukup); skip local-part medsos (lambat + noise)
    for em in emails[:1]:
        em_clean = (em or "").strip().lower()
        if not em_clean or "@" not in em_clean:
            continue
        searches.append(
            search_web_evidence(f'"{em_clean}" penipu OR scam OR penipuan OR loker')
        )

    gform_inspections: list[dict[str, Any]] = []
    for u in urls[:2]:
        if is_gform_url(u):
            gform_inspections.append(inspect_gform(u))

    risk_flags: list[str] = []
    safe_flags: list[str] = []
    for gf in gform_inspections:
        risk_flags.extend(gf.get("risk_flags") or [])
        safe_flags.extend(gf.get("safe_flags") or [])

    has_any_working_web_or_social = any(w.get("ok") for w in website_checks) or any(
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
    addresses = entities.get("addresses") or []
    companies = entities.get("companies") or []

    # ── Relevance filter: bangun token entitas agar hasil SERP yang tidak
    # terkait (mis. situs acak yang kebetulan muncul) TIDAK dihitung sebagai
    # jejak digital. Fleksibel: cocok via nama perusahaan, brand dalam kurung,
    # domain website resmi, atau potongan kata kunci nama yang khas. ─────────
    def _entity_tokens() -> list[str]:
        toks: set[str] = set()
        for comp in companies:
            c = (comp or "").strip()
            if not c:
                continue
            # brand dalam kurung, mis. "PT. X (PT. VIS)" → "pt. vis", "vis"
            for m in re.findall(r"\(([^)]+)\)", c):
                m = m.strip().lower()
                if len(m) >= 3:
                    toks.add(m)
            # nama lengkap & bentuk bersih (tanpa PT/CV/UD/lembaga dsb.)
            base = re.sub(r"\b(pt\.?|cv\.?|ud\.?|tbk\.?|lembaga|konsultasi|bimbingan|belajar|group|indonesia)\b", " ", c.lower())
            base = re.sub(r"\s+", " ", base).strip()
            if len(base) >= 4:
                toks.add(base)
            # kata kunci khas (>=5 huruf) dari nama
            for w in re.split(r"[^\w]+", c.lower()):
                if len(w) >= 5 and w not in ("international", "solution", "sejahtera"):
                    toks.add(w)
        # domain website resmi (indonesiacollege.co.id → "indonesiacollege")
        for d in domains:
            host = d.split(".")[0].lower()
            if len(host) >= 4:
                toks.add(host)
        return sorted(toks, key=len, reverse=True)

    _ENT_TOKENS = _entity_tokens()

    def _is_generic_social_url(url: str) -> bool:
        """True jika URL adalah halaman generik platform (login/signup/home), bukan
        profil/post spesifik entitas — mis. instagram.com/p/signin, /accounts/login."""
        ul = url.lower()
        generic_bits = ("/signin", "/signup", "/login", "/accounts/", "/home",
                        "/explore/", "/p/signin", "/?hl=", "sharer", "/share")
        return any(b in ul for b in generic_bits)

    def _is_relevant(url: str, text: str) -> bool:
        """True jika hasil SERP relevan dgn entitas (url atau teks mengandung token)."""
        if not _ENT_TOKENS:
            return True  # tak ada entitas → jangan difilter (biarkan)
        hay = f"{url} {text}".lower().replace("-", "").replace("_", "").replace(".", "").replace(" ", "")
        for tok in _ENT_TOKENS:
            t = tok.replace(" ", "").replace(".", "")
            if t and t in hay:
                return True
        return False

    for s in searches:
        for r in s.get("results") or []:
            u = r.get("url") or ""
            title = r.get("title") or ""
            snippet = r.get("snippet") or ""
            combined_text = f"{title} {snippet}".lower()

            # Hanya hitung jejak digital yang RELEVAN dengan entitas — buang
            # hasil SERP acak/iklan yang tidak mengandung token entitas.
            if not _is_relevant(u, combined_text):
                continue
            total_public_results += 1

            # Cross-reference alamat: Cek apakah nama kota/jalan dari loker muncul di snippet pencarian bisnis
            for addr in addresses:
                # Ambil keyword lokasi kunci (misal: Kaliurang, Sleman, Umbulharjo, Yogyakarta)
                loc_words = [w for w in re.split(r"[^\w]+", addr.lower()) if len(w) > 3 and w not in ("jalan", "gang", "nomor", "penempatan")]
                matched_words = [w for w in loc_words if w in combined_text]
                if len(matched_words) >= 2 and companies:
                    safe_flags.append(
                        f"✅ Location Match: Pencarian web publik untuk '{companies[0]}' mengonfirmasi lokasi '{', '.join(matched_words)}'."
                    )

            if "instagram.com" in u and u not in found_social and _is_relevant(u, combined_text) and not _is_generic_social_url(u):
                found_social.append(u)
                safe_flags.append(
                    f"Terdeteksi profil/post Instagram publik aktif: {title} ({u})"
                )
            elif (
                any(soc in u for soc in ("facebook.com", "linkedin.com", "tiktok.com"))
                and u not in found_social
                and _is_relevant(u, combined_text)
                and not _is_generic_social_url(u)
            ):
                found_social.append(u)
                safe_flags.append(f"Terdeteksi akun media sosial publik: {u}")

    if total_public_results >= 1:
        safe_flags.append(
            f"Ditemukan {total_public_results} jejak digital publik di web (portal lowongan/direktori)."
        )

    def uniq(xs: list[str]) -> list[str]:
        seen = set()
        out = []
        for x in xs:
            if x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

    return {
        "enabled": True,
        # Jujur: web search memakai multi-engine (DuckDuckGo/Yahoo/Bing via
        # curl_cffi+BeautifulSoup); Scrapling dipakai untuk fetch halaman web.
        "engine": "multi-engine (DDG/Yahoo/Bing) + Scrapling fetch",
        "websites": website_checks,
        "gform_inspections": gform_inspections,
        "searches": searches,
        "risk_flags": uniq(risk_flags),
        "safe_flags": uniq(safe_flags),
    }


async def run_web_evidence(entities: dict) -> dict[str, Any]:
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, collect_web_evidence, entities)
