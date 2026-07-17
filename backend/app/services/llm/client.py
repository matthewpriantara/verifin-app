"""Client OpenAI-compatible untuk OpenAgentic (Grok, Claude, dll)."""

from __future__ import annotations

import json
import re
from typing import Any, Optional

import httpx

from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT


def _parse_json_value(text: str) -> Any:
    """Parse JSON; tahan trailing text / NDJSON ganda."""
    cleaned = (text or "").strip()
    if not cleaned:
        raise json.JSONDecodeError("empty", cleaned, 0)

    # Ambil baris/object pertama yang valid
    try:
        obj, _ = json.JSONDecoder().raw_decode(cleaned)
        return obj
    except json.JSONDecodeError:
        pass

    # Coba tiap baris (NDJSON)
    for line in cleaned.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj, _ = json.JSONDecoder().raw_decode(line)
            return obj
        except json.JSONDecodeError:
            continue

    start = cleaned.find("{")
    while start != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(cleaned[start:])
            return obj
        except json.JSONDecodeError:
            start = cleaned.find("{", start + 1)

    raise json.JSONDecodeError("no json object", cleaned, 0)


def extract_json_from_response(text: str) -> dict:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned).strip()

    try:
        obj = _parse_json_value(cleaned)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    return {
        "verdict": "ERROR",
        "risk_score": 0,
        "summary": "AI tidak dapat menghasilkan analisis JSON yang valid.",
        "risk_factors": [],
        "safe_factors": [],
        "recommendations": ["Lakukan pengecekan manual pada lowongan kerja ini."],
    }


async def chat_completion(
    messages: list[dict[str, Any]],
    *,
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 2048,
    timeout: Optional[float] = None,
) -> str:
    if not LLM_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY belum diset. Isi backend/.env dengan key OpenAgentic."
        )

    url = f"{LLM_BASE_URL}/chat/completions"
    payload = {
        "model": model or LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=timeout or LLM_TIMEOUT) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        try:
            data = _parse_json_value(response.text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Respons LLM bukan JSON valid (awal): {response.text[:200]!r}"
            ) from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"Format respons LLM tidak dikenali: {type(data)}")

    try:
        content = data["choices"][0]["message"]["content"]
        return content if isinstance(content, str) else json.dumps(content)
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Format respons LLM tidak dikenali: {data}") from exc


async def check_llm_status() -> dict:
    if not LLM_API_KEY:
        return {
            "provider": "openagentic",
            "configured": False,
            "reachable": False,
            "model": LLM_MODEL,
            "detail": "LLM_API_KEY belum diset",
        }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(
                f"{LLM_BASE_URL}/models",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            )
            reachable = res.status_code < 500
            return {
                "provider": "openagentic",
                "configured": True,
                "reachable": reachable,
                "model": LLM_MODEL,
                "status_code": res.status_code,
            }
    except Exception as exc:
        return {
            "provider": "openagentic",
            "configured": True,
            "reachable": False,
            "model": LLM_MODEL,
            "detail": str(exc),
        }
