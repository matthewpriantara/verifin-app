import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))
LLM_VALIDATOR_MODEL = os.getenv("LLM_VALIDATOR_MODEL") or LLM_MODEL
LLM_EXTRACTOR_MODEL = os.getenv("LLM_EXTRACTOR_MODEL") or LLM_MODEL

DATABASE_URL = os.getenv("DATABASE_URL", "")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

LIGHTPANDA_CONTAINER = os.getenv("LIGHTPANDA_CONTAINER", "lightpanda")
SEARXNG_URL = os.getenv("SEARXNG_URL", "").rstrip("/")

NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
OSINT_TIMEOUT_SEC = float(os.getenv("OSINT_TIMEOUT_SEC", "15.0"))
OSINT_USER_AGENT = os.getenv("OSINT_USER_AGENT", "Verifin-OSINT-App/1.0 (gemastik; contact@verifin.app)")

SEARXNG_TIMEOUT = int(os.getenv("SEARXNG_TIMEOUT", "15"))
SEARXNG_CACHE_TTL = int(os.getenv("SEARXNG_CACHE_TTL", "600"))
SEARXNG_MIN_INTERVAL = float(os.getenv("SEARXNG_MIN_INTERVAL", "0.8"))

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads" / "evidence"))
MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(5 * 1024 * 1024)))

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

VERIFIN_DEBUG_RAW_JSON = os.getenv("VERIFIN_DEBUG_RAW_JSON", "false").lower() in {
    "1", "true", "yes", "on"
}
