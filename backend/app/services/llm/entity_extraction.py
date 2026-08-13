"""
Hybrid NER — LLM-based Entity Extraction (Layer 1 suplemen).

Melengkapi `app/services/ner.py` (regex) dengan extraction pass berbasis LLM
untuk entitas SEMANTIK yang sulit ditangkap pola deterministik:
- companies : nama perusahaan/PT (regex rapuh pada brand tanpa legal form,
  false positive pada frasa umum seperti "dan cekatan", "INDONESIA COLLEGE")
- addresses : alamat fisik (semantik — paham konteks, bukan sekadar pola jalan)
- salaries  : nominal gaji/upah dalam bentuk apapun (Rp, juta, per bulan, dsb.)

Desain HYBRID (sesuai keputusan arsitektur):
- Entitas STRUKTURAL (HP/email/URL) TETAP regex — pola stabil, cepat, murah.
- Entitas SEMANTIK (companies/addresses/salaries) via LLM — paham konteks.
- LLM extraction berjalan PARALEL dengan OSINT probe di router (tidak menambah
  critical path latency).
- Jika LLM down/timeout/JSON rusak → FALLBACK penuh ke hasil regex. Regex
  adalah safety net, bukan sumber utama untuk entitas semantik.

Kejujuran teknis: LLM di sini HANYA melakukan extraction (NER), terpisah dari
LLM reasoning (Layer 4, verdict). Ini memperkuat proposal — 2 peran LLM yang
jelas dan dapat diaudit. Output di-cache oleh router via raw_text_hash.
"""

import asyncio
import logging
import re
from typing import Any

from app.config import LLM_API_KEY, LLM_MODEL, LLM_TIMEOUT
from app.services.llm.client import chat_completion, extract_json_from_response

logger = logging.getLogger(__name__)

# Timeout khusus extraction — lebih pendek dari reasoning agar fallback cepat.
_EXTRACT_TIMEOUT = float(LLM_TIMEOUT) if LLM_TIMEOUT else 45.0

_SYSTEM_PROMPT = """Kamu adalah mesin Named Entity Recognition (NER) untuk teks lowongan kerja berbahasa Indonesia, termasuk hasil OCR poster yang berantakan.

Tugasmu HANYA mengekstrak entitas, BUKAN menilai penipuan. Jawab HANYA dengan satu objek JSON valid (tanpa markdown, tanpa penjelasan).

Skema JSON:
{
  "companies": ["nama perusahaan/PT/organisasi pemberi kerja, persis seperti tertulis"],
  "addresses": ["alamat fisik lengkap (jalan, gedung, kelurahan, kecamatan, kota, kode pos) persis seperti tertulis"],
  "location_candidates": ["lokasi/area/penempatan kerja yang disebut (kota, kecamatan, provinsi, atau alamat area) persis seperti tertulis"],
  "salaries": ["nominal gaji/upah persis seperti tertulis, contoh: Rp 3.500.000, 5-7 juta, UMR"]
}

Aturan ketat:
1. companies: HANYA entitas perusahaan/instansi/organisasi pemberi kerja nyata. JANGAN masukkan frasa deskriptif (mis. "dan cekatan", "bersedia training"), nama posisi, atau kata umum. Pertahankan legal form (PT/CV/UD) bila ada.
2. addresses: HANYA alamat fisik lokasi kerja/kantor yang memiliki penanda fisik seperti jalan, nomor, RT/RW, gedung, ruko, atau kode pos. Jangan masukkan kota, kecamatan, area kerja, daftar cabang, atau lokasi tanpa penanda fisik.
3. location_candidates: lokasi/area/penempatan kerja yang disebut di teks. Termasuk kota, kecamatan, provinsi, atau area kerja. Contoh: "Karawang", "Jakarta Selatan", "Bantul". Ekstrak dari label "Penempatan", "Lokasi", "Domisili", "Area", "Wilayah", atau konteks lain. PERSIS seperti tertulis di teks.
4. salaries: setiap nominal rentang gaji yang disebut. Simpan format aslinya.
5. Jika suatu kategori tidak ada, kembalikan array kosong [].
6. Jangan mengarang entitas yang tidak tertulis di teks. Ekstrak PERSIS substring dari teks sumber."""

_USER_TEMPLATE = """Ekstrak entitas dari teks lowongan berikut (mungkin hasil OCR, bisa mengandung salah ketik/spasi aneh):

<<<TEKS
{text}
TEKS

Kembalikan HANYA JSON sesuai skema."""


def _clean_str_list(value: Any, *, max_items: int = 10, max_len: int = 200) -> list[str]:
    """Normalisasi output LLM → list[str] unik, bersih, terbatas."""
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in value:
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


async def extract_entities_llm(text: str) -> dict[str, Any] | None:
    """
    Panggil LLM untuk mengekstrak companies/addresses/salaries.

    Returns:
        dict {"companies": [...], "addresses": [...], "salaries": [...]}
        atau None jika LLM tidak tersedia/gagal (→ caller pakai regex).
    """
    if not LLM_API_KEY:
        logger.info("[llm_ner] LLM_API_KEY kosong → skip LLM extraction (fallback regex).")
        return None

    snippet = (text or "").strip()
    if not snippet:
        return None
    # Batasi panjang agar hemat token & cepat (poster OCR bisa sangat panjang).
    snippet = snippet[:4000]

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _USER_TEMPLATE.format(text=snippet)},
    ]

    try:
        raw = await asyncio.wait_for(
            chat_completion(
                messages,
                model=LLM_MODEL,
                temperature=0.0,   # deterministik untuk extraction
                max_tokens=800,    # extraction tidak butuh panjang
                max_retries=2,     # extraction jangan retry lama — cepat fallback
            ),
            timeout=_EXTRACT_TIMEOUT,
        )
    except (asyncio.TimeoutError, Exception) as exc:  # noqa: BLE001 — fallback by design
        logger.warning("[llm_ner] LLM extraction gagal (%s) → fallback regex.", exc)
        return None

    try:
        data = extract_json_from_response(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[llm_ner] JSON LLM tidak valid (%s) → fallback regex.", exc)
        return None

    if not isinstance(data, dict):
        return None

    return {
        "companies": _clean_str_list(data.get("companies")),
        "addresses": _clean_str_list(data.get("addresses")),
        "location_candidates": _clean_str_list(data.get("location_candidates")),
        "salaries": _clean_str_list(data.get("salaries")),
    }

