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
]

_FRAUD_KEYWORDS = [
    r"\b(?:biaya\s*pendaftaran|biaya\s*administrasi|uang\s*jaminan|deposit\s*awal|transfer\s*ke\s*rekening)\b",
    r"\b(?:biro\s*perjalanan|travel\s*agent|tiket\s*pesawat|penggantian\s*biaya|reimburse\s*100%|reimbursement)\b",
    r"\b(?:gaji\s*fantastis|penghasilan\s*tak\s*terbatas|unlimited\s*income|tanpa\s*ijazah|tanpa\s*pengalaman)\b",
    r"\b(?:like\s*dan\s*subscribe|like\s*follow|paruh\s*waktu\s*online|tugas\s*harian|buka\s*tugas\s*vip)\b",
]

_SAFE_KEYWORDS = [
    r"\b(?:pt\b.*?\btbk\b|bumn\b|persero\b)",
    r"\b(?:bpjs|thr|asuransi|pkwt|pkwtt|kontrak\s*kerja)\b",
    r"\b(?:portal\s*karir|karir\s*resmi|walk\s*in\s*interview|kualifikasi|syarat\s*pendidikan)\b",
    r"\b(?:tidak\s*dipungut\s*biaya|gratis|tidak\s*ada\s*biaya\s*apapun)\b",
]


def extract_behavioral_features(text: str) -> dict[str, Any]:
    text_lower = (text or "").lower()

    has_fee = any(re.search(p, text_lower) for p in _FEE_PATTERNS)
    has_foreign = any(re.search(p, text_lower) for p in _FOREIGN_WORK_PATTERNS)
    has_wa = any(re.search(p, text_lower) for p in _WHATSAPP_APPLY_PATTERNS)

    fraud_hits = sum(1 for p in _FRAUD_KEYWORDS if re.search(p, text_lower, re.I))
    safe_hits = sum(1 for p in _SAFE_KEYWORDS if re.search(p, text_lower, re.I))

    has_company = bool(re.search(r"\b(pt|cv|ud|yayasan|persero|perum)\b", text_lower))
    has_address = bool(re.search(r"\b(jl\.|jalan|gedung|komplek|ruko)\b", text_lower))
    has_salary = bool(re.search(r"\b(gaji|salary|upah|honor)\b", text_lower))

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
        "word_count": float(len(text.split())),
        "char_count": float(len(text)),
    }


def classify_text(text: str) -> dict[str, Any]:
    behavioral = extract_behavioral_features(text)
    return {
        "enabled": True,
        "status": "RULE_BASED_HEURISTIC",
        "reason": "Taksonomi Pola Penipuan Kerja Indonesia (Paper22, GASA 2024, UNODC 2023)",
        "behavioral_features": behavioral,
    }
