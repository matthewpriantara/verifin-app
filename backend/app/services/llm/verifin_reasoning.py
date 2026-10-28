from app.services.llm.client import chat_completion, check_llm_status, extract_json_from_response
from app.services.llm.prompt_builder import build_text_verify_prompt, build_verify_prompt
from app.config import LLM_MODEL, LLM_TIMEOUT

REASONING_BUDGET_SEC = 55.0
from app.services.constants import FREE_EMAIL_DOMAINS
from app.services.osint.getcontact import fraud_tag_summary
from app.services import site_kinds
import re as _re
import logging
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

def _has_hard_risk_evidence(entities: dict, osint_results: dict, text_signals: dict | None = None) -> bool:
    phones = osint_results.get("phones") or []
    web = osint_results.get("web") or {}
    network = osint_results.get("fraud_network") or {}
    community = network.get("community_reports") or {}
    signals = text_signals or {}
    gforms = web.get("gform_inspections") or []
    # Sinyal biaya bisa datang dari regex nominal (fee_requests) atau classifier teks
    # ("bayar biaya pendaftaran 150rb via DANA" tidak berformat Rp).
    has_fee = (
        bool(entities.get("fee_requests"))
        or bool((entities.get("extraction_meta") or {}).get("has_fee_request"))
        or bool(entities.get("has_fee_request"))
        or bool(signals.get("has_fee_request"))
    )
    return bool(
        has_fee
        or any(
            p.get("reported_fraud")
            or p.get("scam_confirmed")
            or p.get("reputation_status") == "FLAGGED"
            for p in phones if isinstance(p, dict)
        )
        or any(f.get("risk_flags") for f in gforms if isinstance(f, dict))
        or any(web_search.get("risk_flags") for web_search in web.get("searches") or [])
        or network.get("entity_in_fraud_network")
        or int(community.get("report_count") or 0) > 0
        # Dua tag GetContact atau lebih yang memuat kata penipuan (satu tag bisa salah tandai).
        or fraud_tag_summary(phones)[0] >= 2
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
        or int((web.get("scam_check") or {}).get("warnings") or 0) > 0
        or social_counts.get("public_posts", 0) > 0
        or social_counts.get("public_profiles", 0) > 0
        or web.get("websites")
    )


def _phone_reputation_state(osint_results: dict) -> str:
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


_STRONG_TEXT_SIGNALS = (
    "has_fee_request",
    "has_foreign_work",
    "brand_unofficial_channel",
    "anonymous_employer_claim",
    "has_telegram_apply",
)


def _calibrate_unknown_search_output(
    parsed: dict, entities: dict, osint_results: dict, text_signals: dict | None = None
) -> dict:
    """Bila semua pencarian kosong dan tidak ada bukti apa pun, skor tinggi dari LLM diturunkan:
    "tidak ada data" bukan bukti penipuan. Tidak berlaku bila teks sendiri memuat sinyal kuat
    (biaya, kerja luar negeri, pencatutan BUMN, mengaku perusahaan tanpa nama)."""
    signals = text_signals or {}
    if (
        not _search_has_only_unknown(osint_results)
        or _has_public_evidence(osint_results)
        or _has_hard_risk_evidence(entities, osint_results, signals)
        or any(signals.get(k) for k in _STRONG_TEXT_SIGNALS)
    ):
        return parsed
    if parsed.get("verdict") == "BAHAYA" or float(parsed.get("risk_score") or 0) >= 40:
        parsed["verdict"] = "AMAN"
        parsed["risk_score"] = 28
        parsed["calibrated_unknown_search"] = True
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


def _floor_dead_application_domain(parsed: dict, osint_results: dict) -> dict:
    """Domain tempat melamar (email/tautan di lowongan) tidak punya DNS sama sekali, dan tidak ada
    situs lain yang hidup: hasil minimal WASPADA 45.

    Pola pencatutan yang ditolak LokerJogja.ID (27 Okt 2026): penipu memakai nama usaha nyata
    ("Roemah Boenga") dengan domain buatan (roemahboenga.store) yang tidak pernah dipasang. Jejak
    Instagram/Facebook usaha aslinya ditemukan, dan AI menilai AMAN 28 walau bukti menjumlah 52;
    jejak usaha asli tidak membuktikan domain lamaran itu milik usaha tersebut."""
    websites = (osint_results.get("web") or {}).get("websites") or []
    dead = [w for w in websites if w.get("website_status") == "NOT_FOUND"]
    alive = any(w.get("website_status") == "AVAILABLE" for w in websites)
    if not dead or alive or float(parsed.get("risk_score") or 0) >= 40:
        return parsed
    parsed["verdict"] = "WASPADA"
    parsed["risk_score"] = 45
    parsed["calibrated_dead_domain"] = True
    factor = "Domain tempat melamar tidak terdaftar di DNS; jejak usaha yang ditemukan belum terbukti terhubung dengan domain itu"
    parsed["risk_factors"] = [factor] + [f for f in parsed.get("risk_factors") or [] if f != factor]
    return parsed


_BRAND_IMPERSONATION_LABEL = "Pencatutan Merek: Jalur Lamaran di Luar Domain Resmi"


def _brand_impersonation_evidence(parsed: dict, entities: dict, osint_results: dict, text_signals: dict | None) -> dict | None:
    """Merek yang punya domain resmi, tetapi jalur lamaran di luar domain itu, plus satu bukti lain.

    Syaratnya sengaja tiga lapis supaya UMKM tanpa domain resmi (Morgans Kebab, Excelland, Dekayu)
    tidak ikut kena. Yang diperiksa hanya sinyal yang sudah dihitung sistem, bukan tebakan LLM.
    """
    web = osint_results.get("web") or {}
    domain_info = osint_results.get("domain") or {}
    signals = text_signals or {}
    phones = [p for p in (osint_results.get("phones") or []) if isinstance(p, dict)]
    emails = entities.get("emails") or []

    official_domains: set[str] = set()
    for site in web.get("websites") or []:
        url = str(site.get("url") or "")
        host = _re.sub(r"^https?://(?:www\.)?", "", url).split("/")[0].lower()
        if host and site.get("website_status") == "AVAILABLE" and not site.get("social_profile_found"):
            official_domains.add(host)
    # Poster palsu tidak pernah mencantumkan situs resmi merek; domain resmi dinilai di tahap OSINT
    # Dari hasil pencarian (osint/official_domain.py).
    official_domains |= {str(c.get("domain")) for c in web.get("official_domains") or [] if c.get("domain")}
    official_domains = {d for d in official_domains if not site_kinds.is_third_party(d)}
    if not official_domains:
        return None
    # Lowongan yang mengundang pelamar datang ke alamat fisik bukan pola pencatutan merek daring
    # (kasus negatif N1: cabang ritel memakai Gmail tetapi walk-in di kantor cabang).
    if signals.get("has_walk_in") and signals.get("has_address"):
        return None

    apply_domains = {e.split("@")[-1].lower() for e in emails if "@" in e}
    open_domain = (web.get("open_registration_domain") or {}).get("domain")
    shortener_fail = any("pemendek URL" in str(f) for f in (web.get("risk_flags") or [])) or bool(
        web.get("vision_shortener_failures")
    )
    unofficial = bool(
        apply_domains & set(FREE_EMAIL_DOMAINS)
        or open_domain
        or shortener_fail
        or (apply_domains and not (apply_domains & official_domains))
    )
    if not unofficial:
        return None

    extra: list[str] = []
    if domain_info.get("is_new"):
        extra.append("domain baru")
    if any(w.get("website_status") == "NOT_FOUND" for w in web.get("websites") or []):
        extra.append("domain mati")
    if int((web.get("scam_check") or {}).get("warnings") or 0) > 0:
        extra.append("artikel pencatutan")
    if any((p.get("getcontact") or {}).get("community_level") == "UNKNOWN" for p in phones):
        extra.append("nomor tanpa tag komunitas")
    if (web.get("fraud_site_content") or {}).get("matches"):
        extra.append("isi situs penipuan")
    if signals.get("has_telegram_apply"):
        extra.append("lamaran via Telegram")
    if not extra:
        return None

    # Nama BUMN/Tbk dengan artikel pencatutan minimal 3 adalah pola yang sudah terbukti.
    scam_warnings = int((web.get("scam_check") or {}).get("warnings") or 0)
    brand_claim = bool(signals.get("brand_unofficial_channel")) or bool(
        _re.search(r"\b(?:bumn|persero|tbk)\b", " ".join(str(c) for c in entities.get("companies") or []), _re.I)
    )
    severity = "BAHAYA" if (brand_claim and scam_warnings >= 3) else "WASPADA"
    floor = 75 if severity == "BAHAYA" else 68
    return {"floor": floor, "verdict": severity, "extra": extra, "official": sorted(official_domains)[:2]}


def _apply_brand_impersonation(
    parsed: dict, entities: dict, osint_results: dict, text_signals: dict | None
) -> dict:
    """Naikkan skor ke minimal WASPADA 68, atau BAHAYA 75 untuk pola BUMN + artikel pencatutan."""
    evidence = _brand_impersonation_evidence(parsed, entities, osint_results, text_signals)
    if not evidence:
        return parsed
    web = osint_results.setdefault("web", {})
    web["brand_impersonation"] = {
        "official_domains": evidence["official"],
        "extra_evidence": evidence["extra"],
        "floor": evidence["floor"],
    }
    if float(parsed.get("risk_score") or 0) >= evidence["floor"]:
        parsed["brand_impersonation_guard"] = True
        return parsed
    parsed["verdict"] = evidence["verdict"]
    parsed["risk_score"] = evidence["floor"]
    parsed["brand_impersonation_guard"] = True
    detail = ", ".join(evidence["extra"][:3])
    factor = (
        f"{_BRAND_IMPERSONATION_LABEL}: merek punya domain resmi ({', '.join(evidence['official'])}), "
        f"tetapi jalur lamaran di luar domain itu ({detail})"
    )
    parsed["risk_factors"] = [factor] + [f for f in parsed.get("risk_factors") or [] if f != factor]
    return parsed


def _floor_telegram_channel(parsed: dict, text_signals: dict | None) -> dict:
    """Lamaran yang diarahkan ke Telegram dinilai minimal WASPADA 55.

    Masukan praktisi portal loker (LokerJogja.id, 27 Okt 2026): loker asli memakai WhatsApp,
    email, formulir, atau walk-in; "kalau mengarah ke Telegram, 90% penipuan". LLM kadang tetap
    menilai AMAN karena tidak ada bukti keras, jadi skornya dinaikkan sebagai aturan pengaman."""
    if not (text_signals or {}).get("has_telegram_apply"):
        return parsed
    if float(parsed.get("risk_score") or 0) >= 55:
        parsed["calibrated_telegram"] = True
        return parsed
    parsed["verdict"] = "WASPADA"
    parsed["risk_score"] = 55
    parsed["calibrated_telegram"] = True
    factor = "Lamaran diarahkan ke Telegram, bukan kanal resmi perusahaan"
    parsed["risk_factors"] = [factor] + [
        f for f in parsed.get("risk_factors") or [] if f != factor
    ]
    return parsed


def _floor_fraud_site_content(parsed: dict, osint_results: dict) -> dict:
    """Website lamaran memuat pola penipuan tugas/komisi → minimal WASPADA 55.

    F1 (New Trendy) pernah WASPADA 65 pada satu run dan AMAN 12 pada run berikutnya karena
    LLM/penjelajah situs tidak selalu berhasil membaca isi halaman. Bila isi halaman terbaca
    dan memuat pola itu, skornya tidak boleh turun lagi."""
    matches = ((osint_results.get("web") or {}).get("fraud_site_content") or {}).get("matches") or []
    if not matches or float(parsed.get("risk_score") or 0) >= 55:
        return parsed
    parsed["verdict"] = "WASPADA"
    parsed["risk_score"] = 55
    parsed["calibrated_fraud_site"] = True
    factor = "Isi website lamaran memuat pola penipuan tugas/komisi"
    parsed["risk_factors"] = [factor] + [f for f in parsed.get("risk_factors") or [] if f != factor]
    return parsed


def _has_corrupt_text(
    text: str,
    entities: dict | None = None,
    allowed_tokens: set[str] | None = None,
) -> bool:
    if not isinstance(text, str) or not text.strip():
        return True
    if "�" in text or _re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", text):
        return True
    # Tanda baca menempel huruf menandakan kalimat terpotong/rusak, kecuali di email, domain, dan URL
    # ("hrd@gmail.com", "posindonesia.co.id") yang sah dipakai sebagai bukti.
    without_refs = _re.sub(r"\S+@\S+|(?:https?://)?(?:[\w-]+\.)+[a-z]{2,}(?:/\S*)?", " ", text, flags=_re.I)
    if _re.search(r"(?<!\s)[,:;.!?](?=[A-Za-z])", without_refs):
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


def _fallback_analysis(
    entities: dict, osint_results: dict, reason: str = "", text_signals: dict | None = None
) -> dict:
    """Penilaian berbasis aturan saat LLM gagal. Memakai bukti yang sama dengan LLM: sinyal teks,
    reputasi nomor, laporan komunitas, dan riwayat kasus."""
    signals = text_signals or {}
    comp_name = (entities.get("companies") or ["Perusahaan"])[0]
    phones = [p for p in (osint_results.get("phones") or []) if isinstance(p, dict)]
    has_fraud_phone = any(
        p.get("reported_fraud") or p.get("scam_confirmed") or p.get("reputation_status") == "FLAGGED"
        for p in phones
    )
    phone_checked_clean = any(
        p.get("probe_status") == "COMPLETED" and p.get("reputation_status") == "CLEAN" for p in phones
    )
    has_free_email = any(
        "@" in e and e.split("@")[-1].lower() in FREE_EMAIL_DOMAINS
        for e in (entities.get("emails") or [])
    )
    has_address = any(
        (item.get("address_found") or item.get("found"))
        and (item.get("match_level") or (item.get("address_details") or {}).get("match_level")) == "exact"
        and item.get("address_source") in (None, "posting_address", "posting_address_refined")
        for item in (osint_results.get("address_validations") or [])
        if isinstance(item, dict)
    )
    network = osint_results.get("fraud_network") or {}
    approved_reports = int((network.get("community_reports") or {}).get("report_count") or 0)
    scam_warnings = int(((osint_results.get("web") or {}).get("scam_check") or {}).get("warnings") or 0)
    has_fee = _has_hard_risk_evidence({**entities, "fee_requests": entities.get("fee_requests")}, {}, signals)

    risk_score = 12
    risk_factors: list[str] = []
    safe_factors: list[str] = []

    if has_fee:
        risk_score += 65
        risk_factors.append("Lowongan meminta biaya atau transfer kepada pelamar.")
    if has_fraud_phone:
        risk_score += 65
        risk_factors.append("Nomor kontak tercatat dalam laporan penipuan publik.")
    elif phone_checked_clean:
        safe_factors.append("Tidak ditemukan laporan penipuan pada Kaspersky Who Calls.")
    if approved_reports:
        risk_score += 40
        risk_factors.append("Pernah dilaporkan komunitas dan disetujui admin.")
    if network.get("entity_in_fraud_network"):
        risk_score += 30
        risk_factors.append("Nomor/email sama dengan kasus berbahaya lain.")
    if signals.get("has_foreign_work"):
        risk_score += 25
        risk_factors.append("Menawarkan kerja di luar negeri.")
    if signals.get("brand_unofficial_channel"):
        risk_score += 25
        risk_factors.append("Mengatasnamakan BUMN lewat kanal tidak resmi.")
    elif signals.get("has_whatsapp_apply"):
        risk_score += 15
        risk_factors.append("Pendaftaran hanya lewat WhatsApp pribadi.")
    if signals.get("anonymous_employer_claim"):
        risk_score += 15
        risk_factors.append("Tidak menyebut nama perusahaan yang bisa dicek.")
    if signals.get("has_telegram_apply"):
        risk_score += 25
        risk_factors.append("Lamaran diarahkan ke Telegram, bukan kanal resmi perusahaan.")
    if scam_warnings:
        risk_score += 15
        risk_factors.append("Nama perusahaan pernah dicatut lowongan palsu.")
    web = osint_results.get("web") or {}
    if (web.get("fraud_site_content") or {}).get("matches"):
        risk_score += 25
        risk_factors.append("Isi website lamaran memuat pola penipuan tugas/komisi.")
    if (web.get("open_registration_domain") or {}).get("domain"):
        risk_score += 15
        risk_factors.append("Domain bebas daftar dipakai mengatasnamakan badan usaha/merek.")
    if (web.get("location_mismatch") or {}).get("profile_city"):
        risk_score += 10
        risk_factors.append("Profil publik usaha berada di kota lain dari alamat lowongan.")
    if any(w.get("website_status") in ("NOT_FOUND", "HTTP_ERROR") for w in web.get("websites") or []):
        risk_score += 20
        risk_factors.append("Situs lamaran tidak dapat diakses atau tidak terdaftar.")
    if (osint_results.get("domain") or {}).get("is_new"):
        risk_score += 10
        risk_factors.append("Domain lamaran baru dibuat (kurang dari 90 hari).")
    getcontact = next(
        (
            p.get("getcontact") for p in phones
            if isinstance(p.get("getcontact"), dict) and p["getcontact"].get("probe_status") == "COMPLETED"
        ),
        None,
    )
    if getcontact:
        if getcontact.get("spam_flagged"):
            risk_score += 15
            risk_factors.append("Nomor ditandai spam oleh komunitas GetContact.")
        elif getcontact.get("community_level") == "UNKNOWN":
            risk_score += 10
            risk_factors.append("Nomor belum dikenal komunitas GetContact.")
        elif getcontact.get("community_level") == "WELL_KNOWN":
            risk_score -= 5
            safe_factors.append("Nomor dikenal luas di komunitas GetContact.")
    tag_hits, tag_terms = fraud_tag_summary(phones)
    if tag_hits >= 2:
        risk_score += 20
        risk_factors.append(f"{tag_hits} tag GetContact untuk nomor ini memuat kata penipuan ({', '.join(tag_terms)}).")
    elif tag_hits == 1:
        risk_score += 10
        risk_factors.append(f"Satu tag GetContact untuk nomor ini memuat kata penipuan ({', '.join(tag_terms)}).")
    if has_free_email:
        risk_score += 8
        risk_factors.append(f"Email kontak ({entities.get('emails', [''])[0]}) memakai layanan gratisan.")
    if has_address:
        risk_score -= 6
        safe_factors.append("Jalan dan nomor alamat cocok dengan hasil peta.")

    risk_score = max(0, min(100, risk_score))
    verdict = "AMAN" if risk_score < 40 else "WASPADA" if risk_score < 75 else "BAHAYA"
    verdict_label = {"AMAN": "berisiko rendah", "WASPADA": "perlu diperiksa lebih lanjut", "BAHAYA": "berisiko tinggi"}[verdict]
    summary = (
        f"Penilaian berbasis aturan (penalaran AI tidak tersedia): lowongan {comp_name} dinilai {verdict_label}."
    )

    parsed = {
        "verdict": verdict,
        "risk_score": risk_score,
        "corrected_company_name": None,
        "summary": summary,
        "risk_factors": risk_factors[:4],
        "safe_factors": safe_factors[:3],
        "recommendations": [
            "Pastikan wawancara di lokasi resmi perusahaan.",
            "Jangan membayar biaya apa pun.",
        ],
        "model_used": f"{LLM_MODEL} (Rule-Based Fallback)",
        "entities_analyzed": entities,
    }
    # Aturan pengaman tetap berlaku walau LLM gagal: skor tidak boleh turun di bawah bukti keras.
    parsed = _floor_dead_application_domain(parsed, osint_results)
    parsed = _floor_fraud_site_content(parsed, osint_results)
    parsed = _floor_telegram_channel(parsed, signals)
    return _apply_brand_impersonation(parsed, entities, osint_results, signals)


def _is_valid_llm_output(
    parsed: dict,
    entities: dict | None = None,
    allowed_tokens: set[str] | None = None,
) -> bool:
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
            if len(words) == 1 and len(t) > 15:
                return False
            if _has_corrupt_text(t, entities, allowed_tokens):
                return False
    return True


# Label AMAN bukan jaminan legalitas, jadi ringkasan tidak boleh memberi status hukum
# yang tidak dibuktikan pemeriksaan (prompt melarangnya; ini jaring pengaman).
_SUMMARY_CLAIM_FIXES = (
    (_re.compile(r"\b(lowongan|perusahaan)\s+(?:resmi|terpercaya|legal|sah)\b", _re.I), r"\1"),
    (_re.compile(r"\b(?:yang\s+)?terverifikasi\b", _re.I), "yang tercatat di sumber publik"),
    (_re.compile(r"\bpasti\s+aman\b", _re.I), "tanpa tanda bahaya"),
    (_re.compile(r"\b(jejak digital|jejak publik|data|domain|alamat|nomor)\s+(?:yang\s+)?valid\b", _re.I), r"\1 yang konsisten"),
    (_re.compile(r"\b(domain|situs|website|akun|email|kanal|profil|portal)\s+resmi\b", _re.I), r"\1"),
    (_re.compile(r"\s*\b(?:sangat\s+|cukup\s+)?(?:kredibel|terpercaya)\b", _re.I), ""),
)


def _soften_summary_claims(text: str) -> str:
    for pattern, repl in _SUMMARY_CLAIM_FIXES:
        text = pattern.sub(repl, text)
    text = _re.sub(r"\s{2,}", " ", text).strip()
    return text[:1].upper() + text[1:] if text else text


def _sanitize_llm_output(
    parsed: dict,
    entities: dict,
    osint_results: dict,
    allowed_tokens: set[str] | None = None,
) -> dict:
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
        "Email resmi perusahaan": "Email perusahaan yang tercantum",
        "email resmi perusahaan": "email perusahaan yang tercantum",
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
        "Nomor HP terkonfirmasi bersih di Kaspersky": "Tidak ditemukan laporan fraud pada Kaspersky Who Calls",
        "Nomor HP terkonfirmasi bersih": "Tidak ditemukan laporan fraud pada sumber reputasi yang diperiksa",
        "Nomor HP bersih di Kaspersky": "Tidak ditemukan laporan penipuan pada Kaspersky Who Calls",
        "Nomor HP bersih": "Tidak ditemukan laporan penipuan pada sumber reputasi yang diperiksa",
        "Nomor terkonfirmasi bersih di Kaspersky": "Tidak ditemukan laporan penipuan pada Kaspersky Who Calls",
        "Nomor terkonfirmasi bersih": "Tidak ditemukan laporan penipuan pada sumber reputasi yang diperiksa",
        "Ditemukan jejak bisnis publik toko otomotif": "Ditemukan hasil web relevan dengan nama perusahaan",
        "Ditemukan jejak bisnis publik": "Ditemukan hasil web relevan dengan nama perusahaan",
        "memiliki jejak publik toko otomotif yang jelas": "memiliki satu hasil web yang relevan dengan nama perusahaan",
        "memiliki jejak publik yang jelas": "memiliki hasil web yang relevan dengan nama perusahaan",
        "jejak publik toko otomotif yang jelas": "hasil web yang relevan dengan nama perusahaan",
        "Tidak ada indikasi permintaan biaya pendaftaran": "Tidak ditemukan permintaan biaya pada input",
        "Pendaftaran menggunakan tautan Google Forms": "Isi Google Form belum berhasil diverifikasi",
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

    if isinstance(parsed.get("summary"), str):
        parsed["summary"] = _soften_summary_claims(parsed["summary"])

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
        parsed["safe_factors"] = [
            item for item in (parsed.get("safe_factors") or [])
            if isinstance(item, str)
            and "diperiksa kaspersky" not in item.lower()
            and "tidak ditemukan laporan" not in item.lower()
        ][:3]

    if canonical_company:
        parsed["corrected_company_name"] = None
    return parsed


def _mark_social_link_status(osint_results: dict, entities: dict, raw_text: str, text_signals: dict) -> None:
    """Tandai apakah akun medsos yang ditemukan memang ditautkan lowongan.

    Akun hasil pencarian nama (mis. akun resmi Pos Indonesia) tidak membuktikan lowongan
    atas nama itu asli; penipu justru memakai nama merek besar. Penanda ini dipakai prompt
    dan halaman laporan.
    """
    social = osint_results.get("social")
    if not isinstance(social, dict):
        return
    haystack = " ".join([raw_text.lower(), *[str(u).lower() for u in entities.get("urls") or []]])
    linked = []
    for profile in social.get("profiles") or []:
        url = str(profile.get("url") or "").lower()
        handle = url.rstrip("/").rsplit("/", 1)[-1].lstrip("@")
        if handle and (handle in haystack or url in haystack):
            linked.append(profile.get("url"))
    social["linked_profiles"] = linked
    social["found_by_name_only"] = bool(social.get("profiles")) and not linked
    social["brand_impersonation_risk"] = bool(text_signals.get("brand_unofficial_channel"))


async def analyze_with_verifin(
    entities: dict,
    osint_results: dict | None = None,
    raw_text: str | None = None,
    text_signals: dict | None = None,
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

    _mark_social_link_status(osint_results, entities, raw_text or "", text_signals or {})

    if raw_text:
        prompt = build_text_verify_prompt(raw_text, entities, osint_results, text_signals)
    else:
        prompt = build_verify_prompt(entities, osint_results, text_signals)
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

    # Anggaran waktu total untuk penalaran. Jalur teks/gambar tidak memakai SSE, dan Cloudflare
    # memutus permintaan sekitar 100 detik; lebih baik jatuh ke penilaian aturan daripada 524.
    import asyncio as _asyncio
    loop = _asyncio.get_running_loop()
    deadline = loop.time() + REASONING_BUDGET_SEC
    try:
        parsed = None
        for attempt in range(3):
            remaining = deadline - loop.time()
            if remaining < 8:
                logger.warning("Anggaran waktu LLM habis setelah %d percobaan — fallback aturan.", attempt)
                break
            raw = await _asyncio.wait_for(
                chat_completion(
                    messages=messages,
                    model=LLM_MODEL,
                    temperature=0.0,
                    max_tokens=8192,
                    seed=42,
                    timeout=min(LLM_TIMEOUT, remaining),
                    max_retries=2,
                ),
                timeout=remaining,
            )
            parsed = extract_json_from_response(raw)
            parsed = _sanitize_llm_output(parsed, entities, osint_results, allowed_tokens)
            parsed = _calibrate_unknown_search_output(parsed, entities, osint_results, text_signals)
            parsed = _floor_dead_application_domain(parsed, osint_results)
            parsed = _floor_fraud_site_content(parsed, osint_results)
            parsed = _floor_telegram_channel(parsed, text_signals)
            parsed = _apply_brand_impersonation(parsed, entities, osint_results, text_signals)
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
        if parsed is None:
            return _fallback_analysis(entities, osint_results, reason="timeout", text_signals=text_signals)
        parsed["model_used"] = f"{LLM_MODEL} (Evidence Reasoning)"
        if not _is_valid_llm_output(parsed, entities, allowed_tokens):
            logger.warning("Semua 3 attempt LLM gagal validasi semantik — memakai fallback evidence-only.")
            parsed = _fallback_analysis(entities, osint_results, text_signals=text_signals)
        parsed["entities_analyzed"] = entities
        return parsed

    except Exception as exc:
        logger.exception("LLM reasoning gagal: %s — beralih ke fallback rule-based", exc)
        return _fallback_analysis(entities, osint_results, reason=str(exc), text_signals=text_signals)


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

