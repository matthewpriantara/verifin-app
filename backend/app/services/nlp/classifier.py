from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Keywords & Regex patterns for Indonesian Job Scams (Paper22, GASA 2024, UNODC 2023)
_FEE_PATTERNS = [
    r"\b(?:biaya|uang|dana|deposit|tarif|bayar|transfer)\s+.*?(?:pendaftaran|administrasi|seleksi|tiket|akomodasi|travel|seragam|pelatihan|rekening|kembali|reimburse)\b",
    r"\b(?:mentransfer|transfer|bayar|setor)\s+.*?(?:rekening|biro|travel|panitia|bendahara|biaya)\b",
    r"\b(?:tiket|akomodasi|transportasi)\s+.*?(?:wajib|harus|ditransfer|dibayar|reimburse)\b",
    r"\b(?:uang\s*muka|uang\s*jaminan|deposit\s*awal|biaya\s*registrasi|biaya\s*formulir)\b",
]

_FOREIGN_WORK_PATTERNS = [
    r"\b(?:kamboja|cambodia|myanmar|laos|filipina|philippines|vietnam|thailand)\b",
    r"\b(?:luar\s*negeri|overseas)\b",
]

_WHATSAPP_APPLY_PATTERNS = [
    r"(?:daftar|hubungi|chat|kirim cv|kirim lamaran|kirim format)\s+(?:ke\s+)?(?:wa|whatsapp)\b",
    r"wa\.me/\d+",
    # "Kirim CV: 0896-...", "pesan WhatsApp", "WA: 0812..."
    r"(?:kirim|hubungi|daftar|chat)\s*(?:cv|lamaran|berkas)?[^\n\d]{0,25}(?:\+62|62|0)8\d",
    r"(?:pesan|via|lewat|melalui)\s+(?:wa|whatsapp)\b",
    r"\b(?:wa|whatsapp)\b\s*[:\-]?\s*(?:\+62|62|0)8\d",
    # "silakan WhatsApp admin", "konfirmasi kehadiran via WhatsApp", "daftar lewat link di bio"
    r"(?:silakan|silahkan|konfirmasi\s+\w+\s+(?:via|ke))\s+(?:wa|whatsapp)\b",
    r"\b(?:wa|whatsapp)\s+admin\b",
    # "link di bio", "link di. bio profil", "klik link dibio", "link bio", "link di profil"
    r"\blink\s+(?:yang\s+ada\s+)?(?:di\W*)?(?:bio|profil)\b",
]

# Nama BUMN/perusahaan terbuka. Nama ini mudah dicatut, jadi tidak boleh menjadi sinyal aman;
# rekrutmen resminya lewat portal karier, bukan WhatsApp admin atau tautan di bio.
_BRAND_CLAIM = re.compile(r"\b(?:bumn|persero|tbk)\b")

# Jalur lamaran resmi selain WhatsApp: email atau tautan formulir/portal.
_OFFICIAL_CHANNEL = re.compile(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}|https?://|forms\.gle|www\.", re.I)

# Badan usaha yang disebut namanya: "PT Maju Jaya", "CV. Sinar", "UD Makmur", "Koperasi ...".
# "CV" sebagai daftar riwayat hidup ("kirim CV", "CV terbaru", "CV dan KTP") tidak dihitung.
_NAMED_ENTITY = re.compile(
    r"\b(?:pt|ud|pd|koperasi|yayasan|perum|persero)\.?\s+[a-z0-9]{2,}"
    r"|(?<!kirim )(?<!kirimkan )(?<!lampirkan )(?<!sertakan )(?<!upload )(?<!unggah )(?<!berkas )"
    r"\bcv\.?\s+(?!(?:ke|dan|via|lewat|melalui|terbaru|lengkap|anda|kamu|lamaran|serta|beserta|&)\b)[a-z]{2,}"
    r"|\bnama\s+(?:perusahaan|usaha|toko|instansi)(?:\s*/\s*\w+)?\s*[:\-]\s*\S"
)

# Teks mengaku sebagai pemberi kerja berbadan usaha (pabrik, perusahaan, kantor, gudang).
_EMPLOYER_CLAIM = re.compile(r"\b(?:pabrik|perusahaan|kantor|gudang|factory|company|manufaktur)\b")

_FRAUD_KEYWORDS = [
    r"\b(?:biaya\s*pendaftaran|biaya\s*administrasi|uang\s*jaminan|deposit\s*awal|transfer\s*ke\s*rekening)\b",
    r"\b(?:biro\s*perjalanan|travel\s*agent|agen\s*perjalanan|tiket\s*pesawat|penggantian\s*biaya|reimburse\w*)\b",
    r"\b(?:gaji\s*fantastis|penghasilan\s*tak\s*terbatas|unlimited\s*income|tanpa\s*ijazah|tanpa\s*pengalaman)\b",
    r"\b(?:like\s*dan\s*subscribe|like\s*follow|paruh\s*waktu\s*online|tugas\s*harian|buka\s*tugas\s*vip)\b",
]

_SAFE_KEYWORDS = [
    r"\b(?:bpjs|thr|asuransi|pkwt|pkwtt|kontrak\s*kerja)\b",
    r"\b(?:portal\s*karir|karir\s*resmi|walk\s*in\s*interview|kualifikasi|syarat\s*pendidikan)\b",
    # "Gratis" saja tidak dihitung: poster palsu juga sering menulis "DAFTAR GRATIS!".
    r"\b(?:tidak\s*dipungut\s*biaya|tidak\s*ada\s*biaya\s*apapun)\b",
]


def extract_behavioral_features(text: str, companies: list[str] | None = None) -> dict[str, Any]:
    """Sinyal perilaku dari teks lowongan.

    `companies` adalah nama perusahaan hasil NER; bila ada, lowongan dianggap menyebut badan usaha
    walaupun teksnya tidak memakai awalan PT/CV (mis. "HOTEL NEW SAPHIR").
    """
    text_lower = (text or "").lower()

    has_fee = any(re.search(p, text_lower) for p in _FEE_PATTERNS)
    has_foreign = any(re.search(p, text_lower) for p in _FOREIGN_WORK_PATTERNS)
    # Dihitung hanya bila WhatsApp satu-satunya jalur melamar; loker yang juga mencantumkan
    # email atau tautan resmi tidak dianggap "lamar via WA".
    has_wa = any(re.search(p, text_lower) for p in _WHATSAPP_APPLY_PATTERNS) and not _OFFICIAL_CHANNEL.search(text_lower)

    fraud_hits = sum(1 for p in _FRAUD_KEYWORDS if re.search(p, text_lower, re.I))
    safe_hits = sum(1 for p in _SAFE_KEYWORDS if re.search(p, text_lower, re.I))

    has_company = bool(companies) or bool(_NAMED_ENTITY.search(text_lower))
    has_address = bool(re.search(r"\b(?:jl|jln|jalan|gedung|gd|komplek|kompleks|ruko|kawasan)\b", text_lower))
    claims_employer = bool(_EMPLOYER_CLAIM.search(text_lower))
    has_salary = bool(re.search(r"\b(gaji\w*|salary|upah|honor)\b|rp\.?\s*\d", text_lower))

    return {
        "has_fee_request": bool(has_fee),
        "has_foreign_work": bool(has_foreign),
        "has_whatsapp_apply": bool(has_wa),
        "fraud_keyword_count": float(fraud_hits),
        "safe_keyword_count": float(safe_hits),
        "has_company": bool(has_company),
        "has_address": bool(has_address),
        "has_salary": bool(has_salary),
        "fee_no_company": bool(has_fee and not has_company),
        "salary_no_company": bool(has_salary and not has_company),
        # Mengaku pabrik/perusahaan tetapi tidak menyebut nama badan usaha yang bisa diperiksa.
        "anonymous_employer_claim": bool(claims_employer and not has_company),
        # Menyebut BUMN/Persero/Tbk tetapi pendaftaran hanya lewat WhatsApp atau tautan di bio.
        "brand_unofficial_channel": bool(_BRAND_CLAIM.search(text_lower) and has_wa),
        "word_count": float(len(text.split())),
        "char_count": float(len(text)),
    }


def classify_text(text: str, companies: list[str] | None = None) -> dict[str, Any]:
    behavioral = extract_behavioral_features(text, companies)
    has_fee = behavioral.get("has_fee_request", False)
    has_foreign = behavioral.get("has_foreign_work", False)
    fraud_hits = behavioral.get("fraud_keyword_count", 0.0)
    safe_hits = behavioral.get("safe_keyword_count", 0.0)

    score = 15.0
    if has_fee:
        score += 45.0
    if has_foreign:
        score += 25.0
    score += min(30.0, fraud_hits * 10.0)
    score -= min(20.0, safe_hits * 5.0)
    score = max(0.0, min(100.0, score))

    if score >= 75.0 or has_fee:
        label = "BAHAYA"
    elif score >= 40.0 or has_foreign:
        label = "WASPADA"
    else:
        label = "AMAN"

    return {
        "enabled": True,
        "status": "RULE_BASED_HEURISTIC",
        "reason": "Taksonomi Pola Penipuan Kerja Indonesia (Paper22, GASA 2024, UNODC 2023)",
        "label": label,
        "nlp_score": score,
        "behavioral_features": behavioral,
    }
