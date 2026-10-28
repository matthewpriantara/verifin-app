import asyncio
import copy
from difflib import SequenceMatcher
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
    is_junk_entity,
    is_junk_location,
    uniq_casefold,
    _DATE_TIME_JUNK,
    _DATE_PATTERNS,
    _uniq,
    fix_email_ocr_typos,
    is_multi_employer,
)
from app.services.osint.runner import run_osint_probes
from app.services.precheck import VISION_MARKER
from app.services.xai.shap_explainer import explain_verification_shap
from app.services.graph.fraud_network import (
    build_fraud_network,
    check_entity_in_network,
)
from app.services.status_contract import COMPLETED, UNAVAILABLE
from app.services.ner import clean_indonesian_phone

def _check_fraud_network(db: Session, entities: dict, raw_text: str | None = None) -> dict:
    from app.services.db_cache import _case_hash

    try:
        query = db.query(JobCase)
        if raw_text:
            # Verifikasi ulang teks yang sama tidak boleh cocok dengan riwayatnya sendiri.
            query = query.filter(JobCase.raw_text_hash != _case_hash(raw_text))
        cases = query.order_by(JobCase.created_at.desc()).limit(500).all()

        if not cases:
            return {"status": "NO_DATA", "entity_in_fraud_network": False, "total_case_count": 0}

        cases_data = []
        for c in cases:
            comps = c.companies or []
            phones = c.phones or []
            ent_meta = c.entities or {}
            is_multi = (
                ent_meta.get("is_multi_employer", False)
                or ent_meta.get("is_mixed_input", False)
                or is_multi_employer({"companies": comps, "phones": phones, "emails": c.emails or []})
            )
            is_non_job = (
                ent_meta.get("not_a_job_posting", False)
                or (c.llm_output or {}).get("not_a_job_posting", False)
            )
            cases_data.append({
                "id": str(c.id),
                "verdict": c.verdict,
                "risk_score": c.risk_score,
                "phones": phones,
                "emails": c.emails or [],
                "companies": comps,
                "urls": c.urls or [],
                "created_at": str(c.created_at),
                "is_multi_employer": is_multi,
                "not_a_job_posting": is_non_job,
            })

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
                if not cd.get("is_multi_employer") and not cd.get("not_a_job_posting")
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
            network_ctx["reported_by_community"] = True
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
        # "PT Pos Indonesia (Persero)" di lowongan, "Pos Indonesia" di laporan: bentuk badan usaha diabaikan.
        bare = _LEGAL_WORDS.sub(" ", str(comp)).replace("(", " ").replace(")", " ")
        bare = re.sub(r"\s+", " ", bare).strip().lower()
        if bare and bare != str(comp).strip().lower():
            conditions.append(func.lower(CommunityReport.company_name).in_([bare, f"pt {bare}", f"pt. {bare}"]))
    for em in (entities.get("emails") or []):
        conditions.append(func.lower(CommunityReport.email) == str(em).strip().lower())
    for url in (entities.get("urls") or []):
        conditions.append(CommunityReport.url == str(url).strip())
    phone_canon: dict[str, str] = {}
    for ph in (entities.get("phones") or []):
        # Laporan disimpan dalam format "+628…" (clean_indonesian_phone); baris lama tanpa "+" ikut dicocokkan.
        canon = clean_indonesian_phone(str(ph))
        if canon:
            conditions.append(CommunityReport.phone.in_([canon, canon.lstrip("+")]))
            phone_canon[canon] = canon
            phone_canon[canon.lstrip("+")] = canon

    if not conditions:
        return {"status": "NO_DATA", "report_count": 0, "reported_by_community": False}

    try:
        base_query = db.query(func.count(CommunityReport.id)).filter(or_(*conditions))
        count = base_query.filter(CommunityReport.status == "approved").scalar() or 0
        pending = base_query.filter(CommunityReport.status == "pending").scalar() or 0
        # Nomor mana yang dilaporkan, supaya kartu nomor di laporan tidak menulis "Tanpa laporan"
        # (hasil Kaspersky) untuk nomor yang sudah disetujui sebagai laporan komunitas.
        reported_phones: list[str] = []
        if phone_canon:
            rows = (
                db.query(CommunityReport.phone)
                .filter(CommunityReport.status == "approved", CommunityReport.phone.in_(list(phone_canon)))
                .distinct()
                .all()
            )
            reported_phones = sorted({phone_canon[r[0]] for r in rows if r[0] in phone_canon})
    except Exception:
        return {"status": UNAVAILABLE, "report_count": None, "reported_by_community": None}

    return {
        "status": COMPLETED,
        "report_count": int(count),
        "pending_report_count": int(pending),
        "reported_phones": reported_phones,
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


_SALARY_HINT = re.compile(r"\d|\bUM[RPK]\b", re.I)


def _squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _is_grounded(value: str, source: str) -> bool:
    """Entitas dari LLM hanya diterima bila memang tertulis di teks sumber.

    Dicocokkan per token bermakna (>= 3 huruf) setelah semua tanda baca dan spasi dibuang,
    karena OCR sering menghapus spasi ("GLOBALSINERGI") atau mengganti huruf besar-kecil.
    """
    hay = _squash(source)
    if not hay:
        return False
    whole = _squash(value)
    if whole and whole in hay:
        return True
    tokens = [_squash(t) for t in re.split(r"[\s,./()-]+", value or "")]
    tokens = [t for t in tokens if len(t) >= 3 and t not in {"pt", "cv", "tbk", "the"}]
    return bool(tokens) and all(t in hay for t in tokens)


_LEGAL_PREFIX = re.compile(r"^(PT|CV|UD)\.?\s*", re.I)


def _merge_company_fragments(companies: list[str], source: str) -> list[str]:
    """Gabungkan nama perusahaan yang terpecah di dua baris logo (mis. "PT.INDOKARYA" + "GLOBAL SINERGI").

    OCR menyusun teks per blok tata letak, jadi baris kedua logo selalu tepat di bawah baris pertama.
    Hanya pecahan berawalan PT/CV/UD dengan satu kata nama yang digabung dengan pecahan di baris
    berikutnya (maks. 3 kata, tanpa awalan badan usaha). Akronim pendek (<= 3 huruf, mis. logo "iGS")
    dibuang bila ada nama yang lebih panjang.
    """
    if len(companies) < 2:
        return companies
    lines = [_squash(l) for l in (source or "").splitlines()]

    def line_of(name: str) -> int:
        key = _squash(name)
        return next((i for i, l in enumerate(lines) if key and key in l), 10**6)

    ordered = sorted(companies, key=line_of)
    merged: list[str] = []
    used: set[int] = set()
    for i, name in enumerate(ordered):
        if i in used:
            continue
        current = name
        if _LEGAL_PREFIX.match(name) and len(_LEGAL_PREFIX.sub("", name).split()) <= 1:
            for j in range(i + 1, len(ordered)):
                nxt = ordered[j]
                if j in used or _LEGAL_PREFIX.match(nxt) or len(nxt.split()) > 3 or len(_squash(nxt)) <= 3:
                    continue
                if line_of(nxt) - line_of(name) == 1:
                    current = f"{current} {nxt}"
                    used.add(j)
                    break
        merged.append(_LEGAL_PREFIX.sub(lambda m: f"{m.group(1).upper()} ", current).strip())
    longest = max(len(_squash(n)) for n in merged)
    return [n for n in merged if len(_squash(n)) > 3 or longest <= 3]


_LEGAL_WORDS = re.compile(r"\b(?:pt|cv|ud|persero|tbk)\b\.?", re.I)


def _dedupe_companies(companies: list[str]) -> list[str]:
    """Satukan varian penulisan nama yang sama ("PT POS INDONESIA", "PT pos Indonesia persero",
    "PT Pos Indonesia (Persero)"). Bentuk legal PT/Persero/Tbk dan tanda baca diabaikan saat
    membandingkan; yang disimpan adalah varian berhuruf campuran yang paling lengkap."""
    groups: dict[str, list[str]] = {}
    for name in companies:
        key = _squash(_LEGAL_WORDS.sub(" ", name)) or _squash(name)
        groups.setdefault(key, []).append(name)

    def quality(name: str) -> tuple[int, int]:
        mixed_case = name != name.upper() and name != name.lower() and not name.split()[-1].islower()
        return (int(mixed_case), len(name))

    return [max(names, key=quality) for names in groups.values()]


def _drop_ocr_misreads(companies: list[str], vision_text: str) -> list[str]:
    """Buang nama hasil salah baca OCR pada logo bergaya ("SBOENGA") bila model vision membaca
    nama yang mirip dengan benar ("ROEMAH BOENGA"): nama itu tidak ada di bacaan vision, sedangkan
    nama lain yang ada di bacaan vision berbagi potongan huruf panjang dengannya."""
    seen = _squash(vision_text)
    in_vision = [c for c in companies if _squash(c) and _squash(c) in seen]
    kept = []
    for c in companies:
        sc = _squash(c)
        if c not in in_vision and any(
            SequenceMatcher(None, sc, _squash(v)).find_longest_match(0, len(sc), 0, len(_squash(v))).size >= 5
            for v in in_vision
        ):
            continue
        kept.append(c)
    return in_vision + [c for c in kept if c not in in_vision]


def _contact_key(kind: str, value: str) -> str:
    if kind == "phones":
        digits = re.sub(r"\D", "", value)
        return digits[-9:]
    return re.sub(r"^https?://(?:www\.)?|/+$", "", value.strip().lower())


def _keep_proven_contacts(merged: dict, proof_text: str) -> list[str]:
    """Kontak (nomor, email, URL) hanya dipakai bila juga terbaca OCR/regex dari sumber asli.

    Pembacaan AI vision membantu nama dan alamat, tetapi bisa salah menyalin angka; nomor yang
    hanya ada di bacaan AI tidak boleh dicek ke Who Calls atau masuk graf penipuan. Yang dibuang
    dikembalikan supaya laporan bisa menulis "dibaca AI saja"."""
    proof = extract_entities_from_text(_clean_text_for_ner(proof_text) or proof_text)
    ai_only: list[str] = []
    for kind in ("phones", "emails", "urls"):
        proven = {_contact_key(kind, v) for v in proof.get(kind) or [] if isinstance(v, str)}
        kept = []
        for v in merged.get(kind) or []:
            if not isinstance(v, str) or _contact_key(kind, v) in proven:
                kept.append(v)
            else:
                ai_only.append(v)
        merged[kind] = kept
    return ai_only


async def _extract_entities_hybrid(text: str, proof_text: str | None = None) -> dict:
    """NER hibrida: regex untuk entitas struktural (nomor, email, URL, nominal),
    LLM untuk entitas semantik (perusahaan, alamat, lokasi, gaji), lalu divalidasi.

    Validasi setelah merge membuat format loker baru tidak perlu pola regex baru:
    - grounding: entitas LLM yang tidak tertulis di teks dibuang (anti-halusinasi);
    - saringan sampah: kata umum seperti "Kerja", "Kompetitif" dibuang;
    - gaji wajib memuat angka atau UMR/UMK/UMP.
    Regex semantik hanya menjadi cadangan saat LLM tidak tersedia.
    """
    if proof_text is None and VISION_MARKER in (text or ""):
        proof_text = text.split(VISION_MARKER)[0]
    clean_text = _clean_text_for_ner(text) or text

    regex_entities, llm_extracted = await asyncio.gather(
        asyncio.to_thread(extract_entities_from_text, clean_text),
        _run_llm_ner(clean_text),
    )

    ai_only_contacts = _keep_proven_contacts(regex_entities, proof_text) if proof_text else []

    if llm_extracted is None:
        regex_entities["companies"] = [v for v in (regex_entities.get("companies") or []) if not is_junk_entity(v)]
        regex_entities["location_candidates"] = [
            v for v in (regex_entities.get("location_candidates") or []) if not is_junk_location(v)
        ]
        regex_entities["_ner_meta"] = {
            "used": False,
            "source": "regex_fallback",
            "validation_applied": True,
            "ai_only_contacts": ai_only_contacts,
        }
        return regex_entities

    merged = copy.deepcopy(regex_entities)
    dropped: dict[str, list[str]] = {"ungrounded": [], "junk": []}

    def accept(values: list[str]) -> list[str]:
        kept = []
        for v in values or []:
            if not isinstance(v, str) or not v.strip():
                continue
            if is_junk_entity(v):
                dropped["junk"].append(v)
            elif not _is_grounded(v, clean_text):
                dropped["ungrounded"].append(v)
            else:
                kept.append(v.strip())
        return kept

    # Perusahaan: LLM diutamakan bila lolos grounding; jika tidak ada yang lolos, pakai regex.
    llm_companies = accept(llm_extracted.get("companies") or [])
    regex_companies = [v for v in (merged.get("companies") or []) if not is_junk_entity(v)]
    merged["companies"] = _dedupe_companies(
        uniq_casefold(_merge_company_fragments(llm_companies or regex_companies, clean_text))
    )
    # Nama pemberi kerja dari data terstruktur portal ("Perusahaan: X", dari schema.org JobPosting)
    # diutamakan di atas tebakan dari OCR logo/banner, karena nama pertama yang dicari OSINT.
    declared = re.search(r"^Perusahaan(?:/Pengiklan)?:\s*(.+)$", clean_text, re.M)
    if declared and declared.group(1).strip():
        name = declared.group(1).strip()
        merged["companies"] = [name] + [c for c in merged["companies"] if c.casefold() != name.casefold()]

    if VISION_MARKER in text:
        merged["companies"] = _drop_ocr_misreads(merged["companies"], text.split(VISION_MARKER, 1)[1])

    # Alamat: harus lolos grounding dan terlihat seperti alamat fisik.
    llm_addresses = [v for v in accept(llm_extracted.get("addresses") or []) if _is_plausible_address(v)]
    regex_addresses = [v for v in (merged.get("addresses") or []) if _is_plausible_address(v)]
    merged["addresses"] = _uniq(llm_addresses or regex_addresses)

    # Lokasi: gabungan keduanya, tanpa sampah, tanggal, atau jam.
    locations = list(merged.get("location_candidates") or [])
    locations += accept(llm_extracted.get("location_candidates") or [])
    dropped["junk"] += [v for v in locations if is_junk_location(v)]
    merged["location_candidates"] = [
        v for v in uniq_casefold([v for v in locations if not is_junk_location(v)])
        if not _DATE_TIME_JUNK.search(v) and not _DATE_PATTERNS.search(v)
    ]

    # Gaji: gabungan keduanya, wajib memuat angka atau UMR/UMK/UMP.
    salaries = (merged.get("salaries") or []) + accept(llm_extracted.get("salaries") or [])
    merged["salaries"] = _dedupe_salaries([v for v in _uniq(salaries) if _SALARY_HINT.search(v)])
    dropped["junk"] += [v for v in _uniq(salaries) if not _SALARY_HINT.search(v)]

    if merged.get("emails"):
        merged["emails"] = _uniq([fix_email_ocr_typos(e) for e in merged["emails"] if e])
    if merged.get("urls"):
        merged["urls"] = [u for u in _uniq(merged["urls"]) if not re.search(r"^(?:[a-zA-Z]\.com|gmail|yahoo|gmai|gamil)\.", u, re.I)]
    if merged.get("phones"):
        merged["phones"] = _uniq(merged["phones"])

    added = {
        "companies": bool(llm_companies),
        "addresses": bool(llm_addresses),
        "location_candidates": any(v in merged["location_candidates"] for v in (llm_extracted.get("location_candidates") or [])),
        "salaries": any(v in merged["salaries"] for v in (llm_extracted.get("salaries") or [])),
    }
    merged["_ner_meta"] = {
        "used": True,
        "source": "hybrid_llm_regex" if any(added.values()) else "llm_no_new",
        "added": added,
        "validation_applied": True,
        "dropped_ungrounded": _uniq(dropped["ungrounded"]),
        "dropped_junk": _uniq(dropped["junk"]),
        "ai_only_contacts": ai_only_contacts,
    }
    merged["_content"] = llm_extracted.get("content") or {}
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
    # Classifier sudah menaruh sinyal teks di entities["_text_signals"] sebelum OSINT,
    # sehingga runner bisa memutuskan apakah isi tag GetContact perlu dibaca (kuota 1/hari).
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
    addr_validations = osint_results.get("address_validations") or []
    log = logging.getLogger(__name__)

    # Alamat dari pencarian web TIDAK ditulis ke entities["addresses"]: laporan harus tetap jujur
    # bahwa lowongan tidak mencantumkan alamat. Alamat itu disimpan terpisah dan, bila dipetakan,
    # ditandai address_source="web_search".
    entities["web_addresses"] = osint_addresses[:3]

    best_osint_addr = None
    if existing_addresses:
        street_pattern = re.compile(r"\b(?:jl\.?|jln\.?|jalan)\b", re.I)
        # Hanya alamat web yang memperjelas alamat lowongan (bagian depannya sama, lebih lengkap).
        for osint_addr in sorted(osint_addresses, key=lambda a: bool(street_pattern.search(a)), reverse=True):
            for ner_addr in existing_addresses:
                ner_first = ner_addr.lower().split(",")[0].strip()
                if len(osint_addr) > len(ner_addr) and ner_first and ner_first in osint_addr.lower():
                    best_osint_addr = osint_addr
                    break
            if best_osint_addr:
                break
    else:
        best_osint_addr = osint_addresses[0]

    if not best_osint_addr:
        return entities

    prev_match = (addr_validations[0].get("address_details") or {}).get("match_level", "") if addr_validations else ""
    if prev_match not in ("", "area"):
        log.info("[osint_enrich] alamat lowongan sudah %s, tidak divalidasi ulang", prev_match)
        return entities

    try:
        from app.services.osint.address_validator import validate_address_and_business
        company = (entities.get("companies") or [""])[0]
        web = osint_results.get("web") or {}
        web_results = [
            r for s in (web.get("searches") or []) for r in (s.get("results") or []) if isinstance(r, dict)
        ]
        new_validation = await validate_address_and_business(best_osint_addr, company, web_results)
        new_match = (new_validation.get("address_details") or {}).get("match_level", "")
        log.info("[osint_enrich] validasi alamat web %s → %s", best_osint_addr, new_match)
        if new_match in ("exact", "street", "business") or (new_match == "area" and not addr_validations):
            new_validation["address_source"] = "web_search" if not existing_addresses else "posting_address_refined"
            addr_validations.insert(0, new_validation)
            osint_results["address_validations"] = addr_validations
    except Exception as exc:
        log.warning("[osint_enrich] validasi alamat web gagal: %s", exc)
    return entities


def attach_shap_explanation(
    analysis: dict,
    entities: dict,
    osint_results: dict | None = None,
) -> dict | None:
    """Hitung atribusi skor dan simpan di analysis, sebelum kasus disimpan ke DB."""
    try:
        shap_explanation = explain_verification_shap(
            risk_score=int(analysis.get("risk_score") or 0),
            verdict=analysis.get("verdict", "ERROR"),
            osint_results=osint_results or {},
            risk_factors=analysis.get("risk_factors") or [],
            safe_factors=analysis.get("safe_factors") or [],
            nlp_result=(
                analysis.get("nlp_result")
                if (analysis.get("nlp_result") or {}).get("enabled") is True
                else None
            ),
            network_context=analysis.get("network_context"),
            entities=entities,
            model_used=analysis.get("model_used"),
            guard_rule=(
                "brand_impersonation" if analysis.get("brand_impersonation_guard")
                else "telegram" if analysis.get("calibrated_telegram")
                else "fraud_site" if analysis.get("calibrated_fraud_site")
                else "dead_domain" if analysis.get("calibrated_dead_domain")
                else "unknown_search" if analysis.get("calibrated_unknown_search")
                else None
            ),
        )
    except Exception as exc:
        logging.getLogger(__name__).warning("SHAP explanation gagal: %s", exc)
        shap_explanation = None
    analysis["shap_explanation"] = shap_explanation
    return shap_explanation


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

    shap_explanation = analysis.get("shap_explanation") or attach_shap_explanation(
        analysis, entities, osint_results
    )

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
        input_notes=(osint_results or {}).get("input_notes") or [],
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

def _dedupe_salaries(values: list[str]) -> list[str]:
    """Regex menulis "Rp3.500.000–Rp4.500.000", LLM menulis "± Rp3.500.000–Rp4.500.000":
    angka yang sama dihitung sekali, versi pertama (regex) yang dipertahankan."""
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = "-".join(re.findall(r"\d+", re.sub(r"(?<=\d)[.,](?=\d{3})", "", value))) or value.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out
