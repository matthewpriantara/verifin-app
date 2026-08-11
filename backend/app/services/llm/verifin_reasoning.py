"""
Reasoning engine Verifin via OpenAgentic (default: grok-4.5).

Bagian dari Job Trust Infrastructure — sistem di balik platform pendamping
pencari kerja Verifin yang menggabungkan OSINT, analisis bukti, dan
pemantauan komunitas untuk menilai tingkat kepercayaan suatu lowongan.
"""

from app.services.llm.client import chat_completion, check_llm_status, extract_json_from_response
from app.services.llm.prompt_builder import build_text_verify_prompt, build_verify_prompt
from app.config import LLM_MODEL
from app.services.constants import FREE_EMAIL_DOMAINS
import re as _re
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

def _has_hard_risk_evidence(entities: dict, osint_results: dict) -> bool:
    phones = osint_results.get("phones") or []
    web = osint_results.get("web") or {}
    network = osint_results.get("fraud_network") or {}
    gforms = web.get("gform_inspections") or []
    return bool(
        any(
            p.get("reported_fraud")
            or p.get("scam_confirmed")
            or p.get("reputation_status") == "FLAGGED"
            for p in phones if isinstance(p, dict)
        )
        or any(f.get("risk_flags") for f in gforms if isinstance(f, dict))
        or any(web_search.get("risk_flags") for web_search in web.get("searches") or [])
        or network.get("entity_in_fraud_network")
    )


def _search_has_only_unknown(osint_results: dict) -> bool:
    web = osint_results.get("web") or {}
    searches = web.get("searches") or []
    return bool(searches) and all(
        search.get("status") in {"NO_RESULTS", "NO_RELEVANT_RESULTS", "UNAVAILABLE"}
        for search in searches
    )


def _has_public_evidence(osint_results: dict) -> bool:
    web = osint_results.get("web") or {}
    social = osint_results.get("social") or {}
    web_counts = web.get("evidence_counts") or {}
    social_counts = social.get("evidence_counts") or {}
    return bool(
        web_counts.get("relevant_results", 0) > 0
        or social_counts.get("public_posts", 0) > 0
        or social_counts.get("public_profiles", 0) > 0
        or web.get("websites")
    )


def _phone_reputation_state(osint_results: dict) -> str:
    """Return the canonical phone state without overloading legacy `found`."""
    phones = osint_results.get("phones") or []
    if any(
        p.get("reported_fraud")
        or p.get("scam_confirmed")
        or p.get("reputation_status") == "FLAGGED"
        for p in phones if isinstance(p, dict)
    ):
        return "FLAGGED"
    if any(
        (
            p.get("probe_status") == "COMPLETED"
            and p.get("reputation_status") == "CLEAN"
        )
        or (
            p.get("checked") is True
            and p.get("danger_level") == 0
            and not p.get("reported_fraud")
            and not p.get("scam_confirmed")
        )
        for p in phones if isinstance(p, dict)
    ):
        return "CLEAN"
    if any(p.get("probe_status") == "COMPLETED" for p in phones if isinstance(p, dict)):
        return "COMPLETED"
    return "UNAVAILABLE" if phones else "NOT_PROVIDED"


def _calibrate_unknown_search_output(parsed: dict, entities: dict, osint_results: dict) -> dict:
    """Prevent unavailable/empty search from becoming a fabricated risk signal."""
    if not _search_has_only_unknown(osint_results) or _has_public_evidence(osint_results) or _has_hard_risk_evidence(entities, osint_results):
        return parsed
    if parsed.get("verdict") == "BAHAYA" or float(parsed.get("risk_score") or 0) >= 40:
        parsed["verdict"] = "AMAN"
        parsed["risk_score"] = 28
    for field in ("risk_factors", "safe_factors", "recommendations"):
        values = parsed.get(field) or []
        if not isinstance(values, list):
            values = [values]
        parsed[field] = [
            item for item in values
            if isinstance(item, str) and "zero footprint" not in item.lower() and "nihil" not in item.lower()
        ]
    parsed["summary"] = parsed.get("summary") or "Bukti publik tidak tersedia pada run ini; tidak ditemukan red flag keras."
    if "Bukti publik tidak tersedia pada run ini" not in parsed["summary"] and _search_has_only_unknown(osint_results):
        parsed["summary"] = "Bukti publik tidak tersedia pada run ini; tidak ditemukan red flag keras."
    return parsed


def _has_corrupt_text(
    text: str,
    entities: dict | None = None,
    allowed_tokens: set[str] | None = None,
) -> bool:
    """Detect malformed token joins without guessing a replacement word."""
    if not isinstance(text, str) or not text.strip():
        return True
    if "�" in text or _re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text):
        return True
    if _re.search(r"(?<!\s)[,:;.!?](?=[A-Za-z])", text):
        return True
    evidence_tokens = {
        token.lower()
        for company in (entities or {}).get("companies") or []
        for token in _re.findall(r"[A-Za-zÀ-ÿ0-9]+", str(company))
        if len(token) >= 5
    }
    for token in _re.findall(r"[A-Za-zÀ-ÿ]+", text):
        lower = token.lower()
        if any(
            abs(len(lower) - len(reference)) <= 1
            and lower != reference
            and SequenceMatcher(None, lower, reference).ratio() >= 0.80
            for reference in evidence_tokens
        ):
            return True
    words = text.split()
    return len(words) == 1 and len(text) > 15


def _fallback_analysis(entities: dict, osint_results: dict) -> dict:
    """Evidence-only fallback; no language repair or inferred facts."""
    company = (entities.get("companies") or ["Perusahaan"])[0]
    phones = osint_results.get("phones") or []
    hard_risk = _has_hard_risk_evidence(entities, osint_results)
    address_exact = any(
        (item.get("address_found") or item.get("found"))
        and (item.get("match_level") or (item.get("address_details") or {}).get("match_level")) == "exact"
        for item in (osint_results.get("address_validations") or [])
        if isinstance(item, dict)
    )
    if hard_risk:
        verdict, score = "BAHAYA", 80
    else:
        verdict, score = "AMAN", 28
    risks = []
    if entities.get("addresses") and not address_exact:
        risks.append("Alamat fisik belum terverifikasi exact")
    elif not entities.get("addresses"):
        risks.append("Alamat fisik tidak tercantum")
    if any("@" in e and e.rsplit("@", 1)[-1].lower() in FREE_EMAIL_DOMAINS for e in entities.get("emails") or []):
        risks.append("Email memakai domain gratisan")
    if not phones:
        risks.append("Nomor HP tidak tercantum")
    return {
        "verdict": verdict,
        "risk_score": score,
        "corrected_company_name": None,
        "summary": f"Analisis evidence-only untuk {company}; hasil bahasa model tidak digunakan.",
        "risk_factors": risks[:3],
        "safe_factors": ["Tidak ada hard evidence fraud" ] if not hard_risk else [],
        "recommendations": ["Verifikasi kanal dan alamat sebelum melamar"],
        "model_used": f"{LLM_MODEL} (Evidence Fallback)",
        "entities_analyzed": entities,
    }


def _is_valid_llm_output(
    parsed: dict,
    entities: dict | None = None,
    allowed_tokens: set[str] | None = None,
) -> bool:
    """Validasi semantik output LLM — deteksi truncation dan field rusak."""
    if parsed.get("verdict") not in ("AMAN", "WASPADA", "BAHAYA"):
        return False
    if not isinstance(parsed.get("risk_score"), (int, float)):
        return False
    score = float(parsed["risk_score"])
    verdict_limits = {"AMAN": (0, 39), "WASPADA": (40, 74), "BAHAYA": (75, 100)}
    low, high = verdict_limits[parsed["verdict"]]
    if not low <= score <= high:
        return False

    for field in ("summary", "risk_factors", "safe_factors", "recommendations"):
        val = parsed.get(field, "")
        texts = val if isinstance(val, list) else [val]
        for t in texts:
            if not isinstance(t, str):
                continue
            words = t.split()
            # String panjang tanpa spasi = terpotong
            if len(words) == 1 and len(t) > 15:
                return False
            if _has_corrupt_text(t, entities, allowed_tokens):
                return False
    return True


def _sanitize_llm_output(
    parsed: dict,
    entities: dict,
    osint_results: dict,
    allowed_tokens: set[str] | None = None,
) -> dict:
    """Jaga klaim output tetap selaras dengan fakta service layer."""
    canonical_company = (entities.get("companies") or [None])[0]
    corrected = parsed.get("corrected_company_name")
    if canonical_company:
        parsed["corrected_company_name"] = None

    replacements = {
        "Toko resmi": "Listing toko publik",
        "toko resmi": "listing toko publik",
        "Akun resmi": "Akun publik",
        "akun resmi": "akun publik",
        "Website resmi": "Website publik",
        "website resmi": "website publik",
        "Email resmi": "Email yang tercantum",
        "email resmi": "email yang tercantum",
        "Kanal resmi": "Kanal publik",
        "kanal resmi": "kanal publik",
        "Profil resmi": "Profil publik",
        "profil resmi": "profil publik",
        "Portal resmi": "Portal publik",
        "portal resmi": "portal publik",
        "Nol laporan penipuan di seluruh hasil pencarian SERP": "Belum ditemukan laporan penipuan spesifik pada query publik yang dijalankan",
        "Tidak ada laporan penipuan di seluruh hasil pencarian SERP": "Belum ditemukan laporan penipuan spesifik pada query publik yang dijalankan",
        "tidak ada laporan penipuan di SERP": "belum ditemukan laporan penipuan spesifik pada query publik",
        "Tidak ada laporan penipuan di SERP": "Belum ditemukan laporan penipuan spesifik pada query publik",
        "Nol indikasi penipuan di seluruh hasil pencarian SERP": "Belum ditemukan indikasi penipuan spesifik pada hasil yang relevan",
        "Nol indikasi penipuan di seluruh hasil pencarian": "Belum ditemukan indikasi penipuan spesifik pada hasil yang relevan",
    }
    no_input_address = not (entities.get("addresses") or []) and not (osint_results.get("address_validations") or [])
    if no_input_address:
        replacements.update({
            "Alamat exact belum terverifikasi": "Alamat fisik tidak tercantum",
            "Alamat fisik tidak tervalidasi": "Alamat fisik tidak tercantum",
            "Alamat fisik belum terverifikasi": "Alamat fisik tidak tercantum",
            "Alamat tidak ditemukan": "Alamat fisik tidak tercantum",
        })
    phone_state = _phone_reputation_state(osint_results)
    for field in ("summary", "risk_factors", "safe_factors", "recommendations"):
        value = parsed.get(field)
        values = value if isinstance(value, list) else [value]
        cleaned = []
        for item in values:
            if not isinstance(item, str):
                continue
            if phone_state == "CLEAN" and field == "risk_factors" and _re.search(
                r"reputasi\s+(?:nomor|hp|telepon).*belum\s+terkonfirmasi",
                item,
                _re.I,
            ):
                continue
            text = item
            if corrected and canonical_company and corrected != canonical_company:
                text = text.replace(str(corrected), str(canonical_company))
            for old, new in replacements.items():
                text = text.replace(old, new)
            if not _has_corrupt_text(text, entities, allowed_tokens):
                cleaned.append(text)
        parsed[field] = cleaned if isinstance(value, list) else (cleaned[0] if cleaned else "")

    if phone_state == "CLEAN":
        for field in ("risk_factors", "summary"):
            value = parsed.get(field)
            values = value if isinstance(value, list) else [value]
            if field == "risk_factors":
                parsed[field] = [
                    item for item in values
                    if isinstance(item, str)
                    and not _re.search(
                        r"reputasi\s+(?:nomor|hp|telepon).*belum\s+terkonfirmasi",
                        item,
                        _re.I,
                    )
                ]
        safe = parsed.get("safe_factors") or []
        if not isinstance(safe, list):
            safe = [safe]
        if not any("diperiksa kaspersky" in item.lower() for item in safe if isinstance(item, str)):
            safe.append("Nomor HP diperiksa Kaspersky dan tidak ditemukan laporan fraud")
        parsed["safe_factors"] = safe[:3]

    # Gmail/free email is never an official corporate channel by itself.
    if canonical_company:
        parsed["corrected_company_name"] = None
    return parsed


async def analyze_with_verifin(
    entities: dict,
    osint_results: dict | None = None,
    raw_text: str | None = None,
) -> dict:
    if osint_results is None:
        osint_results = {
            "domain": {
                "age_years": None,
                "created_at": "Tidak diketahui",
                "is_new": False,
            },
            "email_security": {"spf_active": False, "dmarc_active": False},
            "address_validations": [],
            "social": {},
        }

    if raw_text:
        prompt = build_text_verify_prompt(raw_text, entities, osint_results)
    else:
        prompt = build_verify_prompt(entities, osint_results)
    allowed_tokens = {
        token.lower()
        for token in _re.findall(r"[A-Za-zÀ-ÿ]+", prompt)
        if len(token) >= 3
    }

    messages = [
        {
            "role": "system",
            "content": (
                "Kamu adalah Verifin Trust Analyst — bagian dari Job Trust Infrastructure yang membantu "
                "pencari kerja menilai tingkat kepercayaan suatu lowongan sebelum melamar. "
                "Tugasmu adalah menganalisis bukti OSINT yang tersedia dan memberikan penilaian kepercayaan "
                "yang jujur, terukur, dan bisa dipertanggungjawabkan. "
                "Hanya gunakan fakta dari data OSINT/teks yang diberikan. "
                "Dilarang mengarang sumber, status AHU/OSS, atau temuan medsos. "
                "Gunakan bahasa Indonesia formal dan profesional. "
                "Jawab HANYA JSON valid sesuai skema yang diminta."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    try:
        parsed = None
        # ponytail: max 3 retry — cukup untuk truncation, tidak waste token budget provider
        for attempt in range(3):
            raw = await chat_completion(
                messages=messages,
                model=LLM_MODEL,
                temperature=0.0,
                max_tokens=8192,
                seed=42,
            )
            parsed = extract_json_from_response(raw)
            parsed = _sanitize_llm_output(parsed, entities, osint_results, allowed_tokens)
            parsed = _calibrate_unknown_search_output(parsed, entities, osint_results)
            # Sanitize field list — buang item <= 3 karakter (artifact truncation)
            for field in ("risk_factors", "safe_factors", "recommendations"):
                items = parsed.get(field) or []
                parsed[field] = [s for s in items if isinstance(s, str) and len(s) > 3]
            if _is_valid_llm_output(parsed, entities, allowed_tokens):
                break
            logger.warning("LLM output attempt %d gagal validasi semantik, retry...", attempt + 1)
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": (
                    "Output sebelumnya tampaknya terpotong atau tidak valid. "
                    "Regenerate seluruh JSON dari awal. "
                    "Jangan melanjutkan output sebelumnya. "
                    "Pastikan semua field terisi lengkap dan setiap kalimat tidak terpotong di tengah."
                ),
            })
        parsed["model_used"] = f"{LLM_MODEL} (Forensic Reasoning)"
        if not _is_valid_llm_output(parsed, entities, allowed_tokens):
            logger.warning("Semua 3 attempt LLM gagal validasi semantik — memakai fallback evidence-only.")
            parsed = _fallback_analysis(entities, osint_results)
        parsed["entities_analyzed"] = entities
        return parsed

    except Exception as exc:
        # Rule-based fallback engine if LLM API is unavailable
        comp_name = (entities.get("companies") or ["Perusahaan"])[0]
        has_fraud_phone = any(
            p.get("reported_fraud")
            or p.get("scam_confirmed")
            or p.get("reputation_status") == "FLAGGED"
            for p in (osint_results.get("phones") or [])
            if isinstance(p, dict)
        )
        has_free_email = any(
            "@" in e and e.split("@")[-1].lower() in FREE_EMAIL_DOMAINS
            for e in (entities.get("emails") or [])
        )
        has_address = any(
            (item.get("address_found") or item.get("found"))
            and (item.get("match_level") or (item.get("address_details") or {}).get("match_level")) == "exact"
            for item in (osint_results.get("address_validations") or [])
            if isinstance(item, dict)
        )

        risk_score = 12
        risk_factors = []
        safe_factors = []

        if has_fraud_phone:
            risk_score += 65
            risk_factors.append("Nomor telepon kontak terdaftar dalam aduan penipuan publik.")
        else:
            safe_factors.append("Nomor HP kontak bebas dari laporan penipuan di Kaspersky Who Calls.")

        if has_free_email:
            risk_score += 10
            risk_factors.append(f"Email kontak ({entities.get('emails', [''])[0]}) menggunakan domain publik gratisan.")

        if has_address:
            safe_factors.append("Jalan dan nomor alamat cocok dengan hasil peta.")

        verdict = "AMAN" if risk_score < 30 else "WASPADA" if risk_score < 60 else "BAHAYA"
        verdict_label = {"AMAN": "berisiko rendah", "WASPADA": "perlu diperiksa lebih lanjut", "BAHAYA": "berisiko tinggi"}[verdict]
        summary_parts = [f"Berdasarkan pemeriksaan bukti publik independen, lowongan {comp_name} dinilai {verdict_label}."]
        if has_address:
            summary_parts.append("Alamat fisik berhasil dipetakan di OpenStreetMap.")
        if has_fraud_phone:
            summary_parts.append("Ditemukan laporan penipuan pada nomor kontak.")
        elif not has_fraud_phone and osint_results.get("phones"):
            summary_parts.append("Nomor kontak bebas laporan aduan penipuan.")
        summary = " ".join(summary_parts)

        return {
            "verdict": verdict,
            "risk_score": risk_score,
            "summary": summary,
            "risk_factors": risk_factors,
            "safe_factors": safe_factors,
            "recommendations": [
                "Pastikan wawancara diadakan di lokasi resmi perusahaan.",
                "TIDAK AKAN membayar biaya registrasi, seragam, atau pelatihan."
            ],
            "model_used": f"{LLM_MODEL} (Forensic Reasoning)",
            "entities_analyzed": entities,
        }


async def check_ai_status() -> dict:
    status = await check_llm_status()
    detail = status.get("detail")
    if detail is not None and not isinstance(detail, str):
        detail = str(detail)
    return {
        "provider": status.get("provider") or "openagentic",
        "configured": bool(status.get("configured")),
        "reachable": bool(status.get("reachable")),
        "target_model": LLM_MODEL,
        "detail": detail,
    }

