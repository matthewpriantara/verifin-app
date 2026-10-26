import asyncio
import json
import re
import logging
from typing import Any

import httpx

from app.services.pii import PiiMasker

from app.config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_EXTRACTOR_MODEL,
    LLM_MODEL,
    LLM_TIMEOUT,
    LLM_FALLBACK_API_KEY,
    LLM_FALLBACK_BASE_URL,
    LLM_FALLBACK_EXTRACTOR_MODEL,
    LLM_FALLBACK_MODEL,
    LLM_FALLBACK_TIMEOUT,
)

logger = logging.getLogger(__name__)


def _parse_json_value(text: str) -> Any:
    cleaned = (text or "").strip()
    if not cleaned:
        raise json.JSONDecodeError("empty", cleaned, 0)
    try:
        obj, _ = json.JSONDecoder().raw_decode(cleaned)
        return obj
    except json.JSONDecodeError:
        pass
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


def _repair_truncated_json(text: str) -> str:
    t = text.strip()
    t = re.sub(r"```(?:json)?\s*", "", t).strip()
    safe_end = -1
    in_str = False
    escape = False
    after_colon = False
    depth = 0

    for i, ch in enumerate(t):
        if escape:
            escape = False
            continue
        if ch == '\\' and in_str:
            escape = True
            continue
        if ch == '"':
            if in_str:
                in_str = False
                if after_colon:
                    safe_end = i
                    after_colon = False
            else:
                in_str = True
        elif not in_str:
            if ch == ':':
                after_colon = True
            elif ch in ('{', '['):
                depth += 1
            elif ch in ('}', ']'):
                depth -= 1
                safe_end = i
                after_colon = False
            elif ch == ',' :
                after_colon = False

    if in_str and safe_end >= 0:
        t = t[:safe_end + 1]

    t = re.sub(r",\s*$", "", t.rstrip())
    t = re.sub(r":\s*$", ': ""', t)

    t += "]" * max(0, t.count("[") - t.count("]"))
    t += "}" * max(0, t.count("{") - t.count("}"))
    return t


def extract_json_from_response(text: str) -> dict:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", cleaned).strip()
    match_code = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", cleaned)
    if match_code:
        try:
            obj = _parse_json_value(match_code.group(1))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    if cleaned.startswith("```"):
        cleaned_fence = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned_fence = re.sub(r"\s*```$", "", cleaned_fence).strip()
    else:
        cleaned_fence = cleaned

    try:
        obj = _parse_json_value(cleaned_fence)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass
    match_braces = re.search(r"(\{[\s\S]*\})", cleaned)
    if match_braces:
        try:
            obj = _parse_json_value(match_braces.group(1))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    for candidate in [cleaned_fence, cleaned]:
        try:
            repaired = _repair_truncated_json(candidate)
            obj = _parse_json_value(repaired)
            if isinstance(obj, dict) and "verdict" in obj:
                return obj
        except Exception:
            pass

    logger.error("Gagal parse JSON dari LLM raw text:\n%s", text[:500])

    return {
        "verdict": "ERROR",
        "risk_score": 0,
        "summary": "AI tidak dapat menghasilkan analisis JSON yang valid.",
        "risk_factors": [],
        "safe_factors": [],
        "recommendations": ["Lakukan pengecekan manual pada lowongan kerja ini."],
    }


async def _execute_chat_completion(
    base_url: str,
    api_key: str,
    model_name: str,
    timeout_sec: float,
    messages: list[dict[str, Any]],
    masker: PiiMasker,
    temperature: float,
    max_tokens: int,
    seed: int | None,
    max_retries: int,
) -> str:
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model_name,
        "messages": masker.mask_messages(messages),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    if seed is not None:
        payload["seed"] = seed
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
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
                msg = data["choices"][0].get("message") or {}
                content = msg.get("content")
                if not isinstance(content, str) or not content.strip():
                    rc = msg.get("reasoning_content") or msg.get("reasoning") or data["choices"][0].get("reasoning_content") or ""
                    if isinstance(rc, str) and rc.strip():
                        if "{" in rc and "}" in rc:
                            content = rc
                        else:
                            logger.warning("LLM returned empty content but reasoning_content present (%d chars) — using reasoning fallback", len(rc))
                            content = rc
                finish_reason = data["choices"][0].get("finish_reason", "")
                if finish_reason == "length":
                    logger.warning("LLM response terpotong (finish_reason=length) — repair akan dicoba")
                if content is None:
                    content = ""
                return masker.unmask(content if isinstance(content, str) else json.dumps(content))
            except (KeyError, IndexError, TypeError) as exc:
                raise RuntimeError(f"Format respons LLM tidak dikenali: {data}") from exc

        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as exc:
            last_exc = exc
            status = getattr(exc.response, "status_code", None) if isinstance(exc, httpx.HTTPStatusError) else None
            retryable = status is None or status >= 500 or status == 429
            if not retryable or attempt >= max_retries:
                raise
            wait = 2 ** attempt
            logger.warning("attempt %d gagal (%s), retry dalam %ds...", attempt, status or exc, wait)
            await asyncio.sleep(wait)

    raise RuntimeError(f"LLM gagal setelah {max_retries} percobaan: {last_exc}")


async def chat_completion(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    timeout: float | None = None,
    max_retries: int = 3,
    seed: int | None = 42,
) -> str:
    if not LLM_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY belum diset. Isi backend/.env dengan key LLM."
        )

    masker = PiiMasker()
    target_model = model or LLM_MODEL
    try:
        return await _execute_chat_completion(
            base_url=LLM_BASE_URL,
            api_key=LLM_API_KEY,
            model_name=target_model,
            timeout_sec=timeout or LLM_TIMEOUT,
            messages=messages,
            masker=masker,
            temperature=temperature,
            max_tokens=max_tokens,
            seed=seed,
            max_retries=max_retries,
        )
    except Exception as exc:
        if LLM_FALLBACK_BASE_URL and LLM_FALLBACK_API_KEY:
            fallback_model = (
                LLM_FALLBACK_EXTRACTOR_MODEL
                if (model and model == LLM_EXTRACTOR_MODEL)
                else (LLM_FALLBACK_MODEL or target_model)
            )
            logger.warning(
                "⚠️ Primary LLM (%s / %s) gagal: %s. Mengalihkan otomatis ke Fallback LLM (%s / %s)...",
                LLM_BASE_URL,
                target_model,
                exc,
                LLM_FALLBACK_BASE_URL,
                fallback_model,
            )
            return await _execute_chat_completion(
                base_url=LLM_FALLBACK_BASE_URL,
                api_key=LLM_FALLBACK_API_KEY,
                model_name=fallback_model,
                timeout_sec=timeout or LLM_FALLBACK_TIMEOUT,
                messages=messages,
                masker=masker,
                temperature=temperature,
                max_tokens=max_tokens,
                seed=seed,
                max_retries=2,
            )
        raise


async def check_llm_status() -> dict:
    if not LLM_API_KEY:
        return {
            "provider": "not-configured",
            "configured": False,
            "reachable": False,
            "model": LLM_MODEL,
            "detail": "LLM_API_KEY belum diset",
        }

    status: dict[str, Any] = {
        "provider": "ollama" if "11434" in LLM_BASE_URL else "cloud",
        "configured": True,
        "model": LLM_MODEL,
        "base_url": LLM_BASE_URL,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                f"{LLM_BASE_URL}/models",
                headers={"Authorization": f"Bearer {LLM_API_KEY}"},
            )
            status["reachable"] = res.status_code < 500
            status["status_code"] = res.status_code
    except Exception as exc:
        status["reachable"] = False
        status["detail"] = str(exc)

    if LLM_FALLBACK_BASE_URL and LLM_FALLBACK_API_KEY:
        status["fallback"] = {
            "configured": True,
            "base_url": LLM_FALLBACK_BASE_URL,
            "model": LLM_FALLBACK_MODEL,
        }

    return status
