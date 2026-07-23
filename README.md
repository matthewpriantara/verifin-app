# Verifin — Anti-Penipuan Lowongan Kerja (Gemastik XIX / PPL)

> **Job Trust Infrastructure** — verifikasi lowongan kerja berbasis bukti OSINT.
> Setiap klaim bisa dibuktikan, setiap angka bisa diukur, setiap keterbatasan diakui jujur.

Verifin menganalisis lowongan kerja (teks, gambar poster, atau tautan) lalu memberi **Skor Risiko 0–100**
(0 = aman, 100 = bahaya) beserta penjelasan yang dapat diaudit. Bukan sekadar "tebakan AI" — semua
kesimpulan ditarik dari **bukti OSINT nyata** (WHOIS, peta, web, laporan publik).

**Status kesiapan:** ✅ SIAP dikumpulkan tahap awal — skor internal ~92/100.
Lihat ringkasan lengkap di repo pendamping [`gemastik19`](../gemastik19) (folder `kritik-juri/`).

---

## 1. Arsitektur Singkat

Pipeline 4 layer (dijalankan bertahap, hasil deterministik):

```
Input (teks/gambar/link)
   │
   ├─ Layer 1: NER Hibrida — Regex (entitas struktural) + LLM extraction (entitas semantik)
   │            + PaddleOCR bila input berupa gambar poster
   ├─ Layer 2: Klasifikasi Teks — TF-IDF + Logistic Regression (hybrid ML + aturan perilaku)
   │            dilatih pada dataset EMSCAD → ROC-AUC 0,996 · Recall 98,4%
   ├─ Layer 3: OSINT Engine (paralel, asyncio)
   │            ├─ Domain/URL  : WHOIS/RDAP, umur domain, keaktifan web, inspeksi shortlink/GForm
   │            ├─ Phone       : validasi format + prefix operator + cek laporan Kredibel (scraping)
   │            └─ Company     : multi-engine web search (DuckDuckGo/Yahoo/Bing) + relevance filter,
   │                            validasi alamat via OpenStreetMap (Nominatim), deteksi sosial media
   └─ Layer 4: LLM Reasoning + XAI — kimi-k3-high via OpenAgentic, temperature=0 (deterministik),
                evidence-only prompting (hanya boleh menyimpulkan dari bukti OSINT), NetworkX graph
```

**Stack:** FastAPI (backend) · Next.js 14 (frontend) · scikit-learn TF-IDF+LogReg · PaddleOCR 2.8.1 +
OpenCV · Scrapling · curl_cffi + BeautifulSoup · python-whois · NetworkX · OpenStreetMap · Kredibel.

---

## 2. Menjalankan Proyek

### Backend (FastAPI)
```bash
cd backend
source .venv311/bin/activate        # virtualenv Python 3.11 (sudah ada, jangan dibuat ulang sembarangan)
uvicorn app.main:app --port 8000 --reload
```
- Docs API: http://localhost:8000/docs
- Matikan server: `lsof -tiTCP:8000 -sTCP:LISTEN | xargs kill -9`

### Frontend (Next.js 14)
```bash
cd frontend
npm install   # pertama kali
npm run dev   # jalan di http://localhost:3000 (hot-reload)
```

### Environment
Salin `.env.example` → `.env` (backend) dan `.env.local` (frontend), isi kunci API yang diperlukan.
**File `.env` tidak di-commit** — minta kredensial ke tim.

---

## 3. Testing & Evaluasi

| Jenis | Lokasi / Perintah | Hasil |
|-------|-------------------|-------|
| Evaluasi model (EMSCAD) | `backend/evaluasi_emscad_full.py` | ROC-AUC **0,996** · Recall **98,4%** · F1 0,718 |
| Latih ulang classifier | `backend/latih_tfidf_emscad.py` | model → `backend/app/services/nlp/model/` |
| Test end-to-end | lihat repo `gemastik19/test/` | 3 kanal OK; negatif → BAHAYA skor 95 |

**Catatan data:** `dataset/fake_job_postings.csv` (EMSCAD, ~48 MB) **tidak di-commit** karena besar.
Unduh terpisah bila ingin melatih/evaluasi ulang. Model hasil latih (`.pkl`) juga lokal-only.

---

## 4. Struktur Kode Penting

```
backend/app/
├─ api/v1/verify/router.py     # endpoint verifikasi (teks/gambar/link)
├─ api/v1/community/           # komunitas (lapor & upvote/downvote)
├─ services/
│  ├─ ner.py                   # Regex NER + entitas struktural
│  ├─ llm/
│  │  ├─ entity_extraction.py  # ekstraksi entitas semantik via LLM
│  │  └─ verifin_reasoning.py  # Layer 4: evidence-only reasoning
│  ├─ nlp/classifier.py        # Layer 2: TF-IDF + LogReg hybrid
│  ├─ osint/
│  │  ├─ web_evidence.py       # multi-engine search + RELEVANCE FILTER entitas
│  │  ├─ whois_handler.py      # domain/whois
│  │  ├─ phone_validator.py    # nomor HP + Kredibel
│  │  ├─ address_validator.py  # geocoding OpenStreetMap
│  │  ├─ company_validator.py  # jejak perusahaan
│  │  ├─ social_osint.py       # deteksi sosial media
│  │  └─ gform_inspector.py    # deteksi shortlink/Google Form
│  ├─ graph/fraud_network.py   # NetworkX fraud network
│  └─ cache_service.py         # cache konsisten antar kanal
frontend/src/
├─ components/verify/VerifyBox.tsx   # input teks/gambar/link (isPureUrl, auto-resize)
└─ components/report/RiskMeter.tsx   # gauge skor risiko (0/45/80+)
```

---

## 5. Prinsip Integritas (untuk juri)

- **Tidak ada hardcode/fabrikasi** di output — semua dari data nyata yang bisa diverifikasi ulang.
- **Deterministik:** `temperature=0`, seed tetap → input sama = hasil sama.
- **Evidence-only:** LLM dilarang klaim di luar bukti OSINT.
- **Jujur soal batas:** legalitas AHU/OSS tidak diverifikasi otomatis (tidak ada API publik) — diakui terbuka.

---

## 6. Untuk Teman Tim

- Branch kerja: **`hafidz`** · branch utama: **`main`**.
- Sebelum commit: pastikan `git status` tidak menyertakan `.env`, `dataset/`, `node_modules/`, atau `*.aux` LaTeX (sudah di-`.gitignore`).
- Backend HARUS pakai `.venv311` (Python 3.11) — PaddleOCR/scikit-learn sudah terpasang di situ.
- Dokumen proposal & analisis juri ada di repo **`gemastik19`**, bukan di repo ini.
