"""Konfigurasi aplikasi Verifin — semua nilai wajib dari .env."""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

# OpenAgentic (OpenAI-compatible)
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_VISION_MODEL = os.getenv("LLM_VISION_MODEL") or LLM_MODEL
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))

# PostgreSQL — wajib set DATABASE_URL di .env
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Redis (opsional)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Lightpanda headless browser — primary web fetcher & search renderer
# Container docker: docker run -d --name lightpanda -p 127.0.0.1:9222:9222 lightpanda/browser:nightly
LIGHTPANDA_CONTAINER = os.getenv("LIGHTPANDA_CONTAINER", "lightpanda")
LIGHTPANDA_CDP_URL = os.getenv("LIGHTPANDA_CDP_URL", "http://127.0.0.1:9222")

# SearXNG self-hosted — fallback search engine (opsional)
SEARXNG_URL = os.getenv("SEARXNG_URL", "").rstrip("/")

# Debug lokal: cetak payload pipeline lengkap sebagai JSON (mengandung PII/evidence).
VERIFIN_DEBUG_RAW_JSON = os.getenv("VERIFIN_DEBUG_RAW_JSON", "false").lower() in {
    "1", "true", "yes", "on"
}
