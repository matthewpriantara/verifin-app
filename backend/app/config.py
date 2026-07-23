"""Konfigurasi aplikasi Verifin — LLM via OpenAgentic & Database."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory setup (backend folder)
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if present
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

# OpenAgentic (OpenAI-compatible) — Untuk Pipeline Main
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://openagentic.id/api/v1").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "kimi-k3-high")
LLM_VISION_MODEL = os.getenv("LLM_VISION_MODEL", LLM_MODEL)
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))

# PostgreSQL Configuration
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "verifin_db")

# Fallback to direct url if specified, otherwise build it
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Redis (opsional — cache/queue nanti; core verify tidak wajib)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


class Settings:
    PROJECT_NAME: str = "Verifin API"
    VERSION: str = "0.1.0"

    DB_USER = DB_USER
    DB_PASSWORD = DB_PASSWORD
    DB_HOST = DB_HOST
    DB_PORT = DB_PORT
    DB_NAME = DB_NAME
    DATABASE_URL = DATABASE_URL
    REDIS_URL = REDIS_URL


settings = Settings()
