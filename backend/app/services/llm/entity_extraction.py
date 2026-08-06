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

from __future__ import annotations

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
  "addresses": ["HANYA bagian string alamat fisik — lihat aturan ketat di bawah"],
  "salaries": ["nominal gaji/upah persis seperti tertulis, contoh: Rp 3.500.000, 5-7 juta, UMR"]
}

Aturan ketat:
1. companies: HANYA entitas perusahaan/instansi/organisasi pemberi kerja nyata. JANGAN masukkan frasa deskriptif (mis. "dan cekatan", "bersedia training"), nama posisi, atau kata umum. Pertahankan legal form (PT/CV/UD) bila ada.
2. addresses: Ekstrak HANYA bagian alamat yang terdiri dari: nama jalan (Jl./Jalan), nomor, RT/RW, kelurahan, kecamatan, kabupaten/kota, dan/atau provinsi/kode pos.
   BATAS KERAS: String alamat WAJIB berhenti tepat di nama kota, provinsi, atau kode pos terakhir.
   JANGAN ikutkan teks sesudahnya meskipun dipisah koma — apapun yang datang setelah kota/provinsi/kode pos yang bukan bagian alamat (persyaratan, kata kerja, kata benda umum, instruksi pengiriman CV, nama posisi, dll.) HARUS dipotong.
   Contoh BENAR: "Jl. Rawa Terate 3 Kav.1 No.1, Kawasan Industri Pulogadung, Jatinegara, Cakung, Jakarta Timur"
   Contoh SALAH (jangan ikutkan ini): "...Jakarta Timur, KIRIMKAN, dari industri bakery/pengolahan daging, Paham analisa sensori, GMP, HACCP"
   Jika tidak yakin di mana batas kota/provinsi, potong di nama wilayah administratif terakhir yang dikenali.
3. salaries: setiap nominal rentang gaji yang disebut. Simpan format aslinya.
4. Jika suatu kategori tidak ada, kembalikan array kosong [].
5. Jangan mengarang entitas yang tidak tertulis di teks. Ekstrak PERSIS substring dari teks sumber (sampai batas kota/provinsi untuk addresses)."""

_USER_TEMPLATE = """Ekstrak entitas dari teks lowongan berikut (mungkin hasil OCR, bisa mengandung salah ketik/spasi aneh):

<<<TEKS
{text}
TEKS

Kembalikan HANYA JSON sesuai skema."""


def _clean_str_list(value: Any, *, max_items: int = 10, max_len: int = 300) -> list[str]:
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


# Token yang WAJIB ada minimal salah satu agar string dianggap alamat
_ADDR_STRUCTURAL_TOKENS = re.compile(
    r"\b(?:"
    r"Jl\.?|Jalan|Jln\.?|Gang|Gg\.?|Ruko|Komplek|Blok"
    r"|No\.?\s*\d|RT\s*\d|RW\s*\d"
    r"|Kec(?:amatan)?\.?|Kel(?:urahan)?\.?|Kab(?:upaten)?\.?"
    r"|Kota\s+[A-Z]|Kota\s+[a-z]"
    r"|Jakarta|Surabaya|Bandung|Medan|Semarang|Yogyakarta|Makassar"
    r"|Bekasi|Depok|Tangerang|Bogor|Malang|Palembang"
    r"|Indonesia|DKI|DIY|Jawa|Bali|Sumatra|Kalimantan"
    r")",
    flags=re.IGNORECASE,
)


def _is_valid_address_string(s: str) -> bool:
    """Cek apakah string terlihat seperti alamat fisik (bukan persyaratan kerja/OCR garbage)."""
    if len(s) < 8:
        return False
    # Harus mengandung minimal 1 token khas alamat
    return bool(_ADDR_STRUCTURAL_TOKENS.search(s))



def _merge(regex_list: list[str], llm_list: list[str]) -> tuple[list[str], bool]:
    """
    Gabungkan hasil LLM (prioritas) dengan regex (fallback/suplemen).
    Dedup case-insensitive. Return (merged, llm_added_something).
    """
    merged: list[str] = []
    seen: set[str] = set()

    def _push(items: list[str]) -> bool:
        added = False
        for it in items:
            key = it.lower()
            if key not in seen:
                seen.add(key)
                merged.append(it)
                added = True
        return added

    _push(regex_list)
    llm_added = _push(llm_list)
    return merged, llm_added


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
        "addresses": [
            a for a in _clean_str_list(data.get("addresses"), max_len=300)
            if _is_valid_address_string(a)
        ],
        "salaries": _clean_str_list(data.get("salaries")),
    }


async def hybrid_merge_entities(
    text: str,
    regex_entities: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Gabungkan hasil regex dengan LLM extraction untuk entitas semantik.

    Args:
        text: teks sumber (raw).
        regex_entities: output extract_entities_from_text (regex).

    Returns:
        (merged_entities, llm_meta)
        merged_entities: salinan regex_entities dengan companies/addresses/
                         salaries di-merge hasil LLM (jika ada).
        llm_meta: {"used": bool, "added": {kategori: bool}, "source": str}
    """
    meta: dict[str, Any] = {
        "used": False,
        "added": {"companies": False, "addresses": False, "salaries": False},
        "source": "regex",
    }

    llm_result = await extract_entities_llm(text)
    if not llm_result:
        return regex_entities, meta

    merged = dict(regex_entities)
    any_added = False
    for key in ("companies", "addresses", "salaries"):
        regex_vals = list(regex_entities.get(key) or [])
        llm_vals = llm_result.get(key) or []
        combined, llm_added = _merge(regex_vals, llm_vals)
        merged[key] = combined
        meta["added"][key] = llm_added
        any_added = any_added or llm_added

    meta["used"] = True
    meta["source"] = "hybrid_llm_regex" if any_added else "llm_no_new"
    return merged, meta
