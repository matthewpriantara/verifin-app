import asyncio
import logging
import re
from typing import Any

from app.config import LLM_API_KEY, LLM_EXTRACTOR_MODEL, LLM_TIMEOUT
from app.services.llm.client import chat_completion, extract_json_from_response

logger = logging.getLogger(__name__)

_EXTRACT_TIMEOUT = max(float(LLM_TIMEOUT or 60.0), 60.0)

_SYSTEM_PROMPT = """Kamu adalah mesin Named Entity Recognition (NER) untuk teks lowongan kerja berbahasa Indonesia, termasuk hasil OCR poster yang berantakan.

Tugasmu HANYA mengekstrak entitas, BUKAN menilai penipuan. Jawab HANYA dengan satu objek JSON valid (tanpa markdown, tanpa penjelasan).

Skema JSON:
{
  "companies": ["nama perusahaan/PT/organisasi pemberi kerja, persis seperti tertulis"],
  "addresses": ["alamat fisik lengkap (jalan, gedung, kelurahan, kecamatan, kota, kode pos) persis seperti tertulis"],
  "location_candidates": ["lokasi/area/penempatan kerja yang disebut (kota, kecamatan, provinsi, atau alamat area) persis seperti tertulis"],
  "salaries": ["nominal gaji/upah persis seperti tertulis, contoh: Rp 3.500.000, 5-7 juta, UMR"],
  "is_job_posting": true,
  "postings": [{"employer": "nama pemberi kerja", "position": "posisi utama", "first_words": "5-8 kata pertama bagian lowongan ini, persis"}],
  "non_job_content": "jenis teks lain di luar lowongan (berita, promo akun, info grup), atau string kosong"
}

Aturan ketat:
1. companies: HANYA entitas perusahaan/instansi/organisasi pemberi kerja nyata. JANGAN masukkan frasa deskriptif (mis. "dan cekatan", "bersedia training"), nama posisi, atau kata umum. Pertahankan legal form (PT/CV/UD) bila ada.
2. addresses: HANYA alamat fisik lokasi kerja/kantor yang memiliki penanda fisik seperti jalan, nomor, RT/RW, gedung, ruko, atau kode pos. Jangan masukkan kota, kecamatan, area kerja, daftar cabang, atau lokasi tanpa penanda fisik.
3. location_candidates: lokasi/area/penempatan kerja yang disebut di teks. Termasuk kota, kecamatan, provinsi, atau area kerja. Contoh: "Karawang", "Jakarta Selatan", "Bantul". Ekstrak dari label "Penempatan", "Lokasi", "Domisili", "Area", "Wilayah", atau konteks lain. PERSIS seperti tertulis di teks.
4. salaries: setiap nominal rentang gaji yang disebut. Simpan format aslinya.
5. Jika suatu kategori tidak ada, kembalikan array kosong [].
6. Jangan mengarang entitas yang tidak tertulis di teks. Ekstrak PERSIS substring dari teks sumber.
7. is_job_posting: false bila teks bukan penawaran kerja (berita, invoice, promosi produk, meme, logo, percakapan). Lowongan yang mencurigakan tetap true.
8. postings: SATU entri per pemberi kerja berbeda. Satu pemberi kerja dengan banyak posisi = satu entri. Nama brand dan nama PT induknya (mis. "Morgans Kebab" dan "PT Trinity Success Group") = satu entri. Kosong bila bukan lowongan."""

_USER_TEMPLATE = """Ekstrak entitas dari teks lowongan berikut (mungkin hasil OCR, bisa mengandung salah ketik/spasi aneh):

<<<TEKS
{text}
TEKS

Kembalikan HANYA JSON sesuai skema."""


def _clean_str_list(value: Any, *, max_items: int = 10, max_len: int = 200) -> list[str]:
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
    if not LLM_API_KEY:
        logger.info("[llm_ner] LLM_API_KEY kosong → skip LLM extraction (fallback regex).")
        return None

    snippet = (text or "").strip()
    if not snippet:
        return None
    # Sama dengan batas input teks (10.000 karakter) supaya entitas di akhir lowongan tidak hilang.
    snippet = snippet[:10000]

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _USER_TEMPLATE.format(text=snippet)},
    ]

    try:
        raw = await asyncio.wait_for(
            chat_completion(
                messages,
                model=LLM_EXTRACTOR_MODEL,
                temperature=0.0,
                max_tokens=900,
                timeout=_EXTRACT_TIMEOUT,
                max_retries=1,
            ),
            timeout=_EXTRACT_TIMEOUT,
        )
    except (asyncio.TimeoutError, Exception) as exc:
        logger.warning("[llm_ner] LLM extraction gagal (%s) → fallback regex.", exc)
        return None

    if not raw or not raw.strip():
        logger.warning("[llm_ner] LLM returned empty content → fallback regex.")
        return None

    try:
        data = extract_json_from_response(raw)
    except Exception as exc:
        logger.warning("[llm_ner] JSON LLM tidak valid (%s) → fallback regex.", exc)
        return None

    if not isinstance(data, dict):
        return None

    if data.get("verdict") == "ERROR":
        logger.warning("[llm_ner] extract_json returned ERROR verdict → fallback regex.")
        return None

    return {
        "companies": _clean_str_list(data.get("companies")),
        "addresses": _clean_str_list(data.get("addresses")),
        "location_candidates": _clean_str_list(data.get("location_candidates")),
        "salaries": _clean_str_list(data.get("salaries")),
        "content": _clean_content(data),
    }


def _clean_content(data: dict) -> dict[str, Any]:
    """Klasifikasi isi untuk tahap "Memeriksa isi": lowongan atau bukan, dan berapa pemberi kerja."""
    postings = []
    for item in data.get("postings") or []:
        if not isinstance(item, dict):
            continue
        employer = re.sub(r"\s+", " ", str(item.get("employer") or "")).strip()
        if not employer:
            continue
        postings.append({
            "employer": employer[:120],
            "position": re.sub(r"\s+", " ", str(item.get("position") or "")).strip()[:120],
            "first_words": re.sub(r"\s+", " ", str(item.get("first_words") or "")).strip()[:160],
        })
    is_job = data.get("is_job_posting")
    return {
        "is_job_posting": is_job if isinstance(is_job, bool) else None,
        "postings": postings[:8],
        "non_job_content": str(data.get("non_job_content") or "").strip()[:120],
    }

