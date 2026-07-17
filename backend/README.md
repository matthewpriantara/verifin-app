# 🛡️ Verifin Backend Engine

**Verifin** adalah platform verifikasi lowongan kerja pintar berbasis **Multimodal OCR**, **OSINT (Open Source Intelligence)**, **Scrapling Engine**, dan **Explainable AI (XAI)** untuk mendeteksi penipuan rekrutmen dan Tindak Pidana Perdagangan Orang (TPPO) siber.

---

## 🧩 3 Pilar Utama Arsitektur Verifin

Verifin bekerja menggunakan arsitektur 3 tahap (Multi-Stage Processing Pipeline):

```
+-------------------+      +-------------------------+      +--------------------------+
| 1. OCR & NER      | ---> | 2. OSINT & Scrapling    | ---> | 3. LLM Reasoner & XAI    |
| (Local OpenCV/    |      | (WHOIS, OSM, Kredibel,  |      | (Grok-4.5 + SHAP         |
|  PaddleOCR/NER)   |      |  GForm Phishing, Web)   |      |  Feature Explainer)      |
+-------------------+      +-------------------------+      +--------------------------+
```

### 1. Ekstraksi Teks & Entitas (OCR + NER)
* **OpenCV CLAHE & Border Padding:** Memproses citra poster/flyer secara lokal (penajaman kontras adaptif pada stempel/logo dan penambahan margin 30px agar teks pinggir tidak terpotong).
* **PaddleOCR / Tesseract:** Mengekstrak piksel teks secara presisi di bawah 1 detik.
* **Regex NER & IndoBERT:** Mengidentifikasi entitas penting (Nama Perusahaan, Nomor WhatsApp `+62`, Email, URL Situs, Alamat Fisik, dan Rentang Gaji).

### 2. Investigasi Intelijen Real-Time (OSINT Engine)
* **WHOIS & DNS Security:** Mengecek umur domain dan enkripsi email (SPF/DMARC).
* **Kredibel Phone API:** Memeriksa reputasi nomor HP/WA pada basis data aduan penipuan publik.
* **OpenStreetMap Geocoding:** Memvalidasi keberadaan koordinat dan alamat kantor fisik secara presisi.
* **Google Form Phishing Inspector (`gform_inspector`):** Mem-follow redirect shortlink (`bit.ly`, `forms.gle`), membaca formulir target, dan mendeteksi indikasi phishing (permintaan No. Rekening, KTP, atau Biaya Admin).
* **Web Scrapling & Medsos Fallback:** Mencari jejak digital perusahaan di web publik, Instagram, Shopee, dan Threads.

### 3. Penalaran & Penjelasan Transparan (LLM Reasoner + SHAP XAI)
* **Verifin Reasoning Engine (`verifin_reasoning.py` via Grok-4.5):** Menganalisis laporan bukti faktual OSINT tanpa halusinasi, menentukan *Verdict* (`AMAN`, `WASPADA`, `BAHAYA`), dan skor risiko (0-100).
* **SHAP Feature Explainer (`shap_explainer.py`):** Menghitung nilai kontribusi additif Shapley untuk setiap fitur (risiko vs aman) dan menghasilkan data `waterfall_chart` siap render di dashboard frontend Next.js.

---

## 📁 Struktur Direktori Backend

```
backend/
├── app/
│   ├── main.py                     # FastAPI Entry Point
│   ├── config.py                   # Konfigurasi Environment & LLM Settings
│   ├── api/
│   │   └── v1/
│   │       ├── health/
│   │       │   └── router.py       # GET /api/v1/health (Health check)
│   │       └── verify/
│   │           ├── router.py       # POST /api/v1/verify/text & POST /api/v1/verify/image
│   │           └── schema.py       # Pydantic Request/Response Schemas
│   └── services/
│       ├── ocr.py                  # Local OCR Engine (OpenCV CLAHE + PaddleOCR/Tesseract)
│       ├── ner.py                  # Named Entity Recognition (Regex + IndoBERT)
│       ├── osint/
│       │   ├── address_validator.py # OpenStreetMap Geocoding
│       │   ├── company_validator.py # Identitas & Legalitas Perusahaan
│       │   ├── gform_inspector.py   # Phishing Shortlink & Google Form Inspector
│       │   ├── phone_validator.py   # Kredibel.id Fraud Reputation Check
│       │   ├── threads_osint.py     # Threads Meta Social Media Scraper
│       │   ├── web_evidence.py      # Scrapling Web & Marketplace Fallback
│       │   └── whois_handler.py     # Domain Age & SPF/DMARC Security Check
│       ├── llm/
│       │   ├── prompt_builder.py    # Anti-Hallucination Prompt Engineering
│       │   ├── client.py            # OpenAgentic LLM HTTP Client
│       │   └── verifin_reasoning.py # LLM Grok-4.5 Reasoning Engine
│       └── xai/
│           └── shap_explainer.py   # SHAP Additive Feature Value Explainer
├── .env.example
├── requirements.txt
└── README.md
```

---

## 🚀 Cara Menjalankan Server Backend

1. **Persiapkan Virtual Environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Konfigurasi Environment Variable (`.env`):**
   ```env
   LLM_BASE_URL=https://openagentic.id/api/v1
   LLM_API_KEY=your_api_key_here
   LLM_MODEL=grok-4.5
   ```

3. **Jalankan Server Uvicorn:**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. **Akses Dokumentasi API:**
   * Swagger UI: `http://localhost:8000/docs`
   * Redoc: `http://localhost:8000/redoc`

---

## 🧪 Endpoint Utama API

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Status kesehatan server, LLM, dan OSINT services. |
| `POST` | `/api/v1/verify/text` | Verifikasi lowongan kerja dari input teks. |
| `POST` | `/api/v1/verify/image` | Verifikasi lowongan kerja dari gambar poster/flyer (Local OCR). |
| `POST` | `/api/v1/verify/debug/ocr` | Debugging murni ekstraksi piksel teks OCR. |
