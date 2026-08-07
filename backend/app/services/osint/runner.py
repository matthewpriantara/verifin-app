"""OSINT probe runner — eksekusi paralel semua probe publik.

Dipisah dari pipeline.py agar pipeline hanya melakukan orchestration.
Dipanggil pipeline via run_osint_probes(entities).
"""

import asyncio
import re

from app.services.osint.address_validator import validate_address_and_business
from app.services.osint.company_validator import validate_companies
from app.services.osint.phone_validator import check_phones_reputation
from app.services.osint.social import run_social_osint
from app.services.osint.web_evidence import run_web_evidence
from app.services.osint.whois_handler import check_domain_age, check_email_security
from app.services.status_contract import COMPLETED, NOT_PROVIDED, UNAVAILABLE

async def run_osint_probes(entities: dict) -> dict:
    """
    OSINT live paralel: WHOIS/DNS + OSM + Kaspersky Who Calls + Scrapling web + Threads.
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
        "threads": {
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
                "(WHOIS, DNS, OSM, Kaspersky Who Calls, Scrapling, Threads). "
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
            return await validate_companies(entities, limit=1)
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

    async def _threads_job() -> dict:
        try:
            return await asyncio.to_thread(run_social_osint, entities)
        except Exception as exc:
            return {
                "enabled": True,
                "probe_status": UNAVAILABLE,
                "found": False,
                "posts": [],
                "profiles": [],
                "risk_flags": [],
                "error": str(exc),
            }

    loop = asyncio.get_running_loop()
    t0 = loop.time()
    (
        domain_pair,
        addr_list,
        phones,
        web,
        companies_osint,
        threads,
    ) = await asyncio.gather(
        loop.run_in_executor(None, _domain_job),
        _addresses_job(),
        _phones_job(),
        _web_job(),
        _companies_job(),
        _threads_job(),
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
    osint_results["companies"] = companies_osint
    osint_results["threads"] = threads
    _merge_company_web_evidence(osint_results["companies"], web)
    _merge_company_social_evidence(osint_results["companies"], threads)
    return osint_results


def _merge_company_web_evidence(company_records: list, web: dict) -> None:
    if not company_records or not isinstance(web, dict):
        return
    for record in company_records:
        if not isinstance(record, dict):
            continue
        company_name = str(record.get("name") or "")
        tokens = {
            token for token in re.sub(r"[^a-z0-9 ]", " ", company_name.lower()).split()
            if len(token) >= 4 and token not in {"badan", "group", "indonesia"}
        }
        matches = []
        for search in web.get("searches") or []:
            for result in search.get("results") or []:
                blob = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
                matched = sum(token in blob for token in tokens)
                if matched >= min(2, len(tokens)):
                    matches.append({
                        "title": result.get("title"),
                        "url": result.get("url"),
                        "source_type": result.get("source_type"),
                    })
        if not matches:
            continue
        stats = record.setdefault("stats", {})
        stats["public_mentions"] = max(stats.get("public_mentions", 0), len(matches))
        stats["cross_service_public_mentions"] = len(matches)
        record["cross_service_evidence"] = matches[:8]
        if not record.get("safe_flags"):
            record["safe_flags"] = [
                f"Ditemukan {len(matches)} jejak publik yang cocok dari web evidence."
            ]


def _merge_company_social_evidence(company_records: list, social: dict) -> None:
    if not company_records or not isinstance(social, dict):
        return
    posts = [post for post in social.get("posts") or [] if isinstance(post, dict)]
    if not posts:
        return
    evidence = [
        {
            "title": post.get("title"),
            "url": post.get("url"),
            "platform": post.get("platform"),
            "source_type": post.get("source_type"),
            "is_official": bool(post.get("is_official")),
        }
        for post in posts[:12]
    ]
    for record in company_records:
        stats = record.setdefault("stats", {})
        stats["social_public_mentions"] = len(evidence)
        stats["official_social_mentions"] = sum(item["is_official"] for item in evidence)
        record["social_evidence"] = evidence
