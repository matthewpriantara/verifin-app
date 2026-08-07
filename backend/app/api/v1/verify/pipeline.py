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
    """Cek entitas lowongan ke fraud graph NetworkX (GAR-HGNN inspired, 500 kasus terakhir)."""
    try:
        # Ambil kasus terbaru dari DB untuk membangun graf
        cases = db.query(JobCase).order_by(
            JobCase.created_at.desc()
        ).limit(500).all()

        if not cases:
            return {"status": "NO_DATA", "entity_in_fraud_network": False, "total_case_count": 0}

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
        if community.get("status") == COMPLETED and community.get("report_count", 0) > 0:
            network_ctx["entity_in_fraud_network"] = True
            # Eskalasi threat_level bila belum tinggi
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
        return {"status": "NO_DATA", "report_count": 0, "reported_by_community": False}

    try:
        count = db.query(func.count(CommunityReport.id)).filter(or_(*conditions)).scalar() or 0
    except Exception:  # noqa: BLE001
        return {"status": UNAVAILABLE, "report_count": None, "reported_by_community": None}

    return {
        "status": COMPLETED,
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
    hasil fallback penuh ke regex (safety net).

    Metadata extraction disimpan di entities["_ner_meta"] untuk observability
    (sumber: regex | hybrid_llm_regex | llm_no_new).
    """
    regex_task = asyncio.to_thread(extract_entities_from_text, text)
    regex_entities, merged_entities = await asyncio.gather(
        regex_task,
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
    # LLM tidak boleh mengubah area/cabang atau kalimat benefit menjadi alamat.
    for key in ("addresses", "salaries"):
        llm_vals = merged_entities.get(key) or []
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
    # Dedup dan bersihkan hasil merge
    if merged.get("emails"):
        merged["emails"] = _uniq([fix_email_ocr_typos(e) for e in merged["emails"] if e])
    if merged.get("urls"):
        merged["urls"] = [u for u in _uniq(merged["urls"]) if not re.search(r"^(?:[a-zA-Z]\.com|gmail|yahoo|gmai|gamil)\.", u, re.I)]
    for key in ("companies", "addresses", "salaries", "phones"):
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
    }
    return merged



async def _run_llm_ner(text: str) -> dict | None:
    """Jalankan LLM extraction terisolasi; return None jika gagal/tidak aktif."""
    try:
        return await extract_entities_llm(text)
    except Exception:  # noqa: BLE001 — fallback by design
        return None


async def _run_osint_on_entities(entities: dict) -> dict:
    """Thin wrapper — eksekusi OSINT paralel dipindah ke services.osint.runner."""
    return await run_osint_probes(entities)


def _merge_entities(primary: dict, secondary: dict) -> dict:

    keys = ["companies", "phones", "emails", "urls", "addresses", "location_candidates", "salaries"]
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
        elif key == "location_candidates":
            out[key] = _uniq(combined)
        else:
            out[key] = _uniq(combined)
    return out


def _to_response(
    analysis: dict,
    entities: dict,
    osint_results: dict | None = None,
) -> VerifyResponse:
    # Nama dari NER adalah canonical evidence. LLM boleh mengusulkan koreksi
    # hanya saat NER tidak menemukan nama sama sekali; typo LLM tidak boleh
    # menimpa entitas yang sudah dipakai OSINT dan fraud graph.
    corrected = analysis.get("corrected_company_name")
    if not entities.get("companies") and corrected and corrected not in (None, "null", ""):
        entities = {**entities, "companies": [str(corrected)]}

    # Normalisasi kunci entities sesuai schema
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
            nlp_result=analysis.get("nlp_result"),
            network_context=analysis.get("network_context"),
            entities=entities,
        )
    except Exception:
        shap_explanation = None

    # Ekspos status layer NLP jujur (STUB saat ini) — jangan sampai FE mengira aktif
    nlp_meta = analysis.get("nlp_result") or {}
    if osint_results is not None and nlp_meta.get("status"):
        osint_results["nlp"] = {
            "enabled": bool(nlp_meta.get("enabled")),
            "status": nlp_meta.get("status"),
            "reason": nlp_meta.get("reason"),
        }

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
        "threads_query": threads.get("query"),
        "threads_found": bool(threads.get("found")),
        "domain": {
            "age_years": (osint_results.get("domain") or {}).get("age_years"),
            "is_new": (osint_results.get("domain") or {}).get("is_new"),
        },
    }
