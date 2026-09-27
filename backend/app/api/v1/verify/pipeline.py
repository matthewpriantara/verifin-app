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
    _is_plausible_address,
    _uniq,
    clean_indonesian_phone,
    fix_email_ocr_typos,
)
from app.services.osint.runner import run_osint_probes
from app.services.xai.shap_explainer import explain_verification_shap
from app.services.graph.fraud_network import (
    build_fraud_network,
    check_entity_in_network,
)
from app.services.status_contract import COMPLETED, NOT_PROVIDED, UNAVAILABLE

def _check_fraud_network(db: Session, entities: dict) -> dict:
    try:
        cases = db.query(JobCase).order_by(
            JobCase.created_at.desc()
        ).limit(500).all()

        if not cases:
            return {"status": "NO_DATA", "entity_in_fraud_network": False, "total_case_count": 0}

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

        G = build_fraud_network(cases_data)

        network_ctx = check_entity_in_network(G, entities)

        try:
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

        community = _community_report_signal(db, entities)
        network_ctx["community_reports"] = community
        if community.get("status") == COMPLETED and community.get("report_count", 0) > 0:
            network_ctx["entity_in_fraud_network"] = True
            if community["report_count"] >= 3:
                network_ctx["threat_level"] = "HIGH"
            elif network_ctx.get("threat_level") not in ("HIGH",):
                network_ctx["threat_level"] = "MEDIUM"
        network_ctx["status"] = COMPLETED
        return network_ctx

    except Exception as exc:
        logging.getLogger(__name__).warning(f"Fraud network check failed: {exc}")
        return {"status": UNAVAILABLE, "entity_in_fraud_network": None, "error": str(exc)}


def _community_report_signal(db: Session, entities: dict) -> dict:
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
        return {"status": "NO_DATA", "report_count": 0, "reported_by_community": False}

    try:
        count = db.query(func.count(CommunityReport.id)).filter(or_(*conditions)).scalar() or 0
    except Exception:
        return {"status": UNAVAILABLE, "report_count": None, "reported_by_community": None}

    return {
        "status": COMPLETED,
        "report_count": int(count),
        "reported_by_community": count > 0,
        "risk_signal": "HIGH" if count >= 3 else ("MEDIUM" if count == 2 else ("LOW" if count == 1 else "NONE")),
    }

def _clean_text_for_ner(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"^\[TEKS\s+UTAMA[^\]]*\]:\s*", "", text, flags=re.I | re.M)
    cleaned = re.sub(r"^\[TEKS\s+CAPTION[^\]]*\]:\s*", "", cleaned, flags=re.I | re.M)
    cleaned = re.sub(r"^\[UTAS\s+BALASAN[^\]]*\]:\s*", "", cleaned, flags=re.I | re.M)
    cleaned = re.sub(r"^URL\s+Target:\s*\S+\s*", "", cleaned, flags=re.I | re.M)
    return cleaned.strip()


async def _extract_entities_hybrid(text: str) -> dict:
    clean_text = _clean_text_for_ner(text) or text

    regex_entities = await asyncio.to_thread(extract_entities_from_text, clean_text)

    llm_extracted = await _run_llm_ner(clean_text)

    if llm_extracted is None:
        regex_entities["_ner_meta"] = {
            "used": False,
            "source": "regex_fallback",
            "validation_applied": False,
        }
        return regex_entities

    merged = copy.deepcopy(regex_entities)
    added = {"companies": False, "addresses": False, "salaries": False, "location_candidates": False}
    cleaned = {"companies": 0}
    any_added = False

    llm_companies = llm_extracted.get("companies") or []
    if llm_companies:
        merged["companies"] = list(llm_companies)
        added["companies"] = True
        any_added = True

    for key in ("addresses", "location_candidates", "salaries"):
        llm_vals = llm_extracted.get(key) or []
        if not llm_vals:
            continue
        if key == "addresses":
            llm_vals = [value for value in llm_vals if _is_plausible_address(value)]
        existing = {_norm(v) for v in (merged.get(key) or [])}
        for v in llm_vals:
            nv = _norm(v)
            if nv and nv not in existing:
                merged.setdefault(key, []).append(v)
                existing.add(nv)
                added[key] = True
                any_added = True

    if merged.get("emails"):
        merged["emails"] = _uniq([fix_email_ocr_typos(e) for e in merged["emails"] if e])
    if merged.get("urls"):
        merged["urls"] = [u for u in _uniq(merged["urls"]) if not re.search(r"^(?:[a-zA-Z]\.com|gmail|yahoo|gmai|gamil)\.", u, re.I)]
    for key in ("companies", "addresses", "location_candidates", "salaries", "phones"):
        if merged.get(key):
            merged[key] = _uniq(merged[key])
    merged["addresses"] = [
        value for value in (merged.get("addresses") or [])
        if _is_plausible_address(value)
    ]

    merged["_ner_meta"] = {
        "used": True,
        "source": "hybrid_llm_regex" if any_added else "llm_no_new",
        "added": added,
        "cleaned_false_positive_companies": cleaned["companies"],
        "validation_applied": False,
    }
    return merged


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def _fuzzy_contains(a: str, b: str) -> bool:
    na, nb = _norm(a), _norm(b)
    if len(na) < 4 or len(nb) < 4:
        return na == nb
    return na in nb or nb in na


async def _run_llm_ner(text: str) -> dict | None:
    try:
        return await extract_entities_llm(text)
    except Exception:
        return None


async def _run_osint_on_entities(entities: dict) -> dict:
    return await run_osint_probes(entities)


async def _enrich_entities_from_osint(entities: dict, osint_results: dict) -> dict:
    if not osint_results:
        return entities

    web = osint_results.get("web") or {}
    platform_evidence = web.get("platform_evidence") or {}
    merged = platform_evidence.get("merged_evidence") or {}
    results = merged.get("results") or []

    osint_addresses: list[str] = []
    for r in results:
        extracted = r.get("extracted_data") or {}
        addr = extracted.get("address")
        if addr and isinstance(addr, str) and len(addr) > 5:
            if not re.search(r"^(?:null|none|n/a|-|tdk ada)$", addr, re.I):
                osint_addresses.append(addr.strip())

    if not osint_addresses:
        return entities

    osint_addresses = _uniq(osint_addresses)

    existing_addresses = entities.get("addresses") or []
    existing_locations = entities.get("location_candidates") or []

    if not existing_addresses and not existing_locations and osint_addresses:
        entities["addresses"] = osint_addresses
        entities["_ner_meta"] = entities.get("_ner_meta") or {}
        entities["_ner_meta"]["osint_enriched_addresses"] = True
        entities["_ner_meta"]["osint_address_source"] = "web_evidence_extracted"
        logging.getLogger(__name__).info(
            "[osint_enrich] Addresses enriched from OSINT: %s", osint_addresses
        )

    if not existing_locations and osint_addresses:
        entities["location_candidates"] = osint_addresses[:2]
        logging.getLogger(__name__).info(
            "[osint_enrich] Location candidates enriched from OSINT: %s", osint_addresses[:2]
        )

    addr_validations = osint_results.get("address_validations") or []
    needs_revalidation = False
    best_osint_addr = None

    if existing_addresses and osint_addresses:
        street_pattern = re.compile(r"\b(?:jl\.?|jln\.?|jalan)\b", re.I)

        def _addr_priority(addr: str) -> int:
            score = 0
            if street_pattern.search(addr):
                score += 2
            if any(len(addr) > len(na) for na in existing_addresses):
                score += 1
            return score

        sorted_osint = sorted(osint_addresses, key=_addr_priority, reverse=True)

        for osint_addr in sorted_osint:
            for ner_addr in existing_addresses:
                ner_first = ner_addr.lower().split(",")[0].strip()
                if (len(osint_addr) > len(ner_addr) and
                    ner_first in osint_addr.lower()):
                    best_osint_addr = osint_addr
                    needs_revalidation = True
                    break
            if needs_revalidation:
                break

    if not needs_revalidation and not existing_addresses and osint_addresses:
        best_osint_addr = osint_addresses[0]
        needs_revalidation = True

    if needs_revalidation and best_osint_addr:
        prev_match = ""
        if addr_validations:
            prev_match = (addr_validations[0].get("address_details") or {}).get("match_level", "")

        logging.getLogger(__name__).info(
            "[osint_enrich] Re-validation triggered: best_osint_addr=%s, prev_match=%s",
            best_osint_addr, prev_match
        )

        if prev_match in ("", "area"):
            try:
                from app.services.osint.address_validator import validate_address_and_business
                company = (entities.get("companies") or [""])[0]
                web_results = [
                    r
                    for s in (web.get("searches") or [])
                    for r in (s.get("results") or [])
                    if isinstance(r, dict)
                ]
                new_validation = await validate_address_and_business(
                    best_osint_addr, company, web_results
                )
                new_match = (new_validation.get("address_details") or {}).get("match_level", "")
                logging.getLogger(__name__).info(
                    "[osint_enrich] Re-validation result: %s → match_level=%s",
                    best_osint_addr, new_match
                )
                if new_match in ("exact", "street") or (new_match == "area" and not addr_validations):
                    addr_validations.insert(0, new_validation)
                    osint_results["address_validations"] = addr_validations
                    entities["addresses"] = [best_osint_addr] + [
                        a for a in existing_addresses if a != best_osint_addr
                    ]
                    logging.getLogger(__name__).info(
                        "[osint_enrich] Address updated to: %s (match_level=%s)",
                        best_osint_addr, new_match
                    )
                else:
                    logging.getLogger(__name__).info(
                        "[osint_enrich] Re-validation not better (new=%s vs prev=%s), keeping original",
                        new_match, prev_match
                    )
            except Exception as exc:
                logging.getLogger(__name__).warning(
                    "[osint_enrich] Re-validation failed: %s", exc
                )
    else:
        logging.getLogger(__name__).info(
            "[osint_enrich] No re-validation needed (needs_revalidation=%s, best=%s, existing=%s, osint=%s)",
            needs_revalidation, best_osint_addr, existing_addresses, osint_addresses[:3]
        )

    return entities


def _to_response(
    analysis: dict,
    entities: dict,
    osint_results: dict | None = None,
) -> VerifyResponse:
    corrected = analysis.get("corrected_company_name")
    if not entities.get("companies") and corrected and corrected not in (None, "null", ""):
        entities = {**entities, "companies": [str(corrected)]}

    safe_entities = {
        "companies": entities.get("companies") or [],
        "contacts": entities.get("phones") or [],
        "emails": entities.get("emails") or [],
        "urls": entities.get("urls") or [],
        "addresses": entities.get("addresses") or [],
        "location_candidates": entities.get("location_candidates") or [],
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
            nlp_result=(
                analysis.get("nlp_result")
                if (analysis.get("nlp_result") or {}).get("enabled") is True
                else None
            ),
            network_context=analysis.get("network_context"),
            entities=entities,
        )
    except Exception:
        shap_explanation = None
    analysis["shap_explanation"] = shap_explanation

    nlp_meta = analysis.get("nlp_result") or {}
    if osint_results is not None and nlp_meta.get("status"):
        osint_results["nlp"] = {
            "enabled": bool(nlp_meta.get("enabled")),
            "status": nlp_meta.get("status"),
            "reason": nlp_meta.get("reason"),
        }

    network_ctx = analysis.get("network_context")
    if network_ctx and osint_results is not None:
        existing_fn = osint_results.get("fraud_network") or {}
        existing_fn.update(network_ctx)
        osint_results["fraud_network"] = existing_fn
        if network_ctx.get("syndicate_analysis"):
            osint_results["syndicate_analysis"] = network_ctx["syndicate_analysis"]
        elif "syndicate_analysis" not in osint_results:
            osint_results["syndicate_analysis"] = detect_identity_syndicate(
                contacts=safe_entities.get("phones") or [],
                emails=safe_entities.get("emails") or [],
                current_company=safe_entities["companies"][0] if safe_entities.get("companies") else "Unknown"
            )

    return VerifyResponse(
        case_id=analysis.get("case_id"),
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
    if not osint_results:
        return None
    phones = osint_results.get("phones") or []
    addrs = osint_results.get("address_validations") or []
    web = osint_results.get("web") or {}
    social = osint_results.get("social") or {}
    return {
        "phones": [
            {
                "phone": p.get("phone") or p.get("phone_local"),
                "rating": p.get("rating"),
                "reported_fraud": p.get("reported_fraud") or p.get("scam_confirmed"),
                "reputation_status": p.get("reputation_status"),
                "probe_status": p.get("probe_status"),
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
        "social_query": social.get("query"),
        "social_found": bool(social.get("found")),
        "domain": {
            "age_years": (osint_results.get("domain") or {}).get("age_years"),
            "is_new": (osint_results.get("domain") or {}).get("is_new"),
        },
    }
