"""OSINT probe runner — eksekusi paralel semua probe publik.

Dipisah dari pipeline.py agar pipeline hanya melakukan orchestration.
Dipanggil pipeline via run_osint_probes(entities).
"""

import asyncio
import re

from app.services.osint.address_validator import validate_address_and_business
from app.services.osint.company_validator import validate_companies
from app.services.osint.phone_validator import check_phones_reputation, normalize_phone_id
from app.services.osint.social import run_social_osint
from app.services.osint.web_evidence import run_web_evidence
from app.services.osint.whois_handler import check_domain_age, check_email_security
from app.services.status_contract import COMPLETED, NOT_PROVIDED, UNAVAILABLE

async def run_osint_probes(entities: dict) -> dict:
    """
    OSINT live paralel: WHOIS/DNS + OSM + Kaspersky Who Calls + Scrapling web + seluruh platform media sosial.
    Optimasi latency: asyncio.gather (bukan serial await).
    """
    from app.services.constants import FREE_EMAIL_DOMAINS

    osint_results: dict = {
        "domain": {
            "age_years": None,
            "created_at": "Tidak diketahui",
            "is_new": False,
        },
        "email_security": {"spf_active": False, "dmarc_active": False},
        "address_validations": [],
        "phones": [],
        "phone_probe": {
            "status": NOT_PROVIDED if not (entities.get("phones") or []) else "PENDING",
            "note": "Nomor HP tidak tercantum pada input; pemeriksaan Kaspersky dilewati."
            if not (entities.get("phones") or []) else None,
        },
        "companies": [],
        "web": {
            "enabled": False,
            "websites": [],
            "searches": [],
            "risk_flags": [],
            "safe_flags": [],
        },
        "social": {
            "enabled": False,
            "found": False,
            "posts": [],
            "profiles": [],
            "risk_flags": [],
        },
        "evidence_policy": {
            "mode": "factual_sources_only",
            "note": (
                "Semua temuan OSINT berasal dari fetch/scrape/API nyata "
                "(WHOIS, DNS, OSM, Kaspersky Who Calls, Scrapling, dan seluruh platform media sosial). "
                "LLM reasoner dilarang mengarang fakta di luar evidence."
            ),
            "social": "all_platforms",
        },
        "fraud_network": {
            "nodes": [
                {"id": comp, "type": "company", "risk_score": 0, "status": "CLEAN"} for comp in (entities.get("companies") or [])
            ] + [
                {"id": phone, "type": "phone", "risk_score": 0, "status": "CLEAN"} for phone in (entities.get("phones") or [])
            ] + [
                {"id": email, "type": "email", "risk_score": 0, "status": "FREE_PROVIDER"} for email in (entities.get("emails") or [])
            ] + [
                {"id": addr, "type": "address", "risk_score": 0, "status": "VALID_GIS"} for addr in (entities.get("addresses") or [])
            ],
            "edges": [
                {"source": phone, "target": comp, "relation": "contact_of"} for comp in (entities.get("companies") or []) for phone in (entities.get("phones") or [])
            ] + [
                {"source": email, "target": comp, "relation": "email_of"} for comp in (entities.get("companies") or []) for email in (entities.get("emails") or [])
            ] + [
                {"source": addr, "target": comp, "relation": "location_of"} for comp in (entities.get("companies") or []) for addr in (entities.get("addresses") or [])
            ],
            "cluster_id": None,
            "entity_in_fraud_network": False,
            "total_case_count": 0,
            "threat_level": "LOW",
        },
        "timing": {},
    }

    emails = entities.get("emails", []) or []
    # Jika tidak ada alamat fisik, gunakan location_candidates (lokasi kerja)
    # untuk validasi Nominatim — lokasi kerja dari poster lebih relevan daripada
    # alamat kantor pusat yang mungkin ditemukan OSINT nanti.
    addresses = (entities.get("addresses") or entities.get("location_candidates") or [])[:2]
    companies = entities.get("companies") or []
    company_name = companies[0] if companies else None

    # Domain: skip WHOIS/DNS untuk Gmail/Yahoo (netral + buang waktu)
    def _domain_job() -> tuple[dict, dict]:
        if not emails:
            return osint_results["domain"], osint_results["email_security"]
        domain = emails[0].split("@")[-1].lower() if "@" in emails[0] else ""
        if not domain:
            return osint_results["domain"], osint_results["email_security"]
        if domain in FREE_EMAIL_DOMAINS:
            return (
                {
                    "age_years": None,
                    "created_at": "N/A (free email)",
                    "is_new": False,
                    "domain": domain,
                    "skipped": "free_email",
                },
                {"spf_active": False, "dmarc_active": False, "skipped": "free_email"},
            )
        try:
            age_info = check_domain_age(domain)
            if "age_years" not in age_info and age_info.get("age_days", -1) > 0:
                age_info["age_years"] = round(age_info["age_days"] / 365, 2)
            security_info = check_email_security(domain)
            return age_info, security_info
        except Exception as exc:
            return (
                {
                    "error": str(exc),
                    "is_new": True,
                    "age_years": None,
                    "created_at": "Unknown",
                },
                {"spf_active": False, "dmarc_active": False},
            )

    # ── Arsitektur "1 query nama → distribusi" ──────────────────────────────
    # Pencarian perusahaan hanya ditembak SEKALI (di _web_job via intelligent_
    # search). Hasilnya (web_results) lalu dibagikan ke phone_validator dan
    # address_validator untuk deteksi scam/konfirmasi bisnis TANPA query baru.
    # Ini meminimalkan request ke engine publik (anti rate-limit/captcha).

    async def _addresses_job(web_results: list) -> list:
        if not addresses:
            return []

        async def one(addr: str):
            try:
                return await validate_address_and_business(addr, company_name, web_results)
            except Exception:
                return {
                    "address_input": addr,
                    "address_found": False,
                    "probe_status": UNAVAILABLE,
                    "evidence_status": UNAVAILABLE,
                    "error": "Gagal memvalidasi alamat.",
                }

        return list(await asyncio.gather(*[one(a) for a in addresses]))

    async def _phones_job(web_results: list) -> list:
        try:
            company = (entities.get("companies") or [""])[0]
            return await check_phones_reputation(entities.get("phones") or [], limit=1, company=company, web_results=web_results)
        except Exception as exc:
            return [
                {"source": "kredibel", "found": False, "probe_status": UNAVAILABLE,
                 "reputation_status": UNAVAILABLE, "error": str(exc), "risk_flags": []}
            ]

    async def _web_job() -> dict:
        try:
            return await run_web_evidence(entities)
        except Exception as exc:
            return {
                "enabled": True,
                "probe_status": UNAVAILABLE,
                "websites": [],
                "searches": [],
                "risk_flags": [],
                "safe_flags": [],
                "error": str(exc),
            }

    async def _companies_job() -> list:
        try:
            return await validate_companies(
                entities,
                limit=1,
                web_evidence=osint_results.get("web") or {},
            )
        except Exception as exc:
            return [
                {
                    "checked": False,
                    "probe_status": UNAVAILABLE,
                    "error": str(exc),
                    "registry": {"pt_registry_verified": False},
                    "risk_flags": [],
                    "safe_flags": [],
                    "evidence": [],
                }
            ]

    loop = asyncio.get_running_loop()
    t0 = loop.time()

    # Tahap 1: jalankan pencarian web (1 query) + domain probe secara paralel.
    web, domain_pair = await asyncio.gather(
        _web_job(),
        loop.run_in_executor(None, _domain_job),
    )

    # Ekstrak semua hasil pencarian untuk dibagikan ke phone/address validator.
    shared_web_results: list = [
        r
        for s in (web.get("searches") or [])
        for r in (s.get("results") or [])
        if isinstance(r, dict)
    ]

    # Tahap 2: phone + address validator memakai hasil web yang sudah ada.
    addr_list, phones = await asyncio.gather(
        _addresses_job(shared_web_results),
        _phones_job(shared_web_results),
    )
    osint_results["timing"]["osint_parallel_sec"] = round(loop.time() - t0, 3)

    osint_results["domain"], osint_results["email_security"] = domain_pair
    osint_results["address_validations"] = addr_list
    osint_results["phones"] = phones
    if entities.get("phones"):
        phone_statuses = [p.get("probe_status") for p in phones if isinstance(p, dict)]
        phone_probe_status = (
            COMPLETED if phone_statuses and all(status == COMPLETED for status in phone_statuses)
            else "PARTIAL" if phone_statuses and any(status == COMPLETED for status in phone_statuses)
            else UNAVAILABLE
        )
        osint_results["phone_probe"] = {
            "status": phone_probe_status,
            "note": "Nomor HP ditemukan dan dikirim ke validator reputasi."
            if phone_probe_status == "COMPLETED"
            else "Nomor HP ditemukan, tetapi sebagian pemeriksaan reputasi tidak tersedia."
            if phone_probe_status == "PARTIAL"
            else "Nomor HP ditemukan, tetapi validator reputasi tidak tersedia.",
        }
    osint_results["web"] = web
    try:
        social = await asyncio.to_thread(run_social_osint, entities, web)
    except Exception as exc:
        social = {
            "enabled": True,
            "probe_status": UNAVAILABLE,
            "found": False,
            "posts": [],
            "profiles": [],
            "risk_flags": [],
            "error": str(exc),
        }
    # Company validation consumes web evidence; it must not issue a second
    # round of company searches or website fetches.
    companies_osint = await _companies_job()
    osint_results["companies"] = companies_osint
    osint_results["social"] = social
    _attach_company_evidence_counts(osint_results["companies"], web, social)
    _cross_check_phone_official(osint_results)
    return osint_results


# Prefix operator seluler Indonesia (2 digit pertama setelah kode negara / leading 0).
# Dipakai untuk menolak false positive seperti ID numerik atau nomor pendek acak.
_ID_MOBILE_PREFIXES = {
    "811", "812", "813", "821", "822", "823", "851", "852", "853",  # Telkomsel
    "814", "815", "816", "855", "856", "857", "858",                # Indosat
    "817", "818", "819", "859", "877", "878", "879",                # XL/Axis
    "831", "832", "833", "838",                                     # Axis/3
    "881", "882", "883", "884", "885", "886", "887", "888", "889",  # Smartfren
    "895", "896", "897", "898", "899",                              # Three
    "828", "868",                                                   # Smartfren/Bolt
}


def _extract_phones_from_text(text: str) -> set[str]:
    """Ekstrak kandidat nomor telepon Indonesia dari teks bebas, dinormalisasi
    ke bentuk lokal (tanpa kode negara, tanpa leading 0). Mendukung separator
    spasi/titik/strip di tengah nomor (mis. 0811-2607-494, 0811.2658.586).

    Guard anti-false-positive (generik): nomor harus cukup panjang DAN berawalan
    prefix operator seluler Indonesia yang dikenal, supaya ID numerik / kode acak
    (mis. '0817000 60' dari teks lain) tidak dianggap nomor telepon.
    """
    found: set[str] = set()
    # Blok digit dengan separator opsional; total digit 9-14 setelah dinormalisasi
    for m in re.findall(r"(?:\+?62|0)(?:[\s.\-]?\d){8,13}", text or ""):
        digits = re.sub(r"\D", "", m)
        if digits.startswith("62"):
            local = digits[2:]
        elif digits.startswith("0"):
            local = digits[1:]
        else:
            continue
        local = local.lstrip("0")
        # Nomor seluler ID: 9-12 digit lokal & prefix operator valid.
        if 9 <= len(local) <= 12 and local[:3] in _ID_MOBILE_PREFIXES:
            found.add(local)
    return found


def _cross_check_phone_official(osint_results: dict) -> None:
    """Bandingkan nomor kontak lowongan dengan nomor yang tercantum pada jejak
    publik resmi bisnis (website resmi, Google Maps, halaman sosial) dari SERP.

    Bila nomor lowongan BERSIH dari laporan penipuan tetapi BERBEDA dengan nomor
    resmi bisnis, tambahkan neutral_note — bukan risk flag, karena nomor HR
    memang bisa berbeda dari nomor CS/resmi.
    """
    phones = osint_results.get("phones") or []
    web = osint_results.get("web") or {}
    if not phones or not isinstance(web, dict):
        return

    # Kumpulkan nomor dari snippet hasil web (official + maps + sosial)
    official_phones: set[str] = set()
    sources_with_phone: list[str] = []
    for search in web.get("searches") or []:
        for r in (search.get("results") or []):
            if not isinstance(r, dict):
                continue
            snippet = r.get("snippet") or ""
            title = r.get("title") or ""
            blob = f"{title} {snippet}"
            nums = _extract_phones_from_text(blob)
            if nums:
                official_phones.update(nums)
                sources_with_phone.append(r.get("url") or "")
    # Juga dari website resmi yang berhasil di-fetch
    for site in web.get("websites") or []:
        if not isinstance(site, dict):
            continue
        text = (site.get("text") or site.get("content") or "")
        official_phones.update(_extract_phones_from_text(text))

    if not official_phones:
        return

    for p in phones:
        if not isinstance(p, dict):
            continue
        raw = p.get("phone") or ""
        if not raw:
            continue
        local = normalize_phone_id(raw).get("local", "").lstrip("0")
        if not local:
            continue
        if local not in official_phones:
            sample = sorted(official_phones)[:3]
            note = (
                f"Nomor kontak lowongan ({raw}) berbeda dari nomor yang tercantum pada "
                f"jejak publik resmi bisnis (mis. +62{sample[0]}). Ini netral — nomor HR "
                f"dapat berbeda dari kontak resmi — tetapi pastikan konfirmasi seleksi "
                f"berasal dari kanal resmi perusahaan."
            )
            notes = p.setdefault("neutral_notes", [])
            if note not in notes:
                notes.append(note)
        else:
            p.setdefault("neutral_notes", [])
            p["matches_official_contact"] = True


def _attach_company_evidence_counts(
    company_records: list,
    web: dict,
    social: dict,
) -> None:
    """Attach counts only; detailed evidence stays in its canonical sections."""
    if not company_records:
        return
    web_searches = web.get("searches") if isinstance(web, dict) else []
    social_posts = social.get("posts") if isinstance(social, dict) else []
    web_match_count = sum(
        len(search.get("results") or [])
        for search in web_searches or []
        if isinstance(search, dict)
    )
    social_count = len(social_posts or [])
    for record in company_records:
        if not isinstance(record, dict):
            continue
        stats = record.setdefault("stats", {})
        stats["cross_service_match_count"] = web_match_count
        stats["social_public_mention_count"] = social_count
