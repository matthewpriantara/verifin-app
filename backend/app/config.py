"""Konfigurasi aplikasi Verifin — LLM via OpenAgentic."""

import os
from pathlib import Path

# Load .env sederhana (tanpa python-dotenv wajib)
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


# OpenAgentic (OpenAI-compatible)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://openagentic.id/api/v1").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "grok-4.5")
LLM_VISION_MODEL = os.getenv("LLM_VISION_MODEL", LLM_MODEL)
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))
