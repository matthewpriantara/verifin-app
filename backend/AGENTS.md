# Backend Verifin — Architecture, Pipeline & Guidelines

Dokumentasi teknis backend Verifin (FastAPI, Python 3.11, PostgreSQL 17).

## 1. Entrypoint Aplikasi
- `app/main.py`: Instance FastAPI utama (`app`), lifespan context (DDL tabel DB & warmup PaddleOCR), middleware CORS & request logger, include router dengan prefix `/api/v1` (`verify`, `health`, `community`), serta static mount `/uploads`.
- `main.py`: Entrypoint runner uvicorn lokal (`uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)`).

## 2. Struktur Modul `app/`
- `app/api/v1/`: Endpoint REST API (`app/api/v1/verify/`, `app/api/v1/health/`, `app/api/v1/community/`) dan orkestrasi pipeline.
- `app/services/`: Logika bisnis inti (precheck, NER hibrida, OCR, caching, sanitasi PII, keamanan).
- `app/services/osint/`: Modul investigasi multi-channel (phone Kaspersky Who Calls + GetContact + SERP, company SearXNG/AHU, domain/email WHOIS, GForm inspector, OSM Nominatim).
- `app/services/llm/`: Integrasi LLM (`app/services/llm/verifin_reasoning.py`, `app/services/llm/vision.py`, `app/services/llm/entity_extraction.py`, failover Gemini ke Gemma 4).
- `app/services/xai/`: Atribusi bukti aditif berbobot poin & waterfall (`app/services/xai/shap_explainer.py`).
- `app/services/graph/`: Graf korelasi penipuan heterogen (`app/services/graph/fraud_network.py`).
- `app/data/`: Dataset referensi (`app/data/site_kinds.json`, `app/data/employer_domains.json`).

## 3. Urutan Pipeline Verifikasi (`app/api/v1/verify/pipeline.py`)
1. **Cache Lookup:** Cek DB cache berdasarkan content hash (`app/services/db_cache.py`).
2. **Ingestion & Text Extraction:** Direct text, PaddleOCR + model vision, atau web fetcher URL.
3. **Hybrid NER:** Ekstraksi entitas struktural via regex + semantik via LLM (`app/services/ner.py`).
4. **NLP & Precheck:** Deteksi sinyal perilaku (`app/services/nlp/classifier.py`) dan validasi input (`app/services/precheck.py`: filter non-job I-01, input pendek I-03, multi-employer I-04).
5. **Multi-Channel OSINT Probes:** Eksekusi probe paralel (`app/services/osint/runner.py`) lalu pengayaan entitas.
6. **Graph & Community:** Korelasi graf penipuan (`app/services/graph/fraud_network.py`) & agregasi laporan komunitas.
7. **LLM Synthesis & Scoring:** Multi-factor synthesis prompt (`app/services/llm/verifin_reasoning.py`): AMAN (0–39), WASPADA (40–74), BAHAYA (75–100).
8. **XAI Attribution:** Waterfall poin kontribusi bukti (`app/services/xai/shap_explainer.py`).
9. **Persistence & Response:** Simpan hasil ke PostgreSQL dan kirim SSE / JSON (`VerifyResponse`).

## 4. Aturan Penting Kode
- **Status Contract:** Probe OSINT wajib menggunakan string status resmi dari `app/services/status_contract.py` (`COMPLETED`, `FOUND`, `NO_RESULTS`, `NO_RELEVANT_RESULTS`, `UNAVAILABLE`, `PARSE_FAILED`, `INVALID_INPUT`, `LOGIN_REQUIRED`).
- **Host Lists Terpusat:** Daftar jenis situs (`app/data/site_kinds.json`) dan domain resmi terverifikasi (`app/data/employer_domains.json`) HANYA boleh di folder `app/data/`. Dilarang hardcode host di kode Python; dicek oleh tes `tests/test_audit007_blindspots.py`.
- **Cache Schema Version:** Nilai `CACHE_SCHEMA_VERSION = 15` di `app/services/db_cache.py`. Wajib dinaikkan bila ada perubahan skema respons atau bobot skor agar data usang tidak dipakai.

## 5. Menjalankan & Pengujian (Sesuai CI)
- **Menjalankan Dev:** `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` (atau `python main.py`).
- **Dependensi OS (CI):** `sudo apt-get install -y --no-install-recommends libgl1 libglib2.0-0`.
- **Dependensi Python:** `pip install -r requirements.txt pytest pytest-asyncio pytest-cov`.
- **Menjalankan Tes:** `pytest -q --cov=app --cov-report=term --cov-report=xml`.
  *(Saat CI berjalan tanpa DB/LLM/admin, variabel di-set kosong agar menguji fallback/fail-closed).*

## 6. Variabel Lingkungan Utama (dari `.env.example`)
- **LLM:** `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT`, `LLM_EXTRACTOR_MODEL`, `LLM_FALLBACK_BASE_URL`, `LLM_FALLBACK_API_KEY`, `LLM_FALLBACK_MODEL`, `LLM_FALLBACK_TIMEOUT`, `LLM_FALLBACK_EXTRACTOR_MODEL`, `LLM_VISION_BASE_URL`, `LLM_VISION_API_KEY`, `LLM_VISION_MODEL`.
- **Database & Cache:** `DATABASE_URL`, `VERIFY_CACHE_ENABLED`.
- **OSINT:** `SEARXNG_URL`, `SEARXNG_TIMEOUT`, `SEARXNG_CACHE_TTL`, `SEARXNG_MIN_INTERVAL`, `GETCONTACT_URL`, `GETCONTACT_TOKEN`, `GETCONTACT_TIMEOUT`, `NOMINATIM_URL`, `OSINT_TIMEOUT_SEC`, `OSINT_USER_AGENT`.
- **Keamanan & Admin:** `ADMIN_API_TOKEN`, `RATE_LIMIT_VERIFY_PER_MIN`, `RATE_LIMIT_REPORT_PER_MIN`, `CORS_ORIGINS`, `UPLOAD_DIR`, `MAX_UPLOAD_SIZE_BYTES`, `VERIFIN_DEBUG_RAW_JSON`.
