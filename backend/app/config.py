import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_VISION_MODEL = os.getenv("LLM_VISION_MODEL") or LLM_MODEL
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "120"))
LLM_VALIDATOR_MODEL = os.getenv("LLM_VALIDATOR_MODEL") or LLM_MODEL
LLM_EXTRACTOR_MODEL = os.getenv("LLM_EXTRACTOR_MODEL") or LLM_MODEL

DATABASE_URL = os.getenv("DATABASE_URL", "")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

LIGHTPANDA_CONTAINER = os.getenv("LIGHTPANDA_CONTAINER", "lightpanda")
LIGHTPANDA_CDP_URL = os.getenv("LIGHTPANDA_CDP_URL", "http://127.0.0.1:9222")

SEARXNG_URL = os.getenv("SEARXNG_URL", "").rstrip("/")

VERIFIN_DEBUG_RAW_JSON = os.getenv("VERIFIN_DEBUG_RAW_JSON", "false").lower() in {
    "1", "true", "yes", "on"
}
