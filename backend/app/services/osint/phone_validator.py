"""
Cek reputasi nomor HP via Kredibel (https://www.kredibel.com/).
Pakai Scrapling + cookies login (secrets/kredibel_cookies.json) bila akses publik dibatasi.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from scrapling.fetchers import Fetcher

KREDIBEL_PHONE_URL = "https://www.kredibel.com/phone/id/{local}"
COOKIES_PATH = (
    Path(__file__).resolve().parents[3] / "secrets" / "kredibel_cookies.json"
)
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


def normalize_phone_id(phone: str) -> dict[str, str]:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    if digits.startswith("8") and not digits.startswith("62"):
        digits = "62" + digits

    local = digits[2:] if digits.startswith("62") else digits
    local = local.lstrip("0") or local
    e164 = f"+{digits}" if digits.startswith("62") else f"+62{local}"
    return {"e164": e164, "local": local, "digits": digits, "display": e164}


def _load_cookies() -> dict[str, str]:
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


def _extra_headers(jar: dict[str, str]) -> dict[str, str]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
        "Referer": "https://www.kredibel.com/search/phone",
    }
    if jar:
        headers["Cookie"] = _cookie_header(jar)
        # Laravel XSRF sering butuh header + cookie decoded
        xsrf = jar.get("XSRF-TOKEN")
        if xsrf:
            try:
                headers["X-XSRF-TOKEN"] = unquote(xsrf)
            except Exception:
                headers["X-XSRF-TOKEN"] = xsrf
    return headers


def _page_text_blob(page) -> tuple[str, str, str]:
    title = ""
    try:
        title = (page.css("title::text").get() or "").strip()
    except Exception:
        title = ""

    try:
        texts = [t.strip() for t in page.css("::text").getall() if t and t.strip()]
    except Exception:
        texts = []
    blob = re.sub(r"\s+", " ", " ".join(texts)).strip()

    html = ""
    try:
        html = page.css("body").get() or ""
    except Exception:
        html = ""
    return title, blob, html


def _is_login_wall(title: str, blob: str, phone_local: str) -> bool:
    blob_l = blob.lower()
    title_l = re.sub(r"\s+", " ", (title or "").lower()).strip()
    if "login" in title_l or "error=limit" in blob_l:
        return True
    has_login_cta = any(
        x in blob_l
        for x in (
            "bergabung dengan komunitas kredibel",
            "masuk ke akun kredibel",
            "login with google",
            "the largest anti-fraud community",
        )
    )
    has_signal = (
        "pernah dilaporkan" in blob_l
        or re.search(r"\d+(?:[.,]\d+)?\s*\(\s*\d+\s*reviews?", blob_l)
    )
    return has_login_cta and not has_signal


def _parse_kredibel_page(
    page,
    phone_meta: dict[str, str],
    *,
    used_cookies: bool,
) -> dict[str, Any]:
    title, blob, html = _page_text_blob(page)
    blob_l = blob.lower()
    url = KREDIBEL_PHONE_URL.format(local=phone_meta["local"])

    if _is_login_wall(title, blob, phone_meta["local"]):
        return {
            "source": "kredibel",
            "phone": phone_meta["display"],
            "phone_local": phone_meta["local"],
            "url": url,
            "title": title[:200],
            "found": False,
            "partial": True,
            "authenticated": used_cookies,
            "error": (
                "Kredibel login wall — cookies kedaluwarsa/invalid."
                if used_cookies
                else "Halaman Kredibel membatasi akses publik (login wall)."
            ),
            "risk_flags": [],
            "summary": "Cek Kredibel tidak mendapat detail; perbarui cookies login.",
        }

    rating = None
    review_count = None

    m = re.search(r"(\d+(?:[.,]\d+)?)\s*\(\s*(\d+)\s*reviews?\s*\)", blob, flags=re.I)
    if m:
        rating = float(m.group(1).replace(",", "."))
        review_count = int(m.group(2))
    else:
        m2 = re.search(r"\((\d+)\s*Review\)", blob, flags=re.I)
        if m2:
            review_count = int(m2.group(1))
        m3 = re.search(
            r'class="[^"]*rating-value[^"]*"[^>]*>\s*(\d+(?:[.,]\d+)?)',
            html,
            flags=re.I,
        )
        if m3:
            rating = float(m3.group(1).replace(",", "."))

    # coba class selectors
    if rating is None:
        try:
            rv = page.css(".rating-value::text").get()
            if rv and re.search(r"\d", rv):
                rating = float(re.sub(r"[^\d.,]", "", rv).replace(",", "."))
        except Exception:
            pass
    if review_count is None:
        try:
            for t in page.css("::text").getall():
                mm = re.search(r"\((\d+)\s*reviews?\)", t or "", re.I)
                if mm:
                    review_count = int(mm.group(1))
                    break
        except Exception:
            pass

    reported_fraud = (
        "pernah dilaporkan melakukan penipuan" in blob_l
        and "belum pernah dilaporkan" not in blob_l
    )
    needs_login_stats = "login untuk melihat statistik laporan" in blob_l
    phone_digits = re.sub(r"\D", "", phone_meta["display"])
    phone_in_page = phone_meta["local"] in re.sub(r"\D", "", blob + title) or phone_digits[
        -9:
    ] in re.sub(r"\D", "", blob + title)

    risk_flags: list[str] = []
    if reported_fraud:
        risk_flags.append("Kredibel: nomor pernah dilaporkan melakukan penipuan.")
    if rating is not None and rating <= 2.5 and (review_count or 0) >= 1:
        risk_flags.append(
            f"Kredibel: rating rendah ({rating}/5) dari {review_count} review."
        )
    if review_count and review_count >= 3 and rating is not None and rating < 3.5:
        risk_flags.append("Kredibel: banyak review dengan skor kurang baik.")

    # Statistik laporan (kalau terlihat setelah login)
    report_stats = {}
    m_stat = re.search(r"(\d+)\s*laporan", blob_l)
    if m_stat:
        report_stats["laporan_count"] = int(m_stat.group(1))
        if int(m_stat.group(1)) >= 1:
            risk_flags.append(f"Kredibel: tercatat {m_stat.group(1)} laporan.")

    summary_parts = []
    if reported_fraud:
        summary_parts.append("pernah dilaporkan penipuan")
    if rating is not None:
        summary_parts.append(f"rating {rating}")
    if review_count is not None:
        summary_parts.append(f"{review_count} review")
    if report_stats.get("laporan_count") is not None:
        summary_parts.append(f"{report_stats['laporan_count']} laporan")
    if needs_login_stats:
        summary_parts.append("sebagian statistik masih perlu login")
    if phone_in_page and not summary_parts:
        summary_parts.append("halaman nomor ditemukan, sinyal publik minim")

    return {
        "source": "kredibel",
        "phone": phone_meta["display"],
        "phone_local": phone_meta["local"],
        "url": url,
        "title": title[:200],
        "rating": rating,
        "review_count": review_count,
        "reported_fraud": reported_fraud,
        "needs_login_for_full_stats": needs_login_stats,
        "authenticated": used_cookies,
        "report_stats": report_stats,
        "risk_flags": risk_flags,
        "summary": "; ".join(summary_parts)
        if summary_parts
        else "Halaman Kredibel dibuka, sinyal terbatas.",
        "found": bool(
            phone_in_page or reported_fraud or rating is not None or review_count
        ),
    }


def _fetch_page(url: str, jar: dict[str, str]):
    headers = _extra_headers(jar)
    try:
        return Fetcher.get(url, stealthy_headers=True, headers=headers)
    except TypeError:
        try:
            return Fetcher.get(url, stealthy_headers=True, cookies=jar)
        except TypeError:
            return Fetcher.get(url, stealthy_headers=True)


def _search_phone_public_serp(phone_meta: dict[str, str]) -> dict[str, Any]:
    phone_digits = phone_meta["local"]
    query = f'"{phone_meta["display"]}" OR "0{phone_digits}" penipu OR scam OR penipuan'
    from app.services.osint.web_evidence import search_web_evidence

    res = search_web_evidence(query, max_results=3)
    results = res.get("results") or []
    risk_flags = []
    found_scam = False
    for r in results:
        title = (r.get("title") or "").lower()
        snippet = (r.get("snippet") or "").lower()
        blob = f"{title} {snippet}"
        phone_in_result = (
            phone_digits in re.sub(r"\D", "", blob)
            or phone_meta["display"] in blob
            or f"0{phone_digits}" in blob
        )
        has_scam_report = any(
            w in blob
            for w in (
                "korban",
                "laporan penipuan",
                "loker palsu",
                "penipu loker",
                "terbukti menipu",
                "waspada penipuan",
            )
        )
        is_generic_homepage = (
            "cek rekening" in title or "cara cek" in title or title.strip() == "kredibel"
        )
        if phone_in_result and has_scam_report and not is_generic_homepage:
            found_scam = True
            risk_flags.append(
                f"SERP publik: Ditemukan laporan penipuan spesifik terkait nomor {phone_meta['display']}"
            )
            break
    return {
        "serp_checked": True,
        "serp_results": results,
        "risk_flags": risk_flags,
        "found_scam": found_scam,
    }


def check_phone_kredibel(phone: str) -> dict[str, Any]:
    meta = normalize_phone_id(phone)
    if not meta["local"] or len(meta["local"]) < 8:
        return {
            "source": "kredibel",
            "phone": phone,
            "found": False,
            "error": "Format nomor tidak valid untuk dicek.",
            "risk_flags": [],
        }

    url = KREDIBEL_PHONE_URL.format(local=meta["local"])
    jar = _load_cookies()
    used_cookies = bool(jar.get("kredibel_session") or jar.get("remember_web_59ba36addc2b2f9401580f014c7f58ea4e30989d") or any(
        k.startswith("remember_web") for k in jar
    ))

    try:
        page = _fetch_page(url, jar if used_cookies else {})
        status = getattr(page, "status", None) or getattr(page, "status_code", None)
        if status and int(status) >= 400:
            serp = _search_phone_public_serp(meta)
            return {
                "source": "kredibel",
                "phone": meta["display"],
                "url": url,
                "found": serp.get("found_scam", False),
                "authenticated": used_cookies,
                "error": f"HTTP {status}",
                "risk_flags": serp.get("risk_flags", []),
                "serp_fallback": serp,
            }

        parsed = _parse_kredibel_page(page, meta, used_cookies=used_cookies)

        if parsed.get("partial") and used_cookies:
            try:
                import httpx

                with httpx.Client(timeout=25.0, follow_redirects=True) as client:
                    res = client.get(url, headers=_extra_headers(jar))
                    if res.status_code < 400:
                        class _P:
                            def __init__(self, html: str):
                                self._html = html
                                self.status = res.status_code

                            def css(self, sel: str):
                                from lxml import html as lhtml

                                tree = lhtml.fromstring(self._html)

                                class _R:
                                    def __init__(self, nodes):
                                        self.nodes = nodes

                                    def get(self):
                                        if not self.nodes:
                                            return None
                                        n = self.nodes[0]
                                        if sel.endswith("::text") or "::text" in sel:
                                            return (
                                                n.text_content()
                                                if hasattr(n, "text_content")
                                                else (n.text or "")
                                            )
                                        if "::attr(" in sel:
                                            attr = sel.split("::attr(")[1].rstrip(")")
                                            return n.get(attr)
                                        return lhtml.tostring(n, encoding="unicode")

                                    def getall(self):
                                        if "::text" in sel:
                                            return [
                                                (
                                                    n.text_content()
                                                    if hasattr(n, "text_content")
                                                    else (n.text or "")
                                                )
                                                for n in self.nodes
                                            ]
                                        return [
                                            lhtml.tostring(n, encoding="unicode")
                                            for n in self.nodes
                                        ]

                                if sel == "title::text":
                                    return _R(tree.xpath("//title"))
                                if sel == "body":
                                    return _R(tree.xpath("//body"))
                                if sel == "::text":
                                    class T:
                                        def __init__(self, t):
                                            self.text = t

                                        def text_content(self):
                                            return self.text

                                    return _R([T(str(t)) for t in tree.xpath("//text()") if str(t).strip()])
                                if sel.startswith(".") and "::text" in sel:
                                    cls = sel.split("::")[0].lstrip(".")
                                    return _R(tree.xpath(f'//*[contains(concat(" ", normalize-space(@class), " "), " {cls} ")]'))
                                return _R([])

                        parsed = _parse_kredibel_page(
                            _P(res.text), meta, used_cookies=True
                        )
                        parsed["fetch_mode"] = "httpx+cookies"
            except Exception as exc:
                parsed["cookie_retry_error"] = str(exc)

        # Jika Kredibel partial / tidak ada sinyal publik langsung, jalankan SERP fallback
        if not parsed.get("risk_flags") or parsed.get("partial"):
            serp = _search_phone_public_serp(meta)
            if serp.get("risk_flags"):
                parsed["risk_flags"].extend(serp["risk_flags"])
                parsed["found"] = True
            parsed["serp_fallback"] = serp

        return parsed
    except Exception as exc:
        serp = _search_phone_public_serp(meta)
        return {
            "source": "kredibel",
            "phone": meta["display"],
            "url": url,
            "found": serp.get("found_scam", False),
            "authenticated": used_cookies,
            "error": str(exc),
            "risk_flags": serp.get("risk_flags", []),
            "serp_fallback": serp,
        }


async def check_phones_kredibel(contacts: list[str], limit: int = 2) -> list[dict[str, Any]]:
    import asyncio

    phones = [c for c in (contacts or []) if c][:limit]
    if not phones:
        return []

    loop = asyncio.get_event_loop()
    results = []
    for ph in phones:
        result = await loop.run_in_executor(None, check_phone_kredibel, ph)
        results.append(result)
    return results
