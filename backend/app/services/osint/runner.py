"""OSINT probe runner — eksekusi paralel semua probe publik.

Dipisah dari pipeline.py agar pipeline hanya melakukan orchestration.
Dipanggil pipeline via run_osint_probes(entities).
"""

import asyncio

from app.services.osint.address_validator import validate_address_and_business
from app.services.osint.company_validator import validate_companies
from app.services.osint.phone_validator import check_phones_reputation
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
    addresses = (entities.get("addresses") or [])[:2]
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

    async def _addresses_job() -> list:
        if not addresses:
            return []

        async def one(addr: str):
            try:
                return await validate_address_and_business(addr, company_name)
            except Exception:
                return {
                    "address_input": addr,
                    "address_found": False,
                    "probe_status": UNAVAILABLE,
                    "evidence_status": UNAVAILABLE,
                    "error": "Gagal memvalidasi alamat.",
                }

        return list(await asyncio.gather(*[one(a) for a in addresses]))

    async def _phones_job() -> list:
        try:
            company = (entities.get("companies") or [""])[0]
            return await check_phones_reputation(entities.get("phones") or [], limit=1, company=company)
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
    (
        domain_pair,
        addr_list,
        phones,
        web,
    ) = await asyncio.gather(
        loop.run_in_executor(None, _domain_job),
        _addresses_job(),
        _phones_job(),
        _web_job(),
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
    return osint_results


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
