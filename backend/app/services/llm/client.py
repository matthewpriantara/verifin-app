"""Client OpenAI-compatible untuk OpenAgentic (Grok, Claude, dll)."""

import asyncio
import json
import re
import logging
from typing import Any

import httpx

from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TIMEOUT

logger = logging.getLogger(__name__)


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


def _repair_truncated_json(text: str) -> str:
    t = text.strip()
    # Hapus trailing code fence jika ada
    t = re.sub(r"```(?:json)?\s*$", "", t).strip()

    # Hapus koma atau titik dua gantung di paling akhir
    t = re.sub(r",\s*$", "", t)
    t = re.sub(r":\s*$", ': ""', t)

    # Potong di akhir array/object valid sebelum tutup string
    for i in range(len(t) - 1, -1, -1):
        if t[i] in ('}', ']'):
            t = t[:i + 1]
            break
        if t[i] == ',':
            t = t[:i]
            break

    # Tutup string terbuka
    quotes = len(re.findall(r'(?<!\\)"', t))
    if quotes % 2 != 0:
        t += '"'
    t = re.sub(r",\s*$", "", t)

    # Seimbangkan kurung siku dan kurawal
    open_brackets = t.count("[") - t.count("]")
    open_braces = t.count("{") - t.count("}")
    t += "]" * max(0, open_brackets)
    t += "}" * max(0, open_braces)
    return t


def extract_json_from_response(text: str) -> dict:
    cleaned = (text or "").strip()
    # 1. Hapus tag <think>...</think> jika ada (reasoning model / DeepSeek / Grok thinking)
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", cleaned).strip()

    # 2. Ekstrak dari blok kode markdown ```json ... ``` lengkap
    match_code = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", cleaned)
    if match_code:
        try:
            obj = _parse_json_value(match_code.group(1))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    # 3. Bersihkan pembuka ```json jika ada
    if cleaned.startswith("```"):
        cleaned_fence = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned_fence = re.sub(r"\s*```$", "", cleaned_fence).strip()
    else:
        cleaned_fence = cleaned

    # 4. Coba parsing langsung dari cleaned_fence
    try:
        obj = _parse_json_value(cleaned_fence)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # 5. Cari objek JSON terluar {...} lengkap di mana saja
    match_braces = re.search(r"(\{[\s\S]*\})", cleaned)
    if match_braces:
        try:
            obj = _parse_json_value(match_braces.group(1))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    # 6. Coba perbaiki jika JSON terpotong di akhir (truncation repair)
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


async def chat_completion(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    timeout: float | None = None,
    max_retries: int = 4,
    seed: int | None = 42,
) -> str:
    if not LLM_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY belum diset. Isi backend/.env dengan key OpenAgentic."
        )

    url = f"{LLM_BASE_URL}/chat/completions"
    payload = {
        "model": model or LLM_MODEL,
        "messages": messages,
        # temperature=0 + seed tetap → output deterministik (penting untuk audit/forensik).
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    # Beberapa penyedia (OpenAI-compatible) mendukung seed untuk reprodusibilitas.
    # Dikirim hanya bila di-set agar tidak merusak provider yang menolak field asing.
    if seed is not None:
        payload["seed"] = seed
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
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

        except (httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException) as exc:
            last_exc = exc
            status = getattr(exc.response, "status_code", None) if isinstance(exc, httpx.HTTPStatusError) else None
            # Retry hanya untuk 5xx / rate limit / network error
            retryable = status is None or status >= 500 or status == 429
            if not retryable or attempt >= max_retries:
                raise
            wait = 2 ** attempt  # 2, 4, 8 detik
            logger.warning("attempt %d gagal (%s), retry dalam %ds...", attempt, status or exc, wait)
            await asyncio.sleep(wait)

    raise RuntimeError(f"LLM gagal setelah {max_retries} percobaan: {last_exc}")


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
