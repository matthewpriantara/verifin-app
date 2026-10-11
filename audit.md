# Laporan Audit Komprehensif Per-File Codebase Verifin

Dokumen ini memuat hasil audit komprehensif **per-file** untuk seluruh berkas yang tercatat pada `AGENTS.md` (Total: 138 berkas), mencakup Root, Backend, dan Frontend.

---

## Ringkasan Audit (Executive Summary)

Seluruh temuan prioritas (bug fungsional, routing, styling, dead code, dan inkonsistensi konfigurasi) telah berhasil diperbaiki dan diverifikasi:
- [x] Bug routing 404 upload komunitas diperbaiki via dual mount `/uploads` dan `/uploads/evidence`.
- [x] 4 file dead code (`entity_validator.py`, `FactorList.tsx`, `RiskMeter.tsx`, `EntityPanel.tsx`) telah dibersihkan.
- [x] Dependensi ganda `framer-motion` telah dihapus dari `package.json`.
- [x] Styling token `Badge.tsx` diperbaiki agar sesuai dengan tema Tailwind v4.
- [x] Fallback domain `API_BASE` diselaraskan ke `https://api.verifin.web.id`.
- [x] Fallback secret session admin diselaraskan ke `verifin-admin-secret-change-me-2026`.
- [x] Path skrip evaluasi ML dibuat dinamis dan menangani dataset offline secara graceful.
- [x] Inisialisasi engine database dan PaddleOCR dilindungi pengaman thread-safe.
---

## 1. Root & CI/CD Configurations

### `[1/138] .github/workflows/deploy.yml`
- **Status:** [VALID - CATATAN MINOR]
- **Temuan:**
  - Push trigger dimatikan secara sengaja (`workflow_dispatch` aktif).
  - Variabel `vars.NEXT_PUBLIC_API_URL` memiliki fallback `'https://api.verifin.web.id'`.

### `[2/138] .gitignore`
- **Status:** [BERSIH / RESOLVED]
- **Temuan:**
  - Aturan duplikat `*.log` telah dihapus; hanya didefinisikan satu kali secara global.

### `[3/138] AGENTS.md`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Berkas dokumentasi panduan agen dan struktur berkas repositori sinkron.

### `[4/138] docker-compose.yml`
- **Status:** [BERSIH / RESOLVED]
- **Temuan:**
  - Definisi jaringan `searxng_default` diubah dari `external: true` menjadi `name: searxng_default`. Docker Compose akan otomatis terhubung jika jaringan sudah ada atau membuatnya secara mandiri jika belum ada, mencegah runtime error fatal.
---

## 2. Backend Root & Machine Learning Scripts

### `[5/138] backend/.dockerignore`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Konfigurasi pengecualian image Docker lengkap (`venv`, `__pycache__`, `uploads/`, `.env`).

### `[6/138] backend/.env`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Berkas environment lokal aktif. Seluruh dead config (`LLM_VISION_MODEL`) telah dibersihkan.

### `[7/138] backend/.env.example`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Selaras dengan `app/config.py`, termasuk `LIGHTPANDA_CDP_URL`.

### `[8/138] backend/.gitignore`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Mengabaikan virtualenv, model weights, cache Python, dan artifacts OSINT.

### `[9/138] backend/Dockerfile`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Multi-stage dependency installation dengan dependensi C OpenCV/Paddle (`libgl1`, `libgomp1`). Healthcheck endpoint mengarah ke `/api/v1/health`.

### `[10/138] backend/evaluasi_classifier.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Nihil. Logika path output telah dinamis menggunakan `EVAL_OUTPUT_DIR` / fallback direktori relatif proyek.

### `[11/138] backend/evaluasi_emscad_full.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Nihil. Path dataset dan output telah dinamis serta menangani ketiadaan dataset EMSCAD lokal secara graceful tanpa crash.

### `[12/138] backend/latih_tfidf_emscad.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Nihil. Path dataset telah dinamis serta menangani ketiadaan dataset EMSCAD lokal secara graceful tanpa crash.
### `[13/138] backend/main.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Runner lokal sederhana untuk uvicorn (`app.main:app`, port 8000, reload=True).

### `[14/138] backend/pyrightconfig.json`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Mengarah ke venv lokal `venv` dengan exclude standar.

### `[15/138] backend/pytest.ini`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Konfigurasi pytest dengan `asyncio_mode = auto`.

### `[16/138] backend/requirements.txt`
- **Status:** [CATATAN ARSITEKTUR]
- **Temuan:**
  - Versi `paddlepaddle>=3.0.0` dan `paddleocr>=3.0.0`. Komentar di baris 27 mencatat bahwa macOS Intel membutuhkan `paddlepaddle==2.6.2`, namun file menentukan `>=3.0.0` (kompatibel untuk Docker Linux amd64, tetapi perlu penanganan khusus saat instalasi manual di macOS x86_64).

---

## 3. Backend App Core & Database

### `[17/138] backend/app/__init__.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Package marker standar.

### `[18/138] backend/app/config.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Sentralisasi variabel lingkungan dengan fallback aman untuk seluruh service.

### `[19/138] backend/app/main.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Nihil. Penggunaan `UPLOAD_DIR` telah disentralisasi dari `app.config`, dan di-mount secara aman ganda (`/uploads` dan `/uploads/evidence`) untuk mencegah 404 pada file bukti komunitas.

### `[20/138] backend/app/api/__init__.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Package marker standar.

### `[21/138] backend/app/api/v1/__init__.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Package marker standar.

### `[22/138] backend/app/api/v1/community/__init__.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Package marker standar.

### `[23/138] backend/app/api/v1/community/router.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Nihil. Rute penyimpanan bukti laporan komunitas selaras dengan mount static files `UPLOAD_DIR`.

### `[24/138] backend/app/api/v1/community/schema.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Skema Pydantic `CommunityReportIn`, `CommunityReportOut`, dan `ModerationUpdate` valid dan memiliki batasan panjang string yang aman.

### `[25/138] backend/app/api/v1/health/__init__.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Package marker standar.

### `[26/138] backend/app/api/v1/health/router.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Nihil. Telemetry status OSINT telah diperbarui menggunakan `kaspersky_whocalls` menggantikan residual Kredibel.

### `[27/138] backend/app/api/v1/verify/__init__.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Package marker standar.

### `[28/138] backend/app/api/v1/verify/pipeline.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Pipeline verifikasi multi-modal (Hybrid NER, OSINT parallel runner, XAI SHAP, dan Graph traversal) terintegrasi dengan baik.

### `[29/138] backend/app/api/v1/verify/router.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Endpoint `/verify/text`, `/verify/image`, `/verify/url`, `/verify/url/stream` (SSE), `/cases`, dan `/cases/{case_id}` berfungsi dengan baik dengan error handling dan DB caching.

### `[30/138] backend/app/api/v1/verify/schema.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Nihil. Default value `LlmStatusResponse` provider telah diselaraskan dengan provider aktif (`google-api`).

### `[31/138] backend/app/database/models.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Model SQLAlchemy `JobCase` dan `CommunityReport` memiliki indeks yang tepat pada field pencarian (`raw_text_hash`, `company_name`, `phone`, `email`, `url`, `status`).

### `[32/138] backend/app/database/postgres_client.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Nihil. Inisialisasi engine dan SessionLocal dilindungi kondisi pemeriksaan `_db_url`, mencegah unhandled crash saat offline/test.
---

## 4. Backend Services

### `[33/138] backend/app/services/__init__.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Package marker standar.

### `[34/138] backend/app/services/constants.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Definisi konstanta threshold skor risiko, free email domain, dan badan hukum valid.

### `[35/138] backend/app/services/db_cache.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Logika caching query PostgreSQL berdasarkan hash input dan versi schema (`CACHE_SCHEMA_VERSION = 7`) berjalan dengan baik untuk menghindari LLM/OSINT ulang pada konten identik.

### `[36/138] backend/app/services/hasher.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Fungsi `compute_content_sha256` dan `detect_identity_syndicate` bekerja akurat untuk mendeteksi nomor telepon/email yang dipakai berulang di berbagai perusahaan berbeda.

### `[37/138] backend/app/services/ner.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Ekstraksi berbasis Regex dengan filter konteks penipuan biaya (`_is_fee_context`) dan normalisasi telepon Indonesia.
### `[38/138] backend/app/services/ocr.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Nihil. Fungsi `get_ocr_model()` telah dilindungi pola double-checked locking thread-safe menggunakan `ocr_lock`.

### `[39/138] backend/app/services/status_contract.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Definisi status audit OSINT konsisten (`NOT_PROVIDED`, `COMPLETED`, `FOUND`, `UNAVAILABLE`, dll.).

### `[40/138] backend/app/services/url_guard.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Pencegahan SSRF ketat: memvalidasi skema HTTP/HTTPS, memblokir localhost, link-local, private IP ranges (RFC 1918), dan resolving DNS socket.

### `[41/138] backend/app/services/web_fetcher.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Scraping halaman lowongan dengan penanganan konten media sosial (Instagram, Threads, LinkedIn) dan pembersihan script/iklan.

### `[42/138] backend/app/services/graph/__init__.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Package marker standar.

### `[43/138] backend/app/services/graph/fraud_network.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Heterogeneous Graph traversal berbasis NetworkX (`JobCase`, `Phone`, `Email`, `Company`) untuk mendeteksi korelasi sindikat penipuan lintas kasus.

### `[44/138] backend/app/services/llm/__init__.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Package marker standar.

### `[45/138] backend/app/services/llm/client.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - HTTP client OpenAI-compatible dengan parser JSON resilient (`_repair_truncated_json` dan `_parse_json_value`) yang menangani output model saat terpotong.

### `[46/138] backend/app/services/llm/entity_extraction.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Modul LLM NER untuk mengekstrak entitas dari teks OCR yang berantakan, terintegrasi di `pipeline.py`.
### `[47/138] backend/app/services/llm/entity_validator.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Nihil. Berkas dead code (244 baris) yang tidak pernah diimpor/digunakan telah dihapus secara bersih dari repositori.

### `[48/138] backend/app/services/llm/prompt_builder.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Penyusun prompt reasoning Verifin dengan injeksi bukti OSINT, sinyal graf sindikat, dan format JSON reasoning.

### `[49/138] backend/app/services/llm/verifin_reasoning.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Orchestrator reasoning LLM, kalkulasi fallback rule-based saat AI unreachable, dan pengecekan kesehatan server AI (`check_ai_status`).

### `[50/138] backend/app/services/nlp/__init__.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Package marker standar.

### `[51/138] backend/app/services/nlp/classifier.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Klasifikasi perilaku lowongan kerja Layer-1 (pre-screening kata kunci penipuan biaya, WhatsApp apply, dan TPPO luar negeri).

### `[52/138] backend/app/services/osint/__init__.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Package marker standar.

### `[53/138] backend/app/services/osint/address_validator.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Geocoding OpenStreetMap / Nominatim dengan pencocokan bertingkat (`exact`, `street`, `area`) dan verifikasi bisnis di Google Maps.

### `[54/138] backend/app/services/osint/ai_extractor.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Ekstraksi data struktural dari hasil scraping web menggunakan LLM fallback.

### `[55/138] backend/app/services/osint/company_validator.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Validasi reputasi dan legalitas entitas perusahaan melalui pencarian multi-query dan analisis digital footprint.

### `[56/138] backend/app/services/osint/gform_inspector.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Inspeksi formulir Google Forms untuk mendeteksi indikasi phishing atau pungutan biaya terselubung.

### `[57/138] backend/app/services/osint/lightpanda_client.py`
- **Status:** [POTENSI TIMEOUT / ENV SENSITIVE]
- **Temuan:**
  - Baris 28–36: Memanggil `docker exec lightpanda ...`. Di dalam container Docker tanpa bind mount `/var/run/docker.sock`, pemanggilan subprocess ini akan selalu melempar error dan masuk ke fallback HTTP client biasa.

### `[58/138] backend/app/services/osint/phone_validator.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Integrasi Scrapling ke Kaspersky Who Calls Indonesia dengan fallback SERP query. Bersih dari logika usang.

### `[59/138] backend/app/services/osint/platform_providers.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Ekstraksi data spesifik untuk domain platform loker (Jobstreet, Glints, Karir.com, Kalibrr, LinkedIn).

### `[60/138] backend/app/services/osint/query_builder.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Pembentukan query Google Dork / OSINT cerdas untuk mendeteksi laporan penipuan entitas.

### `[61/138] backend/app/services/osint/runner.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Eksekusi paralel `asyncio.gather` untuk seluruh probe OSINT (telepon, domain, web evidence, alamat OSM, media sosial).

### `[62/138] backend/app/services/osint/search_intelligence.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Normalisasi hasil pencarian web dan penentuan sinyal risiko/keamanan digital footprint.

### `[63/138] backend/app/services/osint/searxng_client.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Client query ke instans SearXNG lokal dengan rate limiting dan caching TTL.

### `[64/138] backend/app/services/osint/social.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Audit akun media sosial (Instagram, Facebook, LinkedIn, TikTok, X) untuk verifikasi keberadaan profil rekrutmen resmi.

### `[65/138] backend/app/services/osint/web_evidence.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Aggregator bukti digital web, sintesis laporan penipuan dari forum/komunitas online.

### `[66/138] backend/app/services/osint/whois_handler.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Pengecekan usia domain via WHOIS/RDAP dan evaluasi keamanan email domain korporat (rekord SPF / DMARC via DNS resolver).

### `[67/138] backend/app/services/xai/__init__.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Package marker standar.
### `[68/138] backend/app/services/xai/shap_explainer.py`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Nihil. Key bobot fitur nomor telepon telah diperbarui menjadi `phone_fraud_flag` dengan alias backward-compatible.

---

## 5. Frontend Root, Configs, E2E Scripts, & Public Assets

### `[69/138] frontend/.dockerignore`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Mengabaikan `node_modules`, `.next`, `.git`, dan file `.env`.

### `[70/138] frontend/.env`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Berkas environment lokal frontend aktif (`NEXT_PUBLIC_API_URL`).

### `[71/138] frontend/.env.example`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Panduan variabel lingkungan frontend valid.

### `[72/138] frontend/.gitignore`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Standard Next.js gitignore.

### `[73/138] frontend/Dockerfile`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Multi-stage build Node 22 Alpine dengan pnpm dan standalone output mode.

### `[74/138] frontend/e2e-complete.js`
- **Status:** [SCRIPT AD-HOC / HARDCODED PATH]
- **Temuan:**
  - Baris 5: `path.join(__dirname, '../../proposal-verifin/images')`. Skrip ini adalah helper sekali pakai untuk mengambil tangkapan layar proposal dan tidak terhubung ke test suite otomatis.

### `[75/138] frontend/e2e-final.js`
- **Status:** [SCRIPT AD-HOC / HARDCODED PATH]
- **Temuan:**
  - Skrip helper tangkapan layar ad-hoc serupa dengan hardcoded relative path luar repositori.

### `[76/138] frontend/e2e-retry.js`
- **Status:** [SCRIPT AD-HOC / HARDCODED PATH]
- **Temuan:**
  - Skrip helper retry tangkapan layar ad-hoc.

### `[77/138] frontend/e2e-screenshot.js`
- **Status:** [SCRIPT AD-HOC / HARDCODED PATH]
- **Temuan:**
  - Skrip helper tangkapan layar ad-hoc.

### `[78/138] frontend/eslint.config.mjs`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Konfigurasi ESLint flat config dengan pengecualian file e2e ad-hoc (`e2e-*.js`).

### `[79/138] frontend/next.config.ts`
- **Status:** [HARDCODED IP DEV]
- **Temuan:**
  - Baris 5: `allowedDevOrigins: ["100.111.60.81"]`. Hardcoded IP lokal / Tailscale developer saat development.

### `[80/138] frontend/package.json`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Nihil. Dependensi ganda `framer-motion` telah dihapus; project murni menggunakan library resmi `motion`.
### `[81/138] frontend/pnpm-lock.yaml`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Lockfile konsisten dengan pnpm v11.

### `[82/138] frontend/pnpm-workspace.yaml`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Konfigurasi build allowance untuk pnpm (`sharp`, `unrs-resolver`).

### `[83/138] frontend/postcss.config.mjs`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Konfigurasi Tailwind v4 PostCSS plugin.

### `[84/138] frontend/tsconfig.json`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - TypeScript config dengan strict mode dan path alias `@/*`.

### `[85/138] frontend/public/brand/1x1_bg_black.svg`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Asset logo SVG 1:1 latar hitam resmi.

### `[86/138] frontend/public/brand/1x1_bg_white.svg`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Asset logo SVG 1:1 latar putih resmi.

### `[87/138] frontend/public/brand/1x1_black_bg_transparant.svg`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Asset logo SVG 1:1 hitam transparan resmi.

### `[88/138] frontend/public/brand/1x1_white_bg_transparant.svg`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Asset logo SVG 1:1 putih transparan resmi.

### `[89/138] frontend/public/brand/logo_bg_black.svg`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Asset logo horizontal latar hitam resmi.

### `[90/138] frontend/public/brand/logo_bg_white.svg`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Asset logo horizontal latar putih resmi.

### `[91/138] frontend/public/brand/logo_black_bg_transparant.svg`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Asset logo horizontal hitam transparan resmi.

### `[92/138] frontend/public/brand/logo_white_bg_transparant.svg`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Asset logo horizontal putih transparan resmi.

### `[93/138] frontend/public/favicon.ico`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Favicon multi-resolusi (16, 32, 48, 64) logo resmi.

### `[94/138] frontend/public/icon.png`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - High-res PNG (512x512) logo resmi.

### `[95/138] frontend/public/icon.svg`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Vector SVG icon yang mendukung dynamic dark/light mode browser.

---

## 6. Frontend App Router & API Routes

### `[96/138] frontend/src/app/favicon.ico`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Metadata file resmi Next.js App Router.

### `[97/138] frontend/src/app/globals.css`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Design tokens tema Tailwind v4 lengkap (surface cream, semantic verdict colors, typography Geist).

### `[98/138] frontend/src/app/icon.png`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Metadata file PWA / Apple Touch icon resmi.

### `[99/138] frontend/src/app/icon.svg`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Metadata file SVG icon modern dengan media query prefers-color-scheme.

### `[100/138] frontend/src/app/layout.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Root layout dengan cache-busting query (`?v=2`) dan fallback multi-format icon.

### `[101/138] frontend/src/app/loading.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Root loading skeleton untuk homepage.

### `[102/138] frontend/src/app/page.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Re-export `HomePage` bersih.

### `[103/138] frontend/src/app/admin/loading.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Loading skeleton dashboard admin.

### `[104/138] frontend/src/app/admin/page.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Re-export `AdminPage` bersih.

### `[105/138] frontend/src/app/api/admin/login/route.ts`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Nihil. Fallback `SESSION_SECRET` telah diselaraskan ke `"verifin-admin-secret-change-me-2026"`.

### `[106/138] frontend/src/app/api/admin/session/route.ts`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Nihil. Fallback `SESSION_SECRET` telah diselaraskan ke `"verifin-admin-secret-change-me-2026"`.
### `[107/138] frontend/src/app/report/page.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Re-export `ReportPage` bersih.

### `[108/138] frontend/src/app/report/[caseId]/loading.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Loading skeleton halaman detail laporan.

### `[109/138] frontend/src/app/report/[caseId]/page.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Re-export `ReportPage` bersih.

### `[110/138] frontend/src/app/report-job/loading.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Loading skeleton halaman lapor komunitas.

### `[111/138] frontend/src/app/report-job/page.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Re-export `ReportJobPage` bersih.

### `[112/138] frontend/src/app/verify/page.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Redirect route ke `/` bersih.

---

## 7. Frontend Components, Modules, Lib, & Types

### `[113/138] frontend/src/components/report/EntityPanel.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Nihil. Komponen dead code yang tidak pernah diimpor telah dihapus dari repositori.
### `[114/138] frontend/src/components/report/EvidencePanel.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Komponen visualisasi bukti OSINT (web searches, digital footprint, DNS, maps, social) aktif dan terintegrasi di `ReportPage.tsx`.

### `[115/138] frontend/src/components/ui/Badge.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Nihil. Styling varian `neutral` telah diperbaiki menggunakan class token resmi Tailwind v4 (`bg-bg-subtle text-text-secondary border border-border`).
### `[116/138] frontend/src/components/ui/Button.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Komponen button reusable dengan varian (`primary`, `secondary`, `ghost`, `outline`) dan ukuran terstandarisasi.

### `[117/138] frontend/src/components/ui/Logo.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Single Source of Truth untuk branding Verifin dengan vector monogram `VerifinMark`, mendukung ukuran responsif dan mode `inverted`.

### `[118/138] frontend/src/components/ui/Skeleton.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Komponen skeleton placeholder pulse standar.

### `[119/138] frontend/src/components/ui/testimonials-columns-1.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Komponen marquee kolom testimoni interaktif di homepage.

### `[120/138] frontend/src/lib/admin.ts`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Fungsi fetcher admin case dan status AI.

### `[121/138] frontend/src/lib/api.ts`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Nihil. Fallback `API_BASE` telah diselaraskan ke domain resmi `https://api.verifin.web.id`.
### `[122/138] frontend/src/lib/utils.ts`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Utility format string, normalisasi verdict, design tone mapper, dan penyimpanan history localStorage berbasis `useSyncExternalStore`.

### `[123/138] frontend/src/modules/admin/AdminPage.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Dashboard admin lengkap dengan tab log kasus verifikasi, moderasi laporan komunitas, dan status backend AI.

### `[124/138] frontend/src/modules/admin/ModerationTable.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Tabel moderasi laporan komunitas dengan aksi review (approve/reject), catatan moderator, dan preview bukti foto.

### `[125/138] frontend/src/modules/admin/ReportChart.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Visualisasi statistik distribusi verdict dan metrik laporan penipuan.

### `[126/138] frontend/src/modules/home/HomePage.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Landing page utama dengan hero section, VerifyBox, diagram alur deteksi 4 tahap, search history, dan testimoni pengguna.

### `[127/138] frontend/src/modules/home/SearchHistory.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Komponen riwayat verifikasi lokal dengan paginasi dan hapus per item/semua.

### `[128/138] frontend/src/modules/layout/Footer.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Komponen footer terintegrasi dengan `<Logo inverted />`, navigasi, dan disclaimer hukum.

### `[129/138] frontend/src/modules/layout/Navbar.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Header navigasi sticky terintegrasi dengan `<Logo />` dan tombol aksi cepat lapor komunitas.

### `[130/138] frontend/src/modules/report/FactorList.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Nihil. Komponen dead code yang tidak pernah diimpor telah dihapus dari repositori.
### `[131/138] frontend/src/modules/report/ReportPage.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Halaman hasil verifikasi mendalam dengan visualisasi skor risiko, atribusi fitur SHAP, bukti OSINT, dan entitas teridentifikasi.

### `[132/138] frontend/src/modules/report/RiskMeter.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Nihil. Komponen dead code yang tidak pernah diimpor telah dihapus dari repositori.
### `[133/138] frontend/src/modules/report/ShapChart.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Visualisasi bobot kontribusi fitur Explainable AI (SHAP waterfall/bar) terintegrasi aktif di `ReportPage.tsx`.

### `[134/138] frontend/src/modules/report-job/ReportJobPage.tsx`
- **Status:** [DUPLIKASI SKELETON]
- **Temuan:**
  - Baris 47–77: Komponen `ReportJobSkeleton` didefinisikan ulang secara lokal padahal sudah ada di `app/report-job/loading.tsx`.

### `[135/138] frontend/src/modules/verify/VerifyBox.tsx`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Input box verifikasi lowongan multi-modal (teks, gambar poster OCR, dan URL media sosial dengan Server-Sent Events streaming).

### `[136/138] frontend/src/types/admin.ts`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Type definitions admin case, status, dan community report valid.

### `[137/138] frontend/src/types/phosphor.d.ts`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Module declaration untuk `@phosphor-icons/react` dan SSR variant.

### `[138/138] frontend/src/types/verify.ts`
- **Status:** [BERSIH / VALID]
- **Temuan:**
  - Type definitions respon verifikasi, payload OSINT, entitas, dan SSE streaming valid.

---

## Status Rekomendasi Tindak Lanjut

Semua rekomendasi terprioritas telah berhasil diselesaikan 100%:
- [x] Bug URL upload bukti komunitas di backend teratasi (dual static mount).
- [x] Styling class token `Badge.tsx` diperbaiki sesuai token tema Tailwind v4.
- [x] Pembersihan seluruh dead code selesai (`entity_validator.py`, `EntityPanel.tsx`, `FactorList.tsx`, `RiskMeter.tsx`, dan `framer-motion`).
- [x] Penyelarasan konfigurasi selesai (`API_BASE` domain resmi dan `ADMIN_SESSION_SECRET` fallback).
