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
        return href
    if href.startswith("//"):
        href = "https:" + href
    try:
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        if "uddg" in qs and qs["uddg"]:
            return unquote(qs["uddg"][0])
    except Exception:
        pass
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
    q = (query or "").strip()
    if not q:
        return {"type": "search", "query": q, "results": [], "ok": False, "risk_flags": []}

    url = f"https://html.duckduckgo.com/html/?q={quote_plus(q)}"
    results: list[dict[str, str]] = []
    try:
        page = Fetcher.get(url, stealthy_headers=True)
        try:
            link_items = list(page.css("a.result__a") or [])
        except Exception:
            link_items = []

        for a in link_items[:max_results]:
            try:
                href = None
                if hasattr(a, "attrib"):
                    href = a.attrib.get("href")
                if not href:
                    try:
                        href = a.css("::attr(href)").get()
                    except Exception:
                        href = None
                href = _unwrap_ddg_href(href or "")

                title_parts = []
                try:
                    title_parts = a.css("::text").getall()
                except Exception:
                    title_parts = []
                title = " ".join(t.strip() for t in title_parts if t and t.strip())
                if not title:
                    title = (getattr(a, "text", None) or "")[:160]
                # buang raw HTML kalau kepilih
                if "<a " in title or "result__a" in title:
                    title = re.sub(r"<[^>]+>", "", title)

                if href:
                    results.append(
                        {
                            "title": title[:160],
                            "url": href,
                            "snippet": "",
                        }
                    )
            except Exception:
                continue

        # snippets
        try:
            snips = list(page.css(".result__snippet::text") or [])
            for i, sn in enumerate(snips[: len(results)]):
                if isinstance(sn, str):
                    results[i]["snippet"] = sn.strip()[:240]
                else:
                    try:
                        results[i]["snippet"] = (sn.get() if hasattr(sn, "get") else str(sn))[
                            :240
                        ]
                    except Exception:
                        pass
        except Exception:
            pass

        risk_flags = []
        blob = " ".join(
            (r.get("title", "") + " " + r.get("snippet", "")).lower() for r in results
        )
        if any(
            w in blob
            for w in ("korban penipuan", "laporan penipuan", "loker palsu", "penipu loker", "scam loker", "hati-hati penipuan", "terbukti menipu")
        ):
            risk_flags.append(
                "Hasil pencarian memuat indikasi laporan penipuan/loker palsu terkait query."
            )

        return {
            "type": "search",
            "query": q,
            "ok": True,
            "url": url,
            "results": results,
            "risk_flags": risk_flags,
        }
    except Exception as exc:
        return {
            "type": "search",
            "query": q,
            "ok": False,
            "error": str(exc),
            "results": [],
            "risk_flags": [],
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
    Web evidence (Scrapling) — dipangkas untuk latency:
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

    # Search minimal berprioritas (parallel sequential tapi sedikit)
    searches: list[dict[str, Any]] = []
    if companies:
        company = companies[0]
        clean_comp = re.sub(r"\s+cab(?:ang)?\s+.*$", "", company, flags=re.I).strip()
        searches.append(search_web_evidence(f"{clean_comp} instagram OR website OR toko"))
        searches.append(search_web_evidence(f'"{clean_comp}" penipu OR scam'))
    elif domains:
        searches.append(search_web_evidence(f"{domains[0]} penipuan OR scam"))

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

    has_any_working_web_or_social = any(w.get("ok") for w in website_checks) or any(gf.get("is_gform") for gf in gform_inspections)
    for w in website_checks:
        risk_flags.extend(w.get("risk_flags") or [])
        safe_flags.extend(w.get("safe_flags") or [])
        if w.get("ok") is False and not has_any_working_web_or_social:
            risk_flags.append(f"Website tidak dapat diakses: {w.get('url')}")
    for s in searches:
        risk_flags.extend(s.get("risk_flags") or [])

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
        "engine": "scrapling",
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
