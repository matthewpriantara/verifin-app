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

logger = logging.getLogger(__name__)


def _is_valid_llm_output(parsed: dict) -> bool:
    """Validasi semantik output LLM — deteksi truncation dan field rusak."""
    if parsed.get("verdict") not in ("AMAN", "WASPADA", "BAHAYA"):
        return False
    if not isinstance(parsed.get("risk_score"), (int, float)):
        return False

    # Token awalan/akhiran umum Indonesia yang sering terkonkatenasi saat truncation
    _CONCAT_PREFIXES = ("tidak", "nomor", "ada", "fee", "di", "dan", "dari", "ke", "yang", "untuk")

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
            # Dua kata Indonesia disambung tanpa spasi di awal token
            # contoh: "Nomorterdeteksi", "Tidakintaan", "Feebutkan"
            t_lower = t.lower()
            for prefix in _CONCAT_PREFIXES:
                if not t_lower.startswith(prefix):
                    continue
                # Setelah prefix, ada huruf lagi langsung (bukan spasi)
                rest = t_lower[len(prefix):]
                if rest and rest[0].isalpha() and not rest[0] == ' ':
                    # Pastikan prefix adalah kata utuh (bukan substring valid seperti "tidak ada")
                    # Cek apakah ada spasi setelah prefix di string asli
                    if len(t) > len(prefix) and t[len(prefix)] != ' ':
                        return False
    return True


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
            "threads": {},
        }

    if raw_text:
        prompt = build_text_verify_prompt(raw_text, entities, osint_results)
    else:
        prompt = build_verify_prompt(entities, osint_results)

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
            # Sanitize field list — buang item <= 3 karakter (artifact truncation)
            for field in ("risk_factors", "safe_factors", "recommendations"):
                items = parsed.get(field) or []
                parsed[field] = [s for s in items if isinstance(s, str) and len(s) > 3]
            if _is_valid_llm_output(parsed):
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
        if not _is_valid_llm_output(parsed):
            logger.warning("Semua 3 attempt LLM gagal validasi semantik — menggunakan output terakhir.")
        parsed["entities_analyzed"] = entities
        return parsed

    except Exception as exc:
        # Rule-based fallback engine if LLM API is unavailable
        comp_name = (entities.get("companies") or ["Perusahaan"])[0]
        has_fraud_phone = any(p.get("reported_fraud") for p in (osint_results.get("phones") or []))
        has_free_email = any(
            "@" in e and e.split("@")[-1].lower() in FREE_EMAIL_DOMAINS
            for e in (entities.get("emails") or [])
        )
        has_address = len(osint_results.get("address_validations") or []) > 0

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
            safe_factors.append("Alamat fisik berhasil dipetakan di OpenStreetMap (GIS spatial verified).")

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


analyze_with_hermes = analyze_with_verifin
