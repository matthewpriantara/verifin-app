# 🛡️ Verifin Backend Engine

**Verifin** adalah platform verifikasi lowongan kerja pintar berbasis **Multimodal OCR**, **OSINT (Open Source Intelligence)**, **Scrapling Engine**, dan **Explainable AI (XAI)** untuk mendeteksi penipuan rekrutmen dan Tindak Pidana Perdagangan Orang (TPPO) siber.

---

## 🧩 3 Pilar Utama Arsitektur Verifin

Verifin bekerja menggunakan arsitektur 3 tahap (Multi-Stage Processing Pipeline):

```
+-------------------+      +-------------------------+      +--------------------------+
| 1. OCR & NER      | ---> | 2. OSINT & Scrapling    | ---> | 3. LLM Reasoner & XAI    |
| (OpenCV CLAHE +   |      | (WHOIS, OSM, Kredibel,  |      | (Grok-4.5 + SHAP         |
|  PaddleOCR +      |      |  GForm, Web, Threads)   |      |  Feature Explainer)      |
|  Regex struktural)|      |                         |      |                          |
+-------------------+      +-------------------------+      +--------------------------+
```

### 1. Ekstraksi Teks & Entitas (OCR + NER)
* **OpenCV CLAHE & Border Padding:** Preprocess poster/flyer lokal (kontras adaptif + margin 30px).
* **PaddleOCR (paddlepaddle 2.6.2 + paddleocr 2.8.1):** Ekstraksi teks lokal (wajib venv Python 3.11 di macOS Intel).
* **Regex NER struktural (`ner.py`):** Full regex (tanpa IndoBERT) — company legal form, alamat multi-layout berbasis pola Indonesia (Jl/Dusun/RT-RW/kode pos, **bukan whitelist kota**), phone `+62`, email, URL, gaji.

### 2. Investigasi Intelijen Real-Time (OSINT Engine)
* **WHOIS & DNS Security:** Umur domain + SPF/DMARC (domain korporat saja; Gmail/Yahoo = netral).
* **Kredibel Phone:** Reputasi nomor HP/WA (scrape + cookie session).
* **OpenStreetMap Geocoding:** Validasi alamat fisik.
* **Google Form Phishing Inspector:** Follow shortlink (`bit.ly`, `forms.gle`), deteksi minta rekening/KTP/biaya.
* **Web Scrapling:** Website + SERP + **query email footprint** (email tidak lagi dicari di Threads).
* **Threads OSINT:** Jejak postingan/brand dari **nama perusahaan** saja.

### 3. Penalaran & Penjelasan Transparan (LLM Reasoner + SHAP XAI)
* **Verifin Reasoning Engine (`verifin_reasoning.py` via Grok-4.5 / OpenAgentic):** Verdict `AMAN` | `WASPADA` | `BAHAYA` + skor 0–100, anti-halusinasi (hanya fakta OSINT).
* **Kalibrasi skor:** Gmail netral untuk UMKM; target UMKM valid (OSM + HP bersih + no fee) **AMAN 5–15**.
* **SHAP Feature Explainer (`shap_explainer.py`):** Kontribusi fitur + `waterfall_chart` untuk frontend.

---

## 📁 Struktur Direktori Backend

```
backend/
├── app/
│   ├── main.py                     # FastAPI Entry Point
│   ├── config.py                   # Environment & LLM Settings
│   ├── api/
│   │   └── v1/
│   │       ├── health/
│   │       │   └── router.py       # GET /api/v1/health
│   │       └── verify/
│   │           ├── router.py       # verify/text, verify/image, verify/status, ...
│   │           └── schema.py       # Pydantic Request/Response
│   └── services/
│       ├── ocr.py                  # OpenCV CLAHE + PaddleOCR
│       ├── ner.py                  # Regex struktural NER (no ML)
│       ├── osint/
│       │   ├── address_validator.py
│       │   ├── company_validator.py
│       │   ├── gform_inspector.py
│       │   ├── phone_validator.py
│       │   ├── threads_osint.py    # query company/brand only
│       │   ├── web_evidence.py     # website + SERP + email search
│       │   └── whois_handler.py
│       ├── llm/
│       │   ├── prompt_builder.py   # anti-halusinasi + kalibrasi skor
│       │   ├── client.py
│       │   └── verifin_reasoning.py
│       └── xai/
│           └── shap_explainer.py
├── secrets/                        # cookies OSINT (gitignored)
├── .env.example
├── requirements.txt
└── README.md
```

---

## 🚀 Cara Menjalankan Server Backend

> **Penting (macOS Intel):** Pakai **Python 3.11** + `paddlepaddle==2.6.2`.  
> Venv Python 3.14 (`.venv`) biasanya **tidak** punya paddle yang jalan.

1. **Virtual Environment (disarankan `.venv311`):**
   ```bash
   cd backend
   python3.11 -m venv .venv311
   source .venv311/bin/activate
   pip install -r requirements.txt
   ```

2. **Environment Variable (`.env`):**
   ```env
   LLM_BASE_URL=https://openagentic.id/api/v1
   LLM_API_KEY=your_api_key_here
   LLM_MODEL=grok-4.5
   ```

3. **Jalankan Uvicorn:**
   ```bash
   .venv311/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   # atau setelah activate:
   uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
   ```

4. **Docs:**
   * Swagger: `http://localhost:8000/docs`
   * Redoc: `http://localhost:8000/redoc`

---

## 🧪 Endpoint Utama API

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` | `/api/v1/health` | Status server + LLM + OSINT |
| `POST` | `/api/v1/verify/text` | Verifikasi dari teks |
| `POST` | `/api/v1/verify/image` | Verifikasi dari gambar (PaddleOCR lokal) |
| `GET` | `/api/v1/verify/status` | Status LLM OpenAgentic |
| `GET` | `/api/v1/check-domain` | Cek cepat umur domain + SPF/DMARC |
| `GET` | `/api/v1/osint/scan-email` | Footprint email |
| `GET` | `/api/v1/osint/scan-username` | Footprint username |

### Contoh test poster
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/verify/image" \
  -F "file=@loker_test2.jpeg"
```

---

## 📊 Verdict & Skor Risiko

| Verdict | Skor | Arti singkat |
| :--- | :--- | :--- |
| `AMAN` | 0–39 | UMKM valid target **5–15**; 0–10 sangat aman |
| `WASPADA` | 40–74 | Ada red flag kombinasi / jejak meragukan |
| `BAHAYA` | 75–100 | Minta biaya, HP fraud, phishing form, scam SERP |

**Netral (bukan red flag tunggal):** email Gmail/Yahoo, gaji tidak disebut, tidak ada website jika alamat OSM valid / medsos aktif.
