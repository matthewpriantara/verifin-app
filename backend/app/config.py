import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

APP_VERSION = os.getenv("APP_VERSION", "1.0.0")
GIT_COMMIT = os.getenv("GIT_COMMIT", "dev")
BUILD_TIME = os.getenv("BUILD_TIME", "")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "35"))
LLM_EXTRACTOR_MODEL = os.getenv("LLM_EXTRACTOR_MODEL") or LLM_MODEL
# Gemma 4 di Ollama berpikir dulu secara default; "none" mematikannya agar JSON masuk ke `content`.
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "").strip()
# Matikan (false) saat uji ulang agar setiap kasus dihitung ulang, bukan dibaca dari job_cases.
VERIFY_CACHE_ENABLED = os.getenv("VERIFY_CACHE_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")
# Pembacaan poster oleh model vision, berjalan bersamaan dengan OCR. Kosongkan model untuk mematikan.
# gemma4:12b-it-qat di Ollama tidak menerima gambar, jadi saat penalaran pindah ke Gemma, isi
# LLM_VISION_BASE_URL/API_KEY dengan penyedia Gemini agar vision tidak ikut pindah.
LLM_VISION_MODEL = os.getenv("LLM_VISION_MODEL", LLM_EXTRACTOR_MODEL).strip()
LLM_VISION_BASE_URL = (os.getenv("LLM_VISION_BASE_URL") or LLM_BASE_URL).rstrip("/")
LLM_VISION_API_KEY = os.getenv("LLM_VISION_API_KEY") or LLM_API_KEY
LLM_VISION_REASONING_EFFORT = (
    os.getenv("LLM_VISION_REASONING_EFFORT", "" if os.getenv("LLM_VISION_BASE_URL") else LLM_REASONING_EFFORT).strip()
)

# Fallback LLM Provider (Cadangan jika Primary gagal/down/timeout)
LLM_FALLBACK_BASE_URL = os.getenv("LLM_FALLBACK_BASE_URL", "").rstrip("/")
LLM_FALLBACK_API_KEY = os.getenv("LLM_FALLBACK_API_KEY", "")
LLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "")
LLM_FALLBACK_TIMEOUT = float(os.getenv("LLM_FALLBACK_TIMEOUT", str(LLM_TIMEOUT)))
LLM_FALLBACK_EXTRACTOR_MODEL = os.getenv("LLM_FALLBACK_EXTRACTOR_MODEL") or LLM_FALLBACK_MODEL
# Sama seperti LLM_REASONING_EFFORT, untuk penyedia cadangan (mis. Gemma di Ollama saat Gemini utama).
LLM_FALLBACK_REASONING_EFFORT = os.getenv("LLM_FALLBACK_REASONING_EFFORT", "").strip()

DATABASE_URL = os.getenv("DATABASE_URL", "")

SEARXNG_URL = os.getenv("SEARXNG_URL", "").rstrip("/")

NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
# Layanan getcontact-api di home (Tailscale). Kosong = fitur mati dan OSINT telepon tetap jalan
# dengan Kaspersky saja. Lihat infra/getcontact-api/README.md.
GETCONTACT_URL = os.getenv("GETCONTACT_URL", "").rstrip("/")
GETCONTACT_TOKEN = os.getenv("GETCONTACT_TOKEN", "")
GETCONTACT_TIMEOUT = float(os.getenv("GETCONTACT_TIMEOUT", "8"))
OSINT_TIMEOUT_SEC = float(os.getenv("OSINT_TIMEOUT_SEC", "15.0"))
OSINT_USER_AGENT = os.getenv("OSINT_USER_AGENT", "Verifin-OSINT-App/1.0 (gemastik; contact@verifin.app)")

SEARXNG_TIMEOUT = int(os.getenv("SEARXNG_TIMEOUT", "15"))
SEARXNG_CACHE_TTL = int(os.getenv("SEARXNG_CACHE_TTL", "21600"))
SEARXNG_MIN_INTERVAL = float(os.getenv("SEARXNG_MIN_INTERVAL", "0.8"))

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads" / "evidence"))
MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(5 * 1024 * 1024)))

# Token rahasia yang dikirim proxy admin Next.js lewat header X-Admin-Token.
# Kosong = endpoint admin ditutup (fail closed).
ADMIN_API_TOKEN = os.getenv("ADMIN_API_TOKEN", "")
RATE_LIMIT_VERIFY_PER_MIN = int(os.getenv("RATE_LIMIT_VERIFY_PER_MIN", "10"))
RATE_LIMIT_REPORT_PER_MIN = int(os.getenv("RATE_LIMIT_REPORT_PER_MIN", "5"))

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

VERIFIN_DEBUG_RAW_JSON = os.getenv("VERIFIN_DEBUG_RAW_JSON", "false").lower() in {
    "1", "true", "yes", "on"
}
