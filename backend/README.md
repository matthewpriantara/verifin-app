# 🛡️ Verifin Backend Engine

Backend FastAPI untuk **Verifin** — verifikasi lowongan kerja berbasis bukti OSINT
(multimodal OCR + OSINT paralel + LLM reasoning + Evidence Attribution).

---

## 🧩 Arsitektur

```
Input (teks / gambar poster / URL)
   │
   ├─ OCR (PaddleOCR lang=id) + OpenCV CLAHE  ── gambar → teks
   ├─ NER Hibrida: Regex struktural (ner.py) + LLM extraction (entity_extraction.py)
   │     · NLP Layer 1 = STUB (classifier.py, jujur enabled:false)
   ├─ OSINT Engine (services/osint/runner.py — asyncio.gather paralel)
   │     · WHOIS/DNS      : umur domain + SPF/DMARC (domain korporat saja)
   │     · Phone          : Kaspersky Who Calls (scrape) + pencarian laporan SERP publik
   │     · Address        : Nominatim (OSM) — match_level exact/street/area
   │     · Web Evidence   : SearXNG + Scrapling, relevance filter
   │     · Company        : jejak publik + deteksi sindikat (graph)
   │     · Social OSINT   : Instagram/Threads/TikTok/FB via SERP
   │     · GForm Inspector: follow shortlink → parse pertanyaan → phishing flags
   ├─ Fraud Network (graph/fraud_network.py — case-memory 500 kasus)
   ├─ LLM Reasoning (verifin_reasoning.py — verdict AMAN/WASPADA/BAHAYA,
   │     temperature=0, seed=42, 3x retry + fallback evidence-only)
   └─ Evidence Attribution (xai/shap_explainer.py — kontribusi fitur + waterfall)
```

**Status kontrak:** semua probe memakai vocabulary kanonikal di
`services/status_contract.py` (`COMPLETED` / `FOUND` / `NO_RESULTS` /
`NO_RELEVANT_RESULTS` / `UNAVAILABLE` / `PARSE_FAILED` / `INVALID_INPUT` /
`NOT_PROVIDED`).

---

## 🚀 Menjalankan

> **Penting (macOS Intel):** wajib Python 3.11 + `paddlepaddle==2.6.2`.
> Pakai venv `.venv311` yang sudah ada.

```bash
cd backend
.venv311/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# atau setelah activate: uvicorn app.main:app --port 8000 --reload
```

Docs API: http://localhost:8000/docs · Redoc: http://localhost:8000/redoc

### Environment (`backend/.env` — tidak di-commit)

```env
LLM_BASE_URL=https://.../v1            # OpenAI-compatible endpoint
LLM_API_KEY=sk-...                     # wajib
LLM_MODEL=...                          # nama model (dinamis; mis. ag/gemini-3.6-flash-high)
LLM_VISION_MODEL=...                   # model untuk kanal gambar/URL
LLM_TIMEOUT=120
DATABASE_URL=postgresql://...          # PostgreSQL (Supabase pooler OK)
SEARXNG_URL=https://...                # SearXNG self-hosted (engine: bing, brave)
REDIS_URL=redis://localhost:6379/0     # opsional
```

Contoh lengkap di `.env.example`. **Nama model tidak di-hardcode** — dibaca dari
`LLM_MODEL`, sehingga ganti model cukup lewat env (cache otomatis ter-invaliddasi
karena cache key = `sha256(text + model)`).

---

## ⚠️ Catatan Integritas (apa yang ADA vs BELUM)

Dokumen ini menggambarkan kode **apa adanya**, bukan rencana:

- **Tidak ada PII masking / no-retention.** Teks lowongan dikirim **apa adanya** ke
  API LLM eksternal, dan hasil analisis beserta entitas (nomor HP, alamat) **disimpan**
  ke tabel `job_cases` untuk mendukung Fraud Network & riwayat. PII masking adalah
  pekerjaan lanjutan yang direncanakan.
- **Tidak ada Alembic.** Evolusi skema dilakukan via migrasi SQL manual
  (`ALTER TABLE ... IF NOT EXISTS`) di `community/router.py`.
- **Tidak ada Supabase Auth / role.** Supabase hanya dipakai sebagai **hosting
  PostgreSQL**. Endpoint `/community/report` bersifat anonim terbuka.
- **`nlp/classifier.py` adalah STUB** (`enabled:false`) — penilaian sinyal perilaku teks
  dilakukan oleh LLM reasoning, bukan model ML terlatih.
- **Tidak ada tabel `fraud_fingerprints`.** Deduplikasi lintas kasus memakai
  `raw_text_hash` (SHA-256) + pencocokan entitas ternormalisasi di `job_cases` /
  `community_reports`.
- **SearXNG** memakai engine **Bing + Brave** (bukan DDG/Mojeek/Startpage).
- **OSINT alamat** hanya via **Nominatim** (OpenStreetMap); **tidak ada Overpass**.
- **OSINT domain** via **python-whois**; fallback ke **Wayback Machine CDX** (bukan RDAP).
- **XAI** adalah *SHAP-inspired additive scoring* **custom (rule-based)** — bukan library `shap`.

---

## 📁 Struktur

```
backend/
├── app/
│   ├── main.py                    # FastAPI entry + OCR warmup di startup
│   ├── config.py                  # env → config
│   ├── api/v1/
│   │   ├── verify/                # router.py (endpoints), pipeline.py (orchestration), schema.py
│   │   ├── community/             # lapor + moderasi laporan komunitas
│   │   └── health/                # health check
│   ├── database/                  # SQLAlchemy models + postgres client
│   └── services/
│       ├── ocr.py                 # PaddleOCR lang=id + CLAHE + downscale 1000px
│       ├── ner.py                 # regex struktural + _uniq_addresses (dedup by nomor rumah)
│       ├── nlp/classifier.py      # STUB (jujur enabled:false)
│       ├── llm/                   # client (retry+repair JSON), verifin_reasoning, entity_extraction
│       ├── osint/                 # runner.py (probe paralel) + tiap probe per file
│       ├── graph/                 # fraud_network.py (NetworkX)
│       ├── xai/                   # shap_explainer.py → Evidence Attribution
│       ├── status_contract.py     # vocab status kanonikal
│       ├── url_guard.py           # SSRF guard (blok localhost/private IP)
│       └── db_cache.py            # exact-match cache (hash text+model → auto invalidasi)
├── secrets/                       # cookies OSINT (gitignored)
├── test_regression.py             # corpus regression (assert-based, tanpa framework)
├── .env.example
└── requirements.txt
```

---

## 🔌 Endpoint

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Status server + PostgreSQL + LLM |
| `POST` | `/api/v1/verify/text` | Verifikasi dari teks |
| `POST` | `/api/v1/verify/image` | Verifikasi dari gambar (OCR PaddleOCR `lang=id`) |
| `POST` | `/api/v1/verify/url` | Verifikasi dari URL postingan (fetch + OCR gambar) |
| `GET` | `/api/v1/verify/status` | Status LLM (model aktif) |
| `GET` | `/api/v1/check-domain` | Cek cepat umur domain + SPF/DMARC |
| `GET` | `/api/v1/cases` | Riwayat kasus (limit/skip) |
| `GET` | `/api/v1/cases/lookup/by-entity` | Cari case by phone/email/company |
| `GET` | `/api/v1/cases/{case_id}` | Detail kasus per ID |
| `POST` | `/api/v1/community/report` | Kirim laporan komunitas (IP pelapor terekam server-side) |
| `GET` | `/api/v1/community/reports` | Daftar laporan + filter status (moderasi) |
| `PATCH` | `/api/v1/community/reports/{id}` | Approve/reject + catatan reviewer |
| `GET` | `/api/v1/community/check` | Agregasi laporan per entitas (fraud network) |
| `GET` | `/api/v1/community/recent` | Laporan terbaru (publik) |

### Test cepat image

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/verify/image" \
  -F "file=@poster.webp;type=image/webp"
```

---

## 🧪 Regression

```bash
.venv311/bin/python3 test_regression.py
```

Menutup: multi-address (boundary `Cabang:`/`Alamat lain:`), dedup by nomor rumah,
shortlink, scam phone `08...`→`+62...`, SSRF guard, verdict-score contract,
single-token search relevance, effective weight SHAP, metadata NLP STUB.

E2E lengkap: `../test/hasil-test-raw/_run_tests.sh fresh` (butuh server hidup).

---

## 📊 Verdict & Skor

| Verdict | Skor | Arti |
| :--- | :--- | :--- |
| `AMAN` | 0–39 | Tidak ditemukan red flag keras |
| `WASPADA` | 40–74 | Ada kombinasi sinyal mencurigakan |
| `BAHAYA` | 75–100 | Minta biaya / HP fraud / phishing / jejak scam |

Skor diverifikasi service-layer (`_is_valid_llm_output`); LLM gagal 3x →
fallback evidence-only. Cache key = `sha256(text + model)` → ganti model otomatis
invalidasi hasil lama.
