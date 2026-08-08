# Verifin — Anti-Penipuan Lowongan Kerja (Gemastik XIX / PPL)

> **Job Trust Infrastructure** — verifikasi lowongan kerja berbasis bukti OSINT.
> Setiap klaim bisa dibuktikan, setiap angka bisa diukur, setiap keterbatasan diakui jujur.

Verifin menganalisis lowongan kerja (teks, gambar poster, atau tautan) lalu memberi **Skor Risiko 0–100**
(0 = aman, 100 = bahaya) beserta penjelasan yang dapat diaudit. Semua kesimpulan ditarik dari
**bukti OSINT nyata** (WHOIS, peta, web, laporan komunitas) — bukan tebakan AI.

---

## 1. Arsitektur Singkat

```
Input (teks / gambar / URL)
   ├─ OCR: PaddleOCR lang=id + OpenCV CLAHE (downscale 1000px, preload di startup)
   ├─ NER Hibrida: Regex struktural + LLM extraction (paralel)
   │     · NLP classifier Layer 1 = STUB (belum ada dataset berlabel Indonesia — jujur enabled:false)
   ├─ OSINT Paralel: WHOIS/DNS · Kredibel phone · Nominatim (OSM) · SearXNG+Scrapling ·
   │                 company footprint · social (IG/Threads/TikTok/FB) · Google Form inspector
   ├─ Fraud Network: NetworkX case-memory (500 kasus) + deteksi sindikat nomor/email
   ├─ LLM Reasoning: verdict AMAN/WASPADA/BAHAYA, temperature=0 + seed (deterministik),
   │                 3x retry + fallback evidence-only saat model gagal
   └─ Evidence Attribution: kontribusi fitur + waterfall (rule-based, bukan SHAP statistik)
```

**Stack:** FastAPI · Next.js 14 · PaddleOCR 2.8.1 + OpenCV · SearXNG + Scrapling ·
python-whois · NetworkX · PostgreSQL (Supabase) · LLM OpenAI-compatible (env-driven).

**Status kontrak probe:** vocabulary kanonikal (`COMPLETED`/`FOUND`/`NO_RESULTS`/
`NO_RELEVANT_RESULTS`/`UNAVAILABLE`/`PARSE_FAILED`) — konsumen tidak lagi membaca boolean
`found`/`ok` yang ambigu.

---

## 2. Menjalankan Proyek

### Backend (FastAPI)
```bash
cd backend
.venv311/bin/uvicorn app.main:app --port 8000 --reload   # wajib venv .venv311 (Python 3.11)
```
- Docs API: http://localhost:8000/docs
- Isi `backend/.env` dari `.env.example` (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`,
  `DATABASE_URL`, `SEARXNG_URL`).
- Detail lengkap: `backend/README.md`.

### Frontend (Next.js 14)
```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```
- Isi `frontend/.env.local`: `NEXT_PUBLIC_API_URL=http://localhost:8000` (+ `ADMIN_PASSWORD` untuk admin).
- Detail lengkap: `frontend/README.md`.

---

## 3. Fitur

- **Verifikasi** teks / gambar poster / URL — laporan berisi verdict, skor, faktor risiko/aman,
  entitas terekstrak, bukti OSINT, graf fraud, Evidence Attribution, latensi OCR.
- **Lapor Komunitas** (`/report-job`) — pengguna melaporkan lowongan mencurigakan
  (`POST /api/v1/community/report`, IP pelapor terekam server-side).
- **Moderasi & Admin** (`/admin`) — riwayat kasus + approve/reject laporan komunitas
  (status `pending`/`approved`/`rejected` + catatan reviewer).
- **Cache exact-match** — hash `text + model LLM`; ganti model otomatis invalidasi hasil lama.

---

## 4. Testing

| Jenis | Perintah | Keterangan |
|-------|----------|------------|
| Regression unit | `cd backend && .venv311/bin/python3 test_regression.py` | 9 kasus: multi-address, shortlink, scam phone, SSRF, verdict-score, single-token search, effective weight, NLP STUB |
| E2E 3 kanal | `test/hasil-test-raw/_run_tests.sh fresh` (di repo `gemastik19`) | text / image OCR / URL; butuh server hidup |

Catatan: `dataset/fake_job_postings.csv` (EMSCAD ~48MB) tidak di-commit; skrip
`backend/evaluasi_emscad_full.py` & `backend/latih_tfidf_emscad.py` tersedia untuk
evaluasi ulang — tetapi **classifier TF-IDF tidak aktif** di pipeline (STUB).

---

## 5. Struktur Penting

```
backend/app/
├── api/v1/verify/          # router, pipeline (orchestration), schema
├── api/v1/community/       # lapor + moderasi
├── services/
│   ├── ocr.py · ner.py · nlp/ · llm/ · osint/ (runner.py + probe) · graph/ · xai/
│   ├── status_contract.py · url_guard.py · db_cache.py
├── test_regression.py
frontend/src/
├── modules/{home,verify,report,report-job,admin}/
├── lib/{api,admin}.ts · types/{verify,admin}.ts
```
