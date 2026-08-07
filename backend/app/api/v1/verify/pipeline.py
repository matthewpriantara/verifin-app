"""Pipeline helpers — fraud network, NER hybrid, OSINT paralel, response builder."""
import asyncio
import copy
import logging
import re
from sqlalchemy.orm import Session
from app.services.hasher import detect_identity_syndicate

from app.api.v1.verify.schema import VerifyResponse, ExtractedEntities
from app.database.models import JobCase
from app.services.llm.entity_extraction import extract_entities_llm
from app.services.ner import (
    extract_entities_from_text,
    _uniq,
    clean_indonesian_phone,
    fix_email_ocr_typos,
)
from app.services.osint.address_validator import validate_address_and_business
from app.services.osint.company_validator import validate_companies
from app.services.osint.phone_validator import check_phones_kredibel
from app.services.osint.social import run_social_osint
from app.services.osint.web_evidence import run_web_evidence
from app.services.osint.whois_handler import check_domain_age, check_email_security
from app.services.xai.shap_explainer import explain_verification_shap
from app.services.graph.fraud_network import (
    build_fraud_network,
    check_entity_in_network,
)

def _check_fraud_network(db: Session, entities: dict) -> dict:
    """Cek entitas lowongan ke fraud graph NetworkX (GAR-HGNN inspired, 500 kasus terakhir)."""
    try:
        # Ambil kasus terbaru dari DB untuk membangun graf
        cases = db.query(JobCase).order_by(
            JobCase.created_at.desc()
        ).limit(500).all()

        if not cases:
            return {"entity_in_fraud_network": False, "total_case_count": 0}

        # Konversi SQLAlchemy objects ke dict
        cases_data = [
            {
                "id": str(c.id),
                "verdict": c.verdict,
                "risk_score": c.risk_score,
                "phones": c.phones or [],
                "emails": c.emails or [],
                "companies": c.companies or [],
                "urls": c.urls or [],
                "created_at": str(c.created_at),
            }
            for c in cases
        ]

        # Build in-memory graph
        G = build_fraud_network(cases_data)

        # Cek entitas baru terhadap graf
        network_ctx = check_entity_in_network(G, entities)

        # Syndicate: deteksi reuse no HP/email lintas perusahaan berbeda
        try:
            # siapkan company_name per kasus agar reuse lintas perusahaan terdeteksi
            hist = [
                {
                    "phones": cd.get("phones") or [],
                    "emails": cd.get("emails") or [],
                    "company_name": (cd.get("companies") or [None])[0],
                }
                for cd in cases_data
            ]
            network_ctx["syndicate_analysis"] = detect_identity_syndicate(
                contacts=entities.get("phones") or [],
                emails=entities.get("emails") or [],
                current_company=(entities.get("companies") or ["Unknown"])[0],
                historical_cases=hist,
            )
        except Exception as _syn_exc:
            network_ctx["syndicate_analysis"] = {
                "syndicate_detected": False, "syndicate_alerts": [],
                "note": f"analisis sindikat dilewati: {_syn_exc}",
            }

        # Community reports — laporan berulang pada entitas = sinyal risiko
        community = _community_report_signal(db, entities)
        network_ctx["community_reports"] = community
        if community.get("report_count", 0) > 0:
            network_ctx["entity_in_fraud_network"] = True
            # Eskalasi threat_level bila belum tinggi
            if community["report_count"] >= 3:
                network_ctx["threat_level"] = "HIGH"
            elif network_ctx.get("threat_level") not in ("HIGH",):
                network_ctx["threat_level"] = "MEDIUM"
        return network_ctx

    except Exception as exc:
        logging.getLogger(__name__).warning(f"Fraud network check failed: {exc}")
        return {"entity_in_fraud_network": False, "error": str(exc)}


def _community_report_signal(db: Session, entities: dict) -> dict:
    """Hitung berapa kali entitas lowongan ini dilaporkan komunitas."""
    from app.database.models import CommunityReport
    from sqlalchemy import func, or_

    conditions = []
    for comp in (entities.get("companies") or []):
        conditions.append(func.lower(CommunityReport.company_name) == str(comp).strip().lower())
    for em in (entities.get("emails") or []):
        conditions.append(func.lower(CommunityReport.email) == str(em).strip().lower())
    for url in (entities.get("urls") or []):
        conditions.append(CommunityReport.url == str(url).strip())
    for ph in (entities.get("phones") or []):
        digits = "".join(c for c in str(ph) if c.isdigit())
        if digits.startswith("0"):
            digits = "62" + digits[1:]
        if digits:
            conditions.append(CommunityReport.phone == digits)

    if not conditions:
        return {"report_count": 0, "reported_by_community": False}

    try:
        count = db.query(func.count(CommunityReport.id)).filter(or_(*conditions)).scalar() or 0
    except Exception:  # noqa: BLE001
        return {"report_count": 0, "reported_by_community": False}

    return {
        "report_count": int(count),
        "reported_by_community": count > 0,
        "risk_signal": "HIGH" if count >= 3 else ("MEDIUM" if count == 2 else ("LOW" if count == 1 else "NONE")),
    }


async def _extract_entities_hybrid(text: str) -> dict:
    """
    Hybrid NER: regex (entitas struktural) + LLM extraction (entitas semantik).

    LLM extraction untuk companies/addresses/salaries berjalan PARALEL dengan
    regex via asyncio.gather — regex selesai instan, LLM overlap sehingga tidak
    menambah critical path secara signifikan. Jika LLM down/timeout/JSON rusak,
    hybrid_merge_entities fallback penuh ke hasil regex (safety net).

    Metadata extraction disimpan di entities["_ner_meta"] untuk observability
    (sumber: regex | hybrid_llm_regex | llm_no_new).
    """
    regex_task = asyncio.to_thread(extract_entities_from_text, text)
    regex_entities, merged_entities = await asyncio.gather(
        regex_task,
        # hybrid_merge_entities butuh hasil regex → kita jalankan LLM-nya
        # paralel dengan regex lewat task terpisah, lalu merge di dalam.
        _run_llm_ner(text),
    )
    # regex_entities = hasil regex; merged_entities = hasil LLM (atau None)
    if merged_entities is None:
        regex_entities["_ner_meta"] = {"used": False, "source": "regex"}
        return regex_entities
    # Merge dengan strategi per-kategori:
    # - companies: LLM adalah daftar OTORITATIF (lebih akurat secara semantik).
    #   Regex hanya dipertahankan bila namanya dikonfirmasi LLM (fuzzy match),
    #   sehingga false positive regex ("dan cekatan", "bersedia training") dibuang.
    # - addresses & salaries: MERGE-ADDITIVE (LLM menambah yang regex lewatkan,
    #   regex tetap jadi suplemen — keduanya cenderung precision-tinggi).
    def _norm(s: str) -> str:
        return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()

    def _fuzzy_contains(a: str, b: str) -> bool:
        """True bila salah satu normalized string mengandung yang lain (min 4 char)."""
        na, nb = _norm(a), _norm(b)
        if len(na) < 4 or len(nb) < 4:
            return na == nb
        return na in nb or nb in na

    merged = copy.deepcopy(regex_entities)
    added = {"companies": False, "addresses": False, "salaries": False}
    cleaned = {"companies": 0}
    any_added = False

    # ── companies: LLM otoritatif ──────────────────────────────────────────
    llm_companies = merged_entities.get("companies") or []
    if llm_companies:
        regex_companies = merged.get("companies") or []
        # Mulai dari daftar LLM (urut), lalu tambah regex yang dikonfirmasi LLM.
        new_companies: list[str] = list(llm_companies)
        for rc in regex_companies:
            if any(_fuzzy_contains(rc, lc) for lc in llm_companies):
                # regex dikonfirmasi LLM → pertahankan jika belum ada
                if not any(_fuzzy_contains(rc, e) for e in new_companies):
                    new_companies.append(rc)
            else:
                cleaned["companies"] += 1  # regex tidak dikonfirmasi → dibuang
        if len(new_companies) > len(regex_companies):
            added["companies"] = True
            any_added = True
        merged["companies"] = new_companies

    # ── addresses & salaries: merge-additive + smart deduplication ────────
    for key in ("addresses", "salaries"):
        llm_vals = merged_entities.get(key) or []
        if not llm_vals:
            continue
        existing = {_norm(v) for v in (merged.get(key) or [])}
        for v in llm_vals:
            nv = _norm(v)
            if nv and nv not in existing:
                merged.setdefault(key, []).append(v)
                existing.add(nv)
                added[key] = True
                any_added = True
    # Dedup dan bersihkan hasil merge
    if merged.get("emails"):
        merged["emails"] = _uniq([fix_email_ocr_typos(e) for e in merged["emails"] if e])
    if merged.get("urls"):
        merged["urls"] = [u for u in _uniq(merged["urls"]) if not re.search(r"^(?:[a-zA-Z]\.com|gmail|yahoo|gmai|gamil)\.", u, re.I)]
    for key in ("companies", "addresses", "salaries", "phones"):
        if merged.get(key):
            merged[key] = _uniq(merged[key])



    merged["_ner_meta"] = {
        "used": True,
        "source": "hybrid_llm_regex" if any_added else "llm_no_new",
        "added": added,
        "cleaned_false_positive_companies": cleaned["companies"],
    }
    return merged



async def _run_llm_ner(text: str) -> dict | None:
    """Jalankan LLM extraction terisolasi; return None jika gagal/tidak aktif."""
    try:
        return await extract_entities_llm(text)
    except Exception:  # noqa: BLE001 — fallback by design
        return None


async def _run_osint_on_entities(entities: dict) -> dict:
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
                    "error": "Gagal memvalidasi alamat.",
                }

        return list(await asyncio.gather(*[one(a) for a in addresses]))

    async def _phones_job() -> list:
        try:
            return await check_phones_kredibel(entities.get("phones") or [], limit=1)
        except Exception as exc:
            return [
                {"source": "kredibel", "found": False, "error": str(exc), "risk_flags": []}
            ]

    async def _web_job() -> dict:
        try:
            return await run_web_evidence(entities)
        except Exception as exc:
            return {
                "enabled": True,
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
                    "error": str(exc),
                    "registry": {"pt_registry_verified": False},
                    "risk_flags": [],
                    "safe_flags": [],
                    "evidence": [],
                }
            ]

    async def _threads_job() -> dict:
        try:
            return await run_social_osint(entities)
        except Exception as exc:
            return {
                "enabled": True,
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
    osint_results["web"] = web
    osint_results["companies"] = companies_osint
    osint_results["threads"] = threads
    return osint_results


def _merge_entities(primary: dict, secondary: dict) -> dict:

    keys = ["companies", "phones", "emails", "urls", "addresses", "salaries"]
    out = {}
    for key in keys:
        combined = list(primary.get(key) or []) + list(secondary.get(key) or [])
        if key == "phones":
            std = []
            for ph in combined:
                c_ph = clean_indonesian_phone(ph)
                if c_ph:
                    std.append(c_ph)
            out[key] = _uniq(std)
        elif key == "emails":
            out[key] = _uniq([fix_email_ocr_typos(e) for e in combined if e])
        elif key == "urls":
            # Filter artifact domain satu huruf seperti L.com / gmai.com
            clean_urls = [
                u for u in combined
                if u and not re.search(r"^(?:[a-zA-Z]\.com|gmail|yahoo|gmai|gamil)\.", u, re.I)
            ]
            out[key] = _uniq(clean_urls)
        elif key == "addresses":
            comp_lows = {c.strip().lower() for c in out.get("companies", [])}
            clean_addrs = [
                a for a in combined
                if a and a.strip().lower() not in comp_lows
                and not any(a.strip().lower() in c or c in a.strip().lower() for c in comp_lows if len(c) >= 6)
            ]
            out[key] = _uniq(clean_addrs)
        else:
            out[key] = _uniq(combined)
    return out


def _to_response(
    analysis: dict,
    entities: dict,
    osint_results: dict | None = None,
) -> VerifyResponse:
    corrected = analysis.get("corrected_company_name")
    if corrected and corrected not in (None, "null", ""):
        entities = {**entities, "companies": [str(corrected)]}

    # Normalisasi kunci entities sesuai schema
    safe_entities = {
        "companies": entities.get("companies") or [],
        "contacts": entities.get("phones") or [],
        "emails": entities.get("emails") or [],
        "urls": entities.get("urls") or [],
        "addresses": entities.get("addresses") or [],
        "salaries": entities.get("salaries") or [],
    }

    risk_score = int(analysis.get("risk_score") or 0)
    verdict = analysis.get("verdict", "ERROR")
    risk_factors = analysis.get("risk_factors") or []
    safe_factors = analysis.get("safe_factors") or []

    shap_explanation = None
    try:
        shap_explanation = explain_verification_shap(
            risk_score=risk_score,
            verdict=verdict,
            osint_results=osint_results or {},
            risk_factors=risk_factors,
            safe_factors=safe_factors,
            nlp_result=analysis.get("nlp_result"),
            network_context=analysis.get("network_context"),
        )
    except Exception:
        shap_explanation = None

    # Ekspos network_context ke response agar FE bisa tampilkan sinyal Fraud Network
    network_ctx = analysis.get("network_context")
    if network_ctx and osint_results is not None:
        existing_fn = osint_results.get("fraud_network") or {}
        existing_fn.update(network_ctx)
        osint_results["fraud_network"] = existing_fn
        # Pakai syndicate dari _check_fraud_network (dihitung dari DB nyata)
        if network_ctx.get("syndicate_analysis"):
            osint_results["syndicate_analysis"] = network_ctx["syndicate_analysis"]
        elif "syndicate_analysis" not in osint_results:
            osint_results["syndicate_analysis"] = detect_identity_syndicate(
                contacts=safe_entities.get("phones") or [],
                emails=safe_entities.get("emails") or [],
                current_company=safe_entities["companies"][0] if safe_entities.get("companies") else "Unknown"
            )

    return VerifyResponse(
        verdict=verdict,
        risk_score=risk_score,
        summary=analysis.get("summary", ""),
        risk_factors=risk_factors,
        safe_factors=safe_factors,
        recommendations=analysis.get("recommendations") or [],
        entities=ExtractedEntities(**safe_entities),
        model_used=analysis.get("model_used"),
        osint=osint_results,
        shap_explanation=shap_explanation,
    )


def _build_osint_summary(osint_results: dict | None) -> dict | None:
    """Snapshot ringan untuk audit/case-memory (hindari raw HTML besar)."""
    if not osint_results:
        return None
    phones = osint_results.get("phones") or []
    addrs = osint_results.get("address_validations") or []
    web = osint_results.get("web") or {}
    threads = osint_results.get("threads") or {}
    return {
        "phones": [
            {
                "phone": p.get("phone") or p.get("phone_local"),
                "rating": p.get("rating"),
                "reported_fraud": p.get("reported_fraud"),
                "review_count": p.get("review_count"),
            }
            for p in phones[:5]
            if isinstance(p, dict)
        ],
        "addresses": [
            {
                "input": a.get("address_input") or a.get("query"),
                "found": a.get("address_found") or a.get("found"),
                "display": ((a.get("address_details") or {}).get("display_name") or "")[:120],
            }
            for a in addrs[:5]
            if isinstance(a, dict)
        ],
        "web_search_count": len((web.get("searches") or [])),
        "web_safe_flags": (web.get("safe_flags") or web.get("safe_signals") or [])[:8],
        "web_risk_flags": (web.get("risk_flags") or [])[:8],
        "threads_query": threads.get("query"),
        "threads_found": bool(threads.get("found")),
        "domain": {
            "age_years": (osint_results.get("domain") or {}).get("age_years"),
            "is_new": (osint_results.get("domain") or {}).get("is_new"),
        },
    }


