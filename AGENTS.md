# Verifin App — Codebase Guidelines & Architecture

Full-stack codebase untuk **Verifin: Platform Deteksi Lowongan Kerja Palsu Berbasis AI & OSINT**.

## Hubungan dengan Dokumen Lomba (`gemastik19`)

- Workspace dokumen lomba: `../gemastik19` (parent: `/Users/fizualstd/Documents/GitHub/_LOMBA/gemastik19`).
- Spesifikasi sistem, laporan, dan proposal merujuk pada: `../gemastik19/siap-submit/` dan `../gemastik19/proposal-verifin/`.

## Stack & Services

- **Backend:** FastAPI (Python 3.11), SQLAlchemy, PostgreSQL, Redis, NetworkX (Fraud Graph), SHAP (Explainable AI), PaddleOCR (OCR).
- **Frontend:** Next.js 16 (React 19, App Router, TypeScript), Tailwind CSS v4, Motion, Phosphor Icons.
- **External Services / Containers (`docker-compose.yml`):**
  - PostgreSQL (`:5432`) & Redis (`:6379`)
  - SearXNG (`:8080`) — Web search intelligence & evidence scraping

## Alur Pipeline Verifikasi (`/api/v1/verify/`)

1. **Ingestion & Text Extraction:**
   - Text direct (`/text`), Image OCR (`/image` via `app.services.ocr`), URL scraping (`/url-stream` via `app.services.web_fetcher`).
2. **Hybrid NER:**
   - Regex-based heuristics + LLM extraction (`app.services.ner` & `app.services.llm.entity_extraction`).
   - Normalisasi nomor telepon (+62) dan sanitasi domain/email.
3. **Multi-Channel OSINT Probes (`app.services.osint.runner`):**
   - Telepon (Kredibel / Whocalls via `phone_validator.py`)
   - Perusahaan & AHU/Pemerintah via SearXNG (`company_validator.py`)
   - Domain age & email SPF/DKIM/MX via WHOIS (`whois_handler.py`)
   - Google Forms phishing check (`gform_inspector.py`)
   - Alamat & geocoding OpenStreetMap (`address_validator.py`)
4. **Graph & Explainable AI:**
   - Heterogeneous Fraud Network correlation (`app.services.graph.fraud_network`).
   - SHAP local explanation waterfall (`app.services.xai.shap_explainer`).
5. **LLM Synthesis & Scoring Verdict:**
   - Multi-factor synthesis prompt (`app.services.llm.verifin_reasoning`).
   - Verdict output: `AMAN` (0–29), `WASPADA` (30–69), `BAHAYA` (70–100).
   - Real-time stage updates dikirim ke frontend via Server-Sent Events (SSE).

## Perintah Pengembangan & Pengujian

- **Backend:**
  ```bash
  cd backend
  source venv/bin/activate  # jika ada venv lokal
  uvicorn app.main:app --reload --port 8000
  pytest
  ```
- **Frontend:**
  ```bash
  cd frontend
  pnpm dev       # berjalan di http://localhost:3000
  pnpm lint
  pnpm build
  ```
- **Docker Stack:**
  ```bash
  docker-compose up -d
  ```

## Konvensi & Aturan Penting

- **Status Contract:** Semua modul OSINT WAJIB mengembalikan status string baku dari `app.services.status_contract` (`COMPLETED`, `FOUND`, `NO_RESULTS`, `UNAVAILABLE`, dsb).
- **Caching:** Cache verifikasi berbasis SHA-256 content hash di `app.services.db_cache` & `app.services.hasher`.
- **Git Isolation:** Setiap perubahan kode di repo ini WAJIB diisolasi dengan flag `-C verifin-app`. Pastikan cek branch (`git -C verifin-app branch --show-current`).
