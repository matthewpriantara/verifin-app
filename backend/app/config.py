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
# Batas panggilan serentak ke penyedia LLM utama. Penyedia yang membatasi permintaan aktif per
# kunci (mis. 3) membalas 429 bila dilampaui; dengan batas ini panggilan mengantre di sini.
# 0 = tanpa batas.
LLM_MAX_CONCURRENCY = int(os.getenv("LLM_MAX_CONCURRENCY", "0"))
# Sebagian gateway membuang pesan system yang panjang tanpa galat, sehingga model menjawab
# tanpa aturan ekstraksi/penalaran. Bila true, isi pesan system digabung ke pesan user pertama
# untuk panggilan ke model utama dan vision (cadangan lokal tidak terpengaruh).
LLM_SYSTEM_AS_USER = os.getenv("LLM_SYSTEM_AS_USER", "false").lower() in ("1", "true", "yes")
# Total detik menunggu ulang setelah 429 sebelum menyerah ke cadangan.
LLM_429_MAX_WAIT = float(os.getenv("LLM_429_MAX_WAIT", "45"))
# Tingkat reasoning effort ("none", "low", "medium", "high") untuk model yang mendukung reasoning tokens.
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "").strip()
# Tingkat berpikir untuk panggilan ekstraksi (entitas, hasil pencarian). Ekstraksi tidak butuh
# penalaran panjang; "none" memangkas waktunya beberapa kali lipat. Kosong = ikut LLM_REASONING_EFFORT.
LLM_EXTRACTOR_REASONING_EFFORT = os.getenv("LLM_EXTRACTOR_REASONING_EFFORT", "").strip()
# Matikan (false) saat uji ulang agar setiap kasus dihitung ulang, bukan dibaca dari job_cases.
VERIFY_CACHE_ENABLED = os.getenv("VERIFY_CACHE_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")
# Pembacaan poster oleh model vision, berjalan bersamaan dengan OCR. Kosongkan model untuk mematikan.
# Konfigurasi endpoint terpisah untuk vision model bila model penalaran utama tidak mendukung multimodal.
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
# Tingkat reasoning effort untuk fallback model provider.
LLM_FALLBACK_REASONING_EFFORT = os.getenv("LLM_FALLBACK_REASONING_EFFORT", "").strip()

DATABASE_URL = os.getenv("DATABASE_URL", "")

SEARXNG_URL = os.getenv("SEARXNG_URL", "").rstrip("/")

NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
# Nominatim publik membatasi 1 permintaan/detik untuk seluruh aplikasi; jeda hanya boleh
# diturunkan bila NOMINATIM_URL menunjuk ke instance sendiri.
NOMINATIM_MIN_INTERVAL = float(os.getenv("NOMINATIM_MIN_INTERVAL", "1.0"))
# Batas tunggu antrean cek alamat per permintaan. Lewat dari ini query dilewati supaya
# lonjakan pengguna tidak membuat tahap cek bukti menunggu berpuluh detik.
NOMINATIM_MAX_WAIT = float(os.getenv("NOMINATIM_MAX_WAIT", "12"))
NOMINATIM_MAX_QUERIES = int(os.getenv("NOMINATIM_MAX_QUERIES", "8"))
# Anggaran waktu cek peta untuk satu alamat. Variasi query dicoba berurutan dan tiap query
# menunggu giliran 1/detik bersama permintaan lain; tanpa anggaran, 10 pengguna serentak membuat
# satu alamat menunggu hampir semenit. Lewat anggaran, hasil terbaik sejauh ini yang dipakai.
NOMINATIM_ADDRESS_BUDGET = float(os.getenv("NOMINATIM_ADDRESS_BUDGET", "12"))
NOMINATIM_CACHE_TTL = int(os.getenv("NOMINATIM_CACHE_TTL", "21600"))
# Layanan getcontact-api di home (Tailscale). Kosong = fitur mati dan OSINT telepon tetap jalan
# dengan Kaspersky saja. Lihat backend/getcontact-api/README.md.
GETCONTACT_URL = os.getenv("GETCONTACT_URL", "").rstrip("/")
GETCONTACT_TOKEN = os.getenv("GETCONTACT_TOKEN", "")
GETCONTACT_TIMEOUT = float(os.getenv("GETCONTACT_TIMEOUT", "8"))
# Produksi: layanan dicapai lewat unix socket hasil reverse SSH tunnel dari home,
# karena firewall VPS menolak koneksi container ke port host. Kosong = TCP biasa ke GETCONTACT_URL.
GETCONTACT_UDS = os.getenv("GETCONTACT_UDS", "")
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
