import asyncio
import re

from app.services.ner import is_multi_employer, primary_employer_name
from app.services.osint.address_validator import validate_address_and_business
from app.services.osint.company_validator import validate_companies
from app.services.osint.getcontact import lookup_getcontact, lookup_getcontact_tags
from app.services.osint.phone_validator import check_phones_reputation, normalize_phone_id
from app.services.osint.social import run_social_osint
from app.services.osint.web_evidence import run_web_evidence
from app.services.osint.whois_handler import check_domain_age, check_email_security
from app.services.status_contract import COMPLETED, NOT_PROVIDED, UNAVAILABLE

# Lokasi di luar negeri tidak dicari di peta Indonesia ("Jepang" bukan Desa Jepang, Kudus).
_FOREIGN_PLACE = re.compile(
    r"\b(?:jepang|japan|korea|taiwan|malaysia|hong\s*kong|singapura|singapore|brunei|arab\s+saudi|saudi|"
    r"qatar|dubai|uni\s+emirat|turki|polandia|australia|kamboja|cambodia|myanmar|laos|thailand|vietnam|"
    r"filipina|philippines|luar\s+negeri)\b",
    re.I,
)


def _part_of_foreign_place(place: str, foreign_places: list[str]) -> bool:
    """Kota yang juga disebut bersama negara asing ("Osaka" dari "Osaka, Jepang") tidak dipetakan.

    Tanpa ini "Osaka" dicari di peta Indonesia dan jatuh ke kelurahan acak di Makassar.
    """
    key = place.strip().lower()
    return bool(key) and any(
        key in [p.strip() for p in f.lower().split(",")] for f in foreign_places
    )


# Wilayah yang bukan tempat yang bisa dipetakan: seluruh negeri, atau frasa yang memuat nama
# perusahaan ("Wilayah Kerja PT. Pos Indonesia (Persero)").
_NOT_A_PLACE = re.compile(
    r"^\s*(?:seluruh\s+)?(?:wilayah\s+)?indonesia\s*$|\bnasional\b|\bseluruh\b|\b(?:pt|cv|persero|tbk)\b\.?",
    re.I,
)


_RISK_TEXT_KEYS = (
    "has_fee_request",
    "brand_unofficial_channel",
    "has_telegram_apply",
    "anonymous_employer_claim",
    "salary_no_company",
)


def _text_has_risk_signal(entities: dict) -> bool:
    """Sinyal risiko teks yang sudah dihitung classifier, plus kata kunci penipuan."""
    signals = entities.get("_text_signals") or {}
    if any(signals.get(k) for k in _RISK_TEXT_KEYS):
        return True
    # Satu kata kunci terlalu lemah: LJ1 (Malio Gelato, loker asli) memakai kuota 1/hari di run 15.
    if float(signals.get("fraud_keyword_count") or 0) >= 2:
        return True
    return bool((entities.get("extraction_meta") or {}).get("has_fee_request"))


async def run_osint_probes(entities: dict) -> dict:
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
            # Anti-kontaminasi lokal: bila input memuat beberapa pemberi kerja dengan kontak berbeda,
            # jangan buat hubungan Cartesian product antara semua kontak dan semua perusahaan.
            "edges": (
                [
                    {"source": phone, "target": comp, "relation": "contact_of"}
                    for comp in (entities.get("companies") or [])
                    for phone in (entities.get("phones") or [])
                ] + [
                    {"source": email, "target": comp, "relation": "email_of"}
                    for comp in (entities.get("companies") or [])
                    for email in (entities.get("emails") or [])
                ] + [
                    {"source": addr, "target": comp, "relation": "location_of"}
                    for comp in (entities.get("companies") or [])
                    for addr in (entities.get("addresses") or [])
                ]
            ) if not is_multi_employer(entities) else [],
            "cluster_id": None,
            "entity_in_fraud_network": False,
            "total_case_count": 0,
            "threat_level": "LOW",
        },
        "timing": {},
    }

    emails = entities.get("emails", []) or []
    _NON_GEO_PATTERNS = re.compile(
        r"^(?:remote|hybrid|wfh|work\s+from\s+home|onsite|on\s+site|"
        r"anywhere|flexible|mobile|field|permanent|kontrak|contract|"
        r"full\s*time|part\s*time|freelance|internship|magang)$",
        re.I,
    )
    # Alamat fisik dari lowongan diutamakan. Bila tidak ada, kota penempatan dipakai, dan hasilnya
    # ditandai supaya laporan tidak menampilkannya sebagai alamat yang tertulis di lowongan.
    address_source = "posting_address" if entities.get("addresses") else "location_candidate"
    raw_addresses = (entities.get("addresses") or entities.get("location_candidates") or [])
    foreign_places = [a for a in raw_addresses if _FOREIGN_PLACE.search(a)]
    addresses = [
        a for a in raw_addresses
        if not _NON_GEO_PATTERNS.match(a.strip())
        and not _FOREIGN_PLACE.search(a)
        and not (address_source == "location_candidate" and _NOT_A_PLACE.search(a))
        and not _part_of_foreign_place(a, foreign_places)
    ][:2]
    companies = entities.get("companies") or []
    company_name = primary_employer_name(companies) or None

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
            # Simpan nama domain supaya XAI tahu lowongan memang memakai domain korporat.
            age_info.setdefault("domain", domain)
            security_info.setdefault("domain", domain)
            return age_info, security_info
        except Exception as exc:
            return (
                {
                    # Gagal memeriksa bukan bukti domain baru.
                    "error": str(exc),
                    "domain": domain,
                    "is_new": None,
                    "age_years": None,
                    "created_at": "Unknown",
                },
                {"spf_active": False, "dmarc_active": False},
            )

    async def _addresses_job(web_results: list) -> list:
        if not addresses:
            return []

        async def one(addr: str):
            try:
                result = await validate_address_and_business(addr, company_name, web_results)
                result["address_source"] = address_source
                return result
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
        loop = asyncio.get_running_loop()
        started = loop.time()
        raw_numbers = [p for p in (entities.get("phones") or []) if p][:1]
        # GetContact berjalan bersamaan dengan Kaspersky; kuota layanan kecil (10/hari).
        getcontact_task = asyncio.gather(*[lookup_getcontact(p) for p in raw_numbers])
        try:
            company = (entities.get("companies") or [""])[0]
            phones = await check_phones_reputation(entities.get("phones") or [], limit=1, company=company, web_results=web_results)
        except Exception as exc:
            phones = [
                {"source": "kredibel", "found": False, "probe_status": UNAVAILABLE,
                 "reputation_status": UNAVAILABLE, "error": str(exc), "risk_flags": []}
            ]
        try:
            lookups = await getcontact_task
        except Exception:
            lookups = []
        for phone, lookup in zip(phones, lookups):
            if isinstance(phone, dict) and isinstance(lookup, dict):
                phone["getcontact"] = lookup
        # Isi tag hanya dibaca bila nomor punya 1–99 tag DAN teks memuat sinyal risiko.
        # Kuota number-detail 1/hari, jadi jangan dipakai untuk lowongan yang jelas aman.
        if lookups and isinstance(lookups[0], dict) and lookups[0].get("probe_status") == COMPLETED:
            level = lookups[0].get("community_level")
            risky_text = _text_has_risk_signal(entities)
            if level in ("FEW", "KNOWN") and risky_text:
                try:
                    tags_result = await lookup_getcontact_tags(raw_numbers[0])
                except Exception:
                    tags_result = {}
                if isinstance(tags_result, dict) and tags_result.get("probe_status") == COMPLETED:
                    lookups[0]["fraud_tags"] = tags_result
        osint_results["timing"]["getcontact_ms"] = round((loop.time() - started) * 1000)
        return phones

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
    web, domain_pair = await asyncio.gather(
        _web_job(),
        loop.run_in_executor(None, _domain_job),
    )

    shared_web_results: list = [
        r
        for s in (web.get("searches") or [])
        for r in (s.get("results") or [])
        if isinstance(r, dict)
    ]

    addr_list, phones = await asyncio.gather(
        _addresses_job(shared_web_results),
        _phones_job(shared_web_results),
    )
    osint_results["timing"]["osint_parallel_sec"] = round(loop.time() - t0, 3)

    osint_results["domain"], osint_results["email_security"] = domain_pair
    osint_results["address_validations"] = addr_list
    if foreign_places:
        osint_results["foreign_locations"] = foreign_places
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
    companies_osint = await _companies_job()
    osint_results["companies"] = companies_osint
    osint_results["social"] = social
    _attach_company_evidence_counts(osint_results["companies"], web, social)
    _cross_check_phone_official(osint_results)
    return osint_results

_ID_MOBILE_PREFIXES = {
    "811", "812", "813", "821", "822", "823", "851", "852", "853",
    "814", "815", "816", "855", "856", "857", "858",
    "817", "818", "819", "859", "877", "878", "879",
    "831", "832", "833", "838",
    "881", "882", "883", "884", "885", "886", "887", "888", "889",
    "895", "896", "897", "898", "899",
    "828", "868",
}


def _extract_phones_from_text(text: str) -> set[str]:
    found: set[str] = set()
    for m in re.findall(r"(?:\+?62|0)(?:[\s.\-]?\d){8,13}", text or ""):
        digits = re.sub(r"\D", "", m)
        if digits.startswith("62"):
            local = digits[2:]
        elif digits.startswith("0"):
            local = digits[1:]
        else:
            continue
        local = local.lstrip("0")
        if 9 <= len(local) <= 12 and local[:3] in _ID_MOBILE_PREFIXES:
            found.add(local)
    return found


def _cross_check_phone_official(osint_results: dict) -> None:
    phones = osint_results.get("phones") or []
    web = osint_results.get("web") or {}
    if not phones or not isinstance(web, dict):
        return

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
                f"Nomor kontak lowongan ({raw}) tidak sama dengan nomor yang muncul di hasil "
                f"pencarian tentang perusahaan ini (mis. +62{sample[0]}). Netral: nomor di hasil "
                f"pencarian belum tentu nomor resmi, dan nomor HR bisa berbeda. Pastikan konfirmasi "
                f"seleksi berasal dari kanal resmi perusahaan."
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
    web_relevant = int(((web or {}).get("evidence_counts") or {}).get("relevant_results") or 0)
    for record in company_records:
        if not isinstance(record, dict):
            continue
        stats = record.setdefault("stats", {})
        stats["cross_service_match_count"] = web_match_count
        stats["social_public_mention_count"] = social_count
        # Validator perusahaan memakai query sendiri dan bisa kosong padahal probe web
        # (query yang lebih kaya: nama + alamat) menemukan hasil relevan. Samakan supaya
        # XAI dan prompt LLM tidak menerima dua fakta yang bertentangan.
        if web_relevant > int(stats.get("public_mentions") or 0):
            stats["public_mentions"] = web_relevant
            stats["public_mentions_source"] = "web_evidence"
            record["neutral_notes"] = [
                note for note in (record.get("neutral_notes") or [])
                if "tidak ada hasil relevan" not in str(note).lower()
            ]
