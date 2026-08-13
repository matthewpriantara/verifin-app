"""
LLM-based Entity Validation — Guard AI untuk semua entitas hasil regex.

Melengkapi `entity_extraction.py` (yang hanya untuk semantic entities) dengan
validation pass untuk STRUCTURAL entities yang selama ini hanya regex:
- phones              : validasi apakah benar nomor kontak atau angka acak dari URL/ID
- emails              : validasi apakah benar email kontak atau placeholder/contoh
- urls                : validasi apakah benar URL lowongan/sosmed atau link tracking/iklan
- addresses           : validasi apakah benar alamat fisik atau frasa non-alamat
- location_candidates : validasi apakah benar lokasi kerja atau frasa admin/OCR corruption

Desain:
- Dipanggil SETELAH regex extraction, SEBELUM merge dengan LLM extraction
- Jika LLM down/timeout → fallback penuh ke hasil regex (safety net)
- Temperature=0 untuk deterministik
- Hanya filter, tidak menambah entitas baru (kecuali typo correction)
"""

import asyncio
import logging
import re
from typing import Any

from app.config import LLM_API_KEY, LLM_MODEL, LLM_TIMEOUT
from app.services.llm.client import chat_completion, extract_json_from_response

logger = logging.getLogger(__name__)

_VALIDATE_TIMEOUT = float(LLM_TIMEOUT) if LLM_TIMEOUT else 30.0

_SYSTEM_PROMPT = """Kamu adalah validator entitas untuk teks lowongan kerja berbahasa Indonesia.

Tugasmu HANYA memvalidasi apakah entitas yang diekstrak regex benar-benar valid atau false positive.

Aturan validasi:

1. PHONES (nomor telepon/HP):
   - VALID: nomor kontak yang bisa dihubungi (format +62xxx atau 08xxx)
   - INVALID: angka dari URL, ID grup Facebook, kode pos, tahun, atau angka acak lainnya
   - Perhatikan konteks: jika nomor muncul di URL/permalink, itu BUKAN kontak

2. EMAILS:
   - VALID: alamat email yang bisa dikirim pesan
   - INVALID: contoh email (xxx@xxx.com), email placeholder, atau domain bukan email

3. URLS:
   - VALID: link ke postingan lowongan, sosmed perusahaan, atau website resmi
   - INVALID: link tracking (bit.ly, goo.gl tanpa konteks), URL iklan, atau broken link

4. ADDRESSES (alamat fisik):
   - VALID: alamat lokasi kerja/kantor dengan penanda fisik (jalan, RT/RW, kelurahan, kecamatan, kota)
   - INVALID: frasa admin ("Kirim CV dan lamaran"), kalimat syarat, atau bukan alamat
   - Contoh VALID: "Manding, Bantul", "Jl. Malioboro No. 1, Yogyakarta"
   - Contoh INVALID: "Kirimc Vdanlamaran", "Bersedia training", "Pria/Wanita"

5. LOCATION_CANDIDATES (lokasi/area kerja):
   - VALID: nama daerah/kota/kecamatan tempat kerja (misal "Manding, Bantul", "Yogyakarta", "Jakarta Selatan")
   - INVALID: frasa admin, instruksi lamaran, atau hasil OCR corruption
   - Tolak: "Kirimc Vdanlamaran", "CV dan lamaran", "Bersedia training"

Jawab HANYA dengan JSON valid:
{
  "phones": {"valid": ["+62xxx"], "invalid": ["+62xxx"], "reasons": {"+62xxx": "alasan"}},
  "emails": {"valid": ["email@x.com"], "invalid": [], "reasons": {}},
  "urls": {"valid": ["https://..."], "invalid": [], "reasons": {}},
  "addresses": {"valid": ["alamat valid"], "invalid": ["alamat invalid"], "reasons": {}},
  "location_candidates": {"valid": ["lokasi valid"], "invalid": ["lokasi invalid"], "reasons": {}}
}

Jika ragu, tandai sebagai INVALID (precision over recall)."""

_USER_TEMPLATE = """Validasi entitas berikut dari teks lowongan:

TEKS SUMBER:
<<<{text}>>>

ENTITAS EKSTRAKSI REGEX:
- Phones: {phones}
- Emails: {emails}
- URLs: {urls}
- Addresses: {addresses}
- Location Candidates: {location_candidates}

Kembalikan HANYA JSON sesuai skema."""


def _clean_phone_list(phones: list[str]) -> list[str]:
    """Normalisasi list nomor telepon."""
    seen = set()
    out = []
    for p in phones:
        # Standardize: hapus spasi, dash, titik
        clean = re.sub(r"[\s\-\.]", "", str(p))
        if not clean or len(clean) < 9 or len(clean) > 16:
            continue
        # Pastikan format +62 atau 08
        if clean.startswith("0"):
            clean = "+62" + clean[1:]
        elif clean.startswith("62") and not clean.startswith("+"):
            clean = "+" + clean
        elif not clean.startswith("+62") and not clean.startswith("08"):
            continue
        if clean not in seen:
            seen.add(clean)
            out.append(clean)
    return out


def _clean_str_list(items: list[str], *, max_items: int = 10, max_len: int = 200) -> list[str]:
    """Normalisasi list string unik, bersih, terbatas."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        s = re.sub(r"\s+", " ", item).strip(" \t\n.,;:-")
        if not s or len(s) < 2 or len(s) > max_len:
            continue
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= max_items:
            break
    return out


async def validate_entities_llm(
    text: str,
    phones: list[str],
    emails: list[str],
    urls: list[str],
    addresses: list[str] | None = None,
    location_candidates: list[str] | None = None,
) -> dict[str, Any] | None:
    """
    Validasi entitas structural via LLM.

    Returns:
        dict dengan key "phones", "emails", "urls", "addresses", "location_candidates"
        yang sudah divalidasi, atau None jika LLM gagal/tidak tersedia (→ caller pakai regex).
    """
    if not LLM_API_KEY:
        logger.info("[llm_validator] LLM_API_KEY kosong → skip validation (fallback regex).")
        return None

    addresses = addresses or []
    location_candidates = location_candidates or []

    # Skip jika tidak ada yang divalidasi
    if not phones and not emails and not urls and not addresses and not location_candidates:
        logger.info("[llm_validator] Tidak ada entities untuk divalidasi.")
        return None

    snippet = (text or "").strip()[:3000]  # Batasi untuk hemat token
    logger.info(
        f"[llm_validator] Validating {len(phones)} phones, {len(emails)} emails, "
        f"{len(urls)} urls, {len(addresses)} addresses, {len(location_candidates)} location_candidates"
    )

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _USER_TEMPLATE.format(
            text=snippet,
            phones=phones,
            emails=emails,
            urls=urls,
            addresses=addresses,
            location_candidates=location_candidates,
        )},
    ]

    try:
        raw = await asyncio.wait_for(
            chat_completion(
                messages,
                model=LLM_MODEL,
                temperature=0.0,
                max_tokens=800,
                max_retries=1,
            ),
            timeout=_VALIDATE_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning("[llm_validator] LLM validation timeout → fallback regex.")
        return None
    except Exception as exc:
        logger.warning(f"[llm_validator] LLM validation gagal ({type(exc).__name__}: {exc}) → fallback regex.")
        return None

    try:
        data = extract_json_from_response(raw)
    except Exception as exc:
        logger.warning("[llm_validator] JSON LLM tidak valid (%s) → fallback regex.", exc)
        return None

    if not isinstance(data, dict):
        return None

    # Process phones
    validated_phones = []
    phone_data = data.get("phones", {})
    if isinstance(phone_data, dict):
        valid_list = phone_data.get("valid", [])
        validated_phones = _clean_phone_list(valid_list)
    elif isinstance(phone_data, list):
        validated_phones = _clean_phone_list(phone_data)

    # Process emails
    validated_emails = []
    email_data = data.get("emails", {})
    if isinstance(email_data, dict):
        valid_list = email_data.get("valid", [])
        validated_emails = [e.strip().lower() for e in valid_list if isinstance(e, str) and "@" in e]
    elif isinstance(email_data, list):
        validated_emails = [e.strip().lower() for e in email_data if isinstance(e, str) and "@" in e]

    # Process urls
    validated_urls = []
    url_data = data.get("urls", {})
    if isinstance(url_data, dict):
        valid_list = url_data.get("valid", [])
        validated_urls = [u.strip() for u in valid_list if isinstance(u, str) and u.startswith(("http", "www."))]
    elif isinstance(url_data, list):
        validated_urls = [u.strip() for u in url_data if isinstance(u, str) and u.startswith(("http", "www."))]

    # Process addresses
    validated_addresses = []
    addr_data = data.get("addresses", {})
    if isinstance(addr_data, dict):
        valid_list = addr_data.get("valid", [])
        validated_addresses = _clean_str_list(valid_list)
    elif isinstance(addr_data, list):
        validated_addresses = _clean_str_list(addr_data)

    # Process location_candidates
    validated_locations = []
    loc_data = data.get("location_candidates", {})
    if isinstance(loc_data, dict):
        valid_list = loc_data.get("valid", [])
        validated_locations = _clean_str_list(valid_list)
    elif isinstance(loc_data, list):
        validated_locations = _clean_str_list(loc_data)

    result = {
        "phones": validated_phones,
        "emails": validated_emails,
        "urls": validated_urls,
        "addresses": validated_addresses,
        "location_candidates": validated_locations,
        "_validation_meta": {
            "phones_removed": len(phones) - len(validated_phones),
            "emails_removed": len(emails) - len(validated_emails),
            "urls_removed": len(urls) - len(validated_urls),
            "addresses_removed": len(addresses) - len(validated_addresses),
            "location_candidates_removed": len(location_candidates) - len(validated_locations),
        }
    }

    logger.info(
        "[llm_validator] Validation done: phones %d→%d, emails %d→%d, urls %d→%d, "
        "addresses %d→%d, locations %d→%d",
        len(phones), len(validated_phones),
        len(emails), len(validated_emails),
        len(urls), len(validated_urls),
        len(addresses), len(validated_addresses),
        len(location_candidates), len(validated_locations),
    )

    return result
