"""
Cek reputasi nomor HP via Kaspersky Who Calls Indonesia.
URL: https://whocalls.id.kaspersky.com/info/{e164_digits} — scrape web, tanpa login.
"""

import asyncio
import re
from typing import Any

from scrapling.fetchers import Fetcher


def normalize_phone_id(phone: str) -> dict[str, str]:
    digits = re.sub(r"[^\d]", "", (phone or "").strip())
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    if digits.startswith("8") and not digits.startswith("62"):
        digits = "62" + digits
    local = digits[2:] if digits.startswith("62") else digits
    local = local.lstrip("0") or local
    e164 = f"+{digits}" if digits.startswith("62") else f"+62{local}"
    return {"e164": e164, "local": local, "digits": digits, "display": e164}


def _check_kaspersky(phone_meta: dict[str, str]) -> dict[str, Any]:
    """
    Cek reputasi via Kaspersky Who Calls Indonesia (scrape web, tanpa login).
    URL: https://whocalls.id.kaspersky.com/info/{e164_digits}
    """
    digits = phone_meta["e164"].lstrip("+")
    url = f"https://whocalls.id.kaspersky.com/info/{digits}"
    risk_flags: list[str] = []
    result: dict[str, Any] = {
        "source": "kaspersky",
        "phone": phone_meta["display"],
        "url": url,
        "checked": False,
        "danger_level": None,
        "category": None,
        "scam_confirmed": False,
        "risk_flags": risk_flags,
    }

    try:
        page = Fetcher().get(url, stealthy_headers=True, follow_redirects=True)
        if page is None or page.status != 200:
            result["error"] = f"Kaspersky HTTP {getattr(page, 'status', 'N/A')}"
            return result

        result["checked"] = True

        verdict_el = page.css('[class*="NumberInfoWrapper_title"]')
        verdict = verdict_el[0].text.strip().upper() if verdict_el else "NETRAL"
        result["category"] = verdict

        comments = [el.text.strip() for el in page.css('[class*="Comments_comment"]') if el.text.strip()]
        result["comments"] = comments

        _danger = {"BERBAHAYA": 2, "SPAM": 2, "MENCURIGAKAN": 1, "NETRAL": 0, "AMAN": 0}
        danger_level = _danger.get(verdict, 1 if verdict not in ("NETRAL", "AMAN") else 0)
        result["danger_level"] = danger_level

        if danger_level >= 2:
            result["scam_confirmed"] = True
            risk_flags.append(f"Kaspersky Who Calls: nomor terdeteksi '{verdict}'.")
        elif danger_level == 1:
            risk_flags.append(f"Kaspersky Who Calls: nomor mencurigakan — '{verdict}'.")

        return result

    except Exception as exc:
        result["error"] = f"Kaspersky check gagal: {exc}"
        return result


def _search_phone_public_serp(phone_meta: dict[str, str]) -> dict[str, Any]:
    phone_digits = phone_meta["local"]
    query = f'"{phone_meta["display"]}" OR "0{phone_digits}" penipu OR scam OR penipuan'
    from app.services.osint.web_evidence import search_web_evidence

    res = search_web_evidence(query, max_results=5)
    results = res.get("results") or []
    risk_flags = []
    found_scam = False

    # Filter noise: buang result yang tidak relevan dengan nomor HP Indonesia
    # (Baidu, Yahoo JP, Microsoft JP, dsb sering masuk saat query nomor tidak ditemukan)
    _ID_DOMAINS = (
        ".id/", "detik.com", "kompas.com", "tribun", "liputan6", "kaskus",
        "kredibel", "cekrekening", "urgent.id", "lapor.go.id", "facebook.com",
        "instagram.com", "whatsapp", "tokopedia", "shopee",
    )
    filtered = []
    for r in results:
        url = (r.get("url") or "").lower()
        title = (r.get("title") or "").lower()
        snippet = (r.get("snippet") or "").lower()
        blob = f"{title} {snippet}"
        # Simpan kalau URL domain Indonesia atau nomor HP muncul di konten
        phone_in_result = (
            phone_digits in re.sub(r"\D", "", blob)
            or phone_meta["display"] in blob
            or f"0{phone_digits}" in blob
        )
        is_id_domain = any(d in url for d in _ID_DOMAINS)
        if phone_in_result or is_id_domain:
            filtered.append(r)

    for r in filtered:
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
        if phone_in_result and has_scam_report:
            found_scam = True
            risk_flags.append(
                f"SERP publik: laporan penipuan terkait nomor {phone_meta['display']}"
            )
            break

    # Deteksi nomor dipakai oleh perusahaan BERBEDA secara eksplisit.
    # Strategi: kumpulkan semua "employer name" dari title/snippet hasil SERP,
    # lalu cek apakah ada nama perusahaan LAIN (bukan company yang dicek sekarang)
    # yang muncul bersama nomor ini. Ini lebih akurat dari sekadar hitung jumlah hasil.
    # ponytail: simple substring match, upgrade ke fuzzy/NER kalau false positive masih banyak
    company_hint = phone_meta.get("company", "").lower()
    if company_hint:
        conflicting = [
            r.get("title", "")
            for r in filtered
            if (
                phone_digits in re.sub(r"\D", "", (r.get("title","") + r.get("snippet","")))
                or f"0{phone_digits}" in (r.get("snippet","") + r.get("title",""))
            )
            and company_hint not in (r.get("title","") + r.get("snippet","")).lower()
            # buang portal loker — mereka listing banyak company di 1 domain
            and not any(p in (r.get("url") or "").lower() for p in (
                "lokerjogja", "jobstreet", "glints", "kalibrr", "karir.com",
                "indeed", "linkedin", "loker.id", "toploker", "depokloker",
                "instagram.com", "facebook.com", "tiktok.com",
                # portal aggregator repost lowongan dengan nomor kontak mereka sendiri
            ))
        ]
        if len(conflicting) > 1:
            risk_flags.append(
                f"Nomor {phone_meta['display']} ditemukan pada lowongan perusahaan lain "
                f"({len(conflicting)} hasil tidak terkait '{phone_meta.get('company')}') "
                f"— kemungkinan nomor dipakai ulang lintas perusahaan."
            )

    return {"serp_checked": True, "serp_results": filtered, "risk_flags": risk_flags, "found_scam": found_scam}


def check_phone_reputation(phone: str, company: str = "") -> dict[str, Any]:
    """Cek reputasi nomor HP via Kaspersky → SERP fallback."""
    meta = normalize_phone_id(phone)
    meta["company"] = company
    if not meta["local"] or len(meta["local"]) < 8:
        return {
            "source": "kaspersky",
            "phone": phone,
            "found": False,
            "error": "Format nomor tidak valid.",
            "risk_flags": [],
        }

    kaspersky = _check_kaspersky(meta)

    # SERP fallback kalau Kaspersky tidak dapat hasil atau nomor aman
    serp = _search_phone_public_serp(meta)

    all_risk_flags = kaspersky.get("risk_flags", []) + serp.get("risk_flags", [])
    return {
        **kaspersky,
        "found": kaspersky.get("scam_confirmed", False) or serp.get("found_scam", False),
        "risk_flags": all_risk_flags,
        "serp_fallback": serp,
    }


async def check_phones_reputation(contacts: list[str], limit: int = 2, company: str = "") -> list[dict[str, Any]]:
    phones = [c for c in (contacts or []) if c][:limit]
    if not phones:
        return []
    loop = asyncio.get_running_loop()
    results = []
    for ph in phones:
        result = await loop.run_in_executor(None, check_phone_reputation, ph, company)
        results.append(result)
    return results
