import asyncio
import re
from typing import Any

from scrapling.fetchers import Fetcher

from app.services.status_contract import COMPLETED, UNAVAILABLE


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


_KASPERSKY_DANGER = {"BERBAHAYA": 2, "SPAM": 2, "MENCURIGAKAN": 1, "NETRAL": 0, "AMAN": 0}
_REPUTATION_BY_DANGER = {0: "CLEAN", 1: "SUSPICIOUS", 2: "FLAGGED"}


def _parse_kaspersky_page(page: Any, result: dict[str, Any]) -> dict[str, Any]:
    verdict_el = page.css('[class*="NumberInfoWrapper_title"]').first
    verdict = verdict_el.text.strip().upper() if verdict_el is not None else ""
    if not verdict:
        result["error"] = "Kaspersky: elemen status nomor tidak ditemukan di halaman."
        return result

    risk_flags = result["risk_flags"]
    if verdict not in _KASPERSKY_DANGER:
        # Label baru/tidak dikenal tidak boleh otomatis dianggap mencurigakan.
        result["error"] = f"Kaspersky: label status tidak dikenal ('{verdict}')."
        result["category"] = verdict
        return result
    danger_level = _KASPERSKY_DANGER[verdict]
    result.update({
        "checked": True,
        "probe_status": COMPLETED,
        "reputation_status": _REPUTATION_BY_DANGER[danger_level],
        "category": verdict,
        "danger_level": danger_level,
        "comments": [
            line.strip()
            for el in page.css('[class*="Comments_comment"]')
            for line in el.get_all_text(strip=True).splitlines()
            if line.strip() and not line.strip().startswith("Coba Kaspersky")
        ],
    })

    if danger_level >= 2:
        result["scam_confirmed"] = True
        risk_flags.append(f"Kaspersky Who Calls: nomor terdeteksi '{verdict}'.")
    elif danger_level == 1:
        risk_flags.append(f"Kaspersky Who Calls: nomor mencurigakan — '{verdict}'.")
    return result


def _check_kaspersky(phone_meta: dict[str, str]) -> dict[str, Any]:
    digits = phone_meta["e164"].lstrip("+")
    url = f"https://whocalls.id.kaspersky.com/info/{digits}"
    result: dict[str, Any] = {
        "source": "kaspersky",
        "phone": phone_meta["display"],
        "url": url,
        "checked": False,
        "probe_status": UNAVAILABLE,
        "reputation_status": UNAVAILABLE,
        "danger_level": None,
        "category": None,
        "scam_confirmed": False,
        "risk_flags": [],
    }

    try:
        page = Fetcher.get(url, stealthy_headers=True, follow_redirects=True)
        if page is None or page.status != 200:
            result["error"] = f"Kaspersky HTTP {getattr(page, 'status', 'N/A')}"
            return result
        return _parse_kaspersky_page(page, result)
    except Exception as exc:
        result["error"] = f"Kaspersky check gagal: {exc}"
        return result


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
        if phone_in_result and has_scam_report:
            found_scam = True
            risk_flags.append(
                f"SERP publik: laporan penipuan terkait nomor {phone_meta['display']}"
            )
            break
    return {"serp_checked": True, "serp_results": results, "risk_flags": risk_flags, "found_scam": found_scam}


def check_phone_kredibel(phone: str) -> dict[str, Any]:
    meta = normalize_phone_id(phone)
    if not meta["local"] or len(meta["local"]) < 8:
        return {
            "source": "kaspersky",
            "phone": phone,
            "found": False,
            "checked": False,
            "probe_status": UNAVAILABLE,
            "reputation_status": UNAVAILABLE,
            "error": "Format nomor tidak valid.",
            "risk_flags": [],
        }

    kaspersky = _check_kaspersky(meta)
    serp = _search_phone_public_serp(meta)

    all_risk_flags = kaspersky.get("risk_flags", []) + serp.get("risk_flags", [])
    reported_fraud = bool(kaspersky.get("scam_confirmed")) or bool(serp.get("found_scam"))
    return {
        **kaspersky,
        "found": reported_fraud,
        "reported_fraud": reported_fraud,
        "risk_flags": all_risk_flags,
        "serp_fallback": serp,
    }


async def check_phones_kredibel(contacts: list[str], limit: int = 2) -> list[dict[str, Any]]:
    phones = [c for c in (contacts or []) if c][:limit]
    if not phones:
        return []
    loop = asyncio.get_running_loop()
    results = []
    for ph in phones:
        result = await loop.run_in_executor(None, check_phone_kredibel, ph)
        results.append(result)
    return results


async def check_phones_reputation(
    contacts: list[str],
    limit: int = 2,
    company: str = "",
    web_results: list | None = None,
    **kwargs,
) -> list[dict[str, Any]]:
    return await check_phones_kredibel(contacts, limit=limit)
