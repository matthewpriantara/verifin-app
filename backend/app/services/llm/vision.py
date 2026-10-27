"""Pembacaan poster lowongan oleh model vision, sebagai pendamping OCR.

OCR salah membaca huruf bergaya (logo "ROEMAH BOENGA" terbaca "SBOENGA"); model vision membaca
konteks gambar dengan lebih baik tetapi bisa mengarang. Hasilnya hanya dipakai untuk menyusun
nama dan alamat; kontak tetap harus terbukti di teks OCR (lihat `_keep_proven_contacts`).
"""
import base64
import logging
import mimetypes

from app.config import (
    LLM_VISION_API_KEY,
    LLM_VISION_BASE_URL,
    LLM_VISION_MODEL,
    LLM_VISION_REASONING_EFFORT,
)
from app.services.llm.client import _execute_chat_completion
from app.services.pii import PiiMasker

logger = logging.getLogger(__name__)

_PROMPT = (
    "Salin semua teks yang terlihat pada gambar ini apa adanya, baris per baris, termasuk teks "
    "di logo, pita, dan tanda air. Jangan menambah penjelasan, jangan menerjemahkan, jangan "
    "memperbaiki ejaan. Bila tidak ada teks, jawab kosong."
)


async def read_image_with_vision(image_path: str, timeout: float = 30.0) -> str:
    if not (LLM_VISION_MODEL and LLM_VISION_BASE_URL and LLM_VISION_API_KEY):
        return ""
    try:
        with open(image_path, "rb") as fh:
            data = base64.b64encode(fh.read()).decode()
        mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": _PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}},
            ],
        }]
        text = await _execute_chat_completion(
            base_url=LLM_VISION_BASE_URL,
            api_key=LLM_VISION_API_KEY,
            model_name=LLM_VISION_MODEL,
            timeout_sec=timeout,
            messages=messages,
            masker=PiiMasker(),
            temperature=0.0,
            max_tokens=1500,
            seed=42,
            max_retries=1,
            reasoning_effort=LLM_VISION_REASONING_EFFORT or None,
        )
        return (text or "").strip()
    except Exception as exc:
        logger.warning("[vision] pembacaan gambar gagal (%s); lanjut dengan OCR saja", exc)
        return ""
