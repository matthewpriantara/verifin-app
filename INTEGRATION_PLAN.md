# 🛡️ Verifin - Comprehensive Application & Development Integration Plan

Dokumen ini berisi rangkuman integrasi sistem, arsitektur teknologi, *tools*, logika bisnis, serta status progres pengembangan platform **Verifin** (Engine Verifikasi Lowongan Kerja Pintar & Deteksi TPPO Siber).

---

## 📌 1. Ikhtisar Aplikasi (Executive Summary)

**Verifin** adalah platform verifikasi lowongan kerja berbasis kecerdasan buatan dan intelijen siber real-time. Aplikasi ini dirancang untuk mendeteksi penipuan rekrutmen dan kejahatan Tindak Pidana Perdagangan Orang (TPPO) siber dengan menganalisis poster gambar, deskripsi teks, maupun link postingan media sosial/job portal.

---

## 🏗️ 2. Arsitektur Integrasi & Stack Teknologi

Platform Verifin menggunakan arsitektur **Decoupled Frontend & Backend** yang terhubung melalui REST API berkinerja tinggi:

```
[ Frontend: Next.js + React ] 
            │ (HTTP / REST API)
            ▼
[ Backend Engine: FastAPI ]
    ├── 1. Preprocessing (OpenCV CLAHE + PaddleOCR)
    ├── 2. Information Extraction (Regex NER Indonesia)
    ├── 3. Live Intelligence (OSINT Multi-Engine & Scrapling)
    ├── 4. AI Reasoning (OpenAgentic LLM)
    ├── 5. Explainable AI (SHAP Feature Explainer)
    └── 6. Persistence & Cache (PostgreSQL 16 + Redis)
```

---

## 🛠️ 3. Rincian Fitur & Tools yang Sudah Terintegrasi

### A. Core Pipeline Backend Engine (`backend/app/`)
1. **Multimodal Extraction (OCR & NER)**
   * **OpenCV CLAHE & Border Padding:** Pemrosesan awal kontras poster gambar dan menambahkan *margin padding* 20px agar teks logo/header terdeteksi sempurna.
   * **PaddleOCR Engine (`ocr.py`):** Pembacaan teks poster gambar secara lokal berlatensi rendah dengan optimasi *downscaling* poster besar.
   * **Regex NER Indonesia (`ner.py`):** Ekstraksi nama perusahaan, nomor HP/WA (`+62` & landline area `021`/`0274`), email, URL, rentang gaji, dan alamat fisik multi-layout Indonesia.

2. **OSINT Intelligence Engine (`backend/app/services/osint/`)**
   * **Kredibel.id Phone Scraper:** Pengecekan real-time status nomor telepon kontak loker terhadap laporan penipuan online.
   * **OpenStreetMap (Nominatim & Overpass API):** *Geocoding* koordinat alamat fisik kantor dan verifikasi keberadaan nama bisnis di peta lokasi.
   * **WHOIS & Email Security Inspector:** Evaluasi umur domain website perusahaan, reputasi domain, serta status SPF/DMARC (Domain gratisan seperti Gmail/Yahoo diperlakukan secara netral).
   * **Web & SERP Scrapling Engine (`web_evidence.py`):** Pencarian jejak digital publik (DuckDuckGo, Yahoo Search, Bing) untuk verifikasi laporan scam dan keberadaan akun Instagram/medsos resmi.
   * **Google Form Phishing Inspector:** Ekstraksi *shortlink* (`bit.ly`, `forms.gle`) dan pengujian indikator pemerasan biaya admin, nomor rekening, atau identitas KTP.

3. **Explainable AI (XAI) & Penalaran (`llm/` & `xai/`)**
   * **OpenAgentic LLM Reasoner:** Penalaran anti-halusinasi yang mengevaluasi fakta OSINT menjadi status keputusan: **`AMAN`**, **`WASPADA`**, atau **`BAHAYA`** beserta *risk score* (0–100).
   * **SHAP Feature Explainer (`shap_explainer.py`):** Mengalkulasi nilai Shapley (*additive features*) untuk menjelaskan kontribusi matematis tiap bukti (seperti laporan Kredibel atau validasi alamat OSM) yang menghasilkan data `waterfall_chart` transparan.

4. **Database & Caching Layer (`app/database/`)**
   * **PostgreSQL 16 Engine:** Penyimpanan riwayat kasus verifikasi (`job_cases`) dan *whitelist* data legalitas perusahaan (`ahu_whitelist`).
   * **Exact Hash DB Caching:** Pengecekan otomatis hash SHA-256 pada input lowongan untuk memberikan respons instan (*cache hit*) tanpa memanggil LLM/OSINT ulang jika data sudah pernah diproses.
   * **Case Memory API (`/cases/lookup/by-entity`):** Endpoint pencarian riwayat kasus terdahulu berdasarkan *exact-match* nomor HP, email, atau nama perusahaan.

---

### B. Antarmuka Pengguna Frontend (`frontend/src/`)
* **Framework:** Next.js (App Router), React, Tailwind CSS, TypeScript.
* **Fitur UI Terintegrasi:**
  * Form input multimodal (Verifikasi Teks, Unggah Gambar Poster, dan Input URL Link Postingan).
  * Dashboard visualisasi hasil analisis risiko, rincian faktor aman vs. faktor risiko.
  * Komponen grafik penjelasan transparan (*Explainable AI Waterfall Chart*).
  * Halaman *Case History* untuk menelusuri arsip verifikasi terdahulu.

---

## 🚦 4. Status Integrasi & Kesiapan Sistem

| Komponen / Fitur | Status | Catatan Integrasi |
| :--- | :---: | :--- |
| **PostgreSQL Database** | ✅ **Terintegrasi** | Tabel `job_cases` & `ahu_whitelist` aktif di PostgreSQL 16 via Docker. |
| **FastAPI REST Server** | ✅ **Terintegrasi** | Memiliki endpoint `/verify/text`, `/verify/image`, `/verify/url`, `/cases/lookup`. |
| **OpenAgentic LLM** | ✅ **Terintegrasi** | Terhubung via API key ke model gratis `mimo-v2.5-free` & `hy3-free`. |
| **Kredibel & Web OSINT** | ✅ **Terintegrasi** | Scraper multi-engine aktif dengan penanganan rate-limit. |
| **OpenStreetMap & Overpass** | ✅ **Terintegrasi** | Geocoding & verifikasi tempat fisik dengan header `User-Agent` terverifikasi. |
| **SHAP XAI Engine** | ✅ **Terintegrasi** | Menghasilkan breakdown kontribusi fitur numerik & waterfall chart JSON. |
| **Frontend UI Integration** | 🔄 **Dalam Pengembangan** | Menghubungkan komponen Next.js ke endpoint FastAPI V1. |

---

## 📑 5. Panduan Menjalankan Sistem Terintegrasi

### 1. Menyalakan Database PostgreSQL
```bash
docker compose -f backend/app/database/docker-compose.yml up -d
```

### 2. Menjalankan Inisialisasi Database
```bash
cd backend
python scripts/init_db.py
```

### 3. Menjalankan Server Engine Backend
```bash
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 4. Menjalankan Client Frontend
```bash
cd frontend
npm run dev
```

---

*Dokumen ini diperbarui secara otomatis berdasarkan milestone progres pengembangan platform Verifin.*
