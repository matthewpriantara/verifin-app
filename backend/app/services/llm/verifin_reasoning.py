"""
Reasoning engine Verifin via OpenAgentic (default: grok-4.5).
"""

from __future__ import annotations

import httpx

from app.config import LLM_MODEL
from app.services.llm.client import chat_completion, check_llm_status, extract_json_from_response
from app.services.llm.prompt_builder import build_text_verify_prompt, build_verify_prompt


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

    try:
        raw = await chat_completion(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Kamu adalah analis forensik lowongan kerja Verifin. "
                        "Hanya gunakan fakta dari data OSINT/teks yang diberikan user. "
                        "Dilarang mengarang sumber, status AHU/OSS, atau temuan medsos. "
                        "Gunakan bahasa Indonesia formal dan profesional. "
                        "Jawab HANYA JSON valid sesuai skema yang diminta."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            model=LLM_MODEL,
            temperature=0.1,
            max_tokens=900,
        )
        parsed = extract_json_from_response(raw)
        parsed["model_used"] = LLM_MODEL
        parsed["entities_analyzed"] = entities
        return parsed

    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:300] if exc.response is not None else str(exc)
        return {
            "verdict": "ERROR",
            "risk_score": 0,
            "summary": f"Gagal memanggil LLM ({exc.response.status_code if exc.response else '?'}): {detail}",
            "risk_factors": [],
            "safe_factors": [],
            "recommendations": ["Cek LLM_API_KEY / kuota OpenAgentic, lalu coba lagi."],
            "model_used": LLM_MODEL,
            "entities_analyzed": entities,
        }
    except Exception as exc:
        return {
            "verdict": "ERROR",
            "risk_score": 0,
            "summary": f"Terjadi kesalahan saat analisis AI: {exc}",
            "risk_factors": [],
            "safe_factors": [],
            "recommendations": ["Lakukan pengecekan manual pada lowongan kerja ini."],
            "model_used": LLM_MODEL,
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
