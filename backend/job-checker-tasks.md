# Panduan Tugas & Arsitektur Backend & AI Engineer (Verifin)

Dokumen ini berisi detail tugas, arsitektur aliran data (dataflow), serta urutan langkah implementasi yang harus kamu lakukan sebagai **Backend & AI Engineer** untuk platform **Verifin** sesuai dengan rencana `job-checker-plan.md`.

---

## 🗺️ Gambaran Umum Alur Sistem (Flow)

Proses dimulai saat pengguna mengirim data (teks, tautan, gambar screenshot) hingga sistem menghasilkan skor risiko (*risk score*) dan analisis forensik yang terstruktur.

```
[User Input] 
     │ (Screenshot, Teks Lowongan, Email, dll.)
     ▼
[1. Ingestion Layer] ──► (PaddleOCR) ──► Ekstraksi Teks Kasar
     │
     ▼
[2. Entity Extraction (NER)] ──► (IndoBERT NER) ──► Entitas Terstruktur (PT, No. HP, Domain/Email, Alamat)
     │
     ▼
[3. OSINT Harvester Engine] ──► (WHOIS, DNS/SPF/DMARC, GetContact API, Maps, AHU/OSS Local DB)
     │
     ▼
[4. Reasoning Engine (Hermes LLM)] ──► Menghitung Risk Score + Analisis Forensik JSON
     │
     ├─► [5. Neo4j Graph DB & PyG GNN] ──► Melacak relasi sindikat & update skor risiko relasional
     │
     ▼
[6. SHAP Explainer (XAI)] ──► Menerjemahkan fitur numerik ke penjelasan ramah pengguna
     │
     ▼
[Output ke User] ──► Next.js Dashboard / WhatsApp Bot
```

---

## 🛠️ Rincian Urutan Tugas & Implementasi

Berikut adalah langkah-langkah implementasi yang harus kamu lakukan secara berurutan:

### Langkah 1: Setup Environment & Dependencies
Persiapkan workspace backend agar mendukung pemrosesan AI lokal dan scraping data.
*   [ ] Pastikan Docker berjalan untuk database pendukung (**Neo4j**, **PostgreSQL**, **Redis**).
*   [ ] Setup python virtual environment dan install dependencies tambahan di `requirements.txt` (misalnya: `spacy` atau `transformers` untuk IndoBERT, `paddleocr` untuk OCR, `neo4j` untuk driver database graf).

### Langkah 2: Implementasi Ingestion & Extraction Layer
Tugas ini fokus untuk mengubah input mentah pengguna menjadi entitas yang siap diperiksa.
*   [ ] **PaddleOCR Integration:**
    *   Buat modul `services/ocr.py` untuk menerima upload gambar (screenshot loker/chat).
    *   Gunakan `PaddleOCR` untuk mengekstrak teks dari gambar tersebut dengan tingkat akurasi tinggi.
*   [ ] **IndoBERT NER Integration:**
    *   Buat modul `services/ner.py` dengan model NLP lokal (seperti `indobenchmark/indobert-base-p1` atau model Hugging Face `w11wo/indobert-jakarta-ner`).
    *   Gunakan model ini untuk mengidentifikasi entitas utama dari teks:
        *   `COMPANY` (Nama Perusahaan/PT)
        *   `CONTACT` (Nomor HP/WhatsApp)
        *   `URL` / `EMAIL` (Tautan website & email pengirim)
        *   `ADDRESS` (Alamat kantor)
        *   `SALARY` (Nominal gaji ditawarkan)

### Langkah 3: Ekspansi OSINT Harvester Module
Kembangkan modul investigasi otomatis berdasarkan entitas yang diekstrak oleh NER.
*   [ ] **WHOIS & SPF/DMARC Module (Sudah ada versi dasar di `test_osint.py`):**
    *   Rapikan dan integrasikan modul deteksi umur domain (`check_domain_age`) dan keamanan SPF/DMARC (`check_email_security`) ke dalam flow backend utama.
*   [ ] **GetContact Scraper / Mock Service:**
    *   Buat modul untuk mendeteksi *reputasi tag* nomor HP penipu (apakah ditandai sebagai "penipu", "loker palsu", dll.).
*   [ ] **AHU & OSS Local DB Validator:**
    *   Buat query pencarian ke *local database copy* (PostgreSQL) berisi daftar PT terdaftar dari Kemenkumham untuk memvalidasi legalitas badan usaha.
*   [ ] **Maps API Location Verifier:**
    *   Gunakan Geocoding API untuk memverifikasi apakah alamat yang dicantumkan merupakan kantor nyata atau lahan kosong/koordinat fiktif.

### Langkah 4: Hubungkan ke AI Reasoning Engine (Hermes LLM)
Hubungkan payload OSINT yang sudah dikumpulkan dengan model bahasa lokal untuk penalaran tingkat tinggi.
*   [ ] **Setup Ollama / local vLLM:**
    *   Pastikan model `Nous-Hermes-2-Pro-Llama-3-8B` dapat diakses secara lokal.
*   [ ] **Hermes Prompt Engineering:**
    *   Buat skema prompt terstruktur yang menerima:
        1. Teks lowongan asli hasil OCR.
        2. Objek JSON dari hasil OSINT (Legalitas PT, Umur Domain, Keamanan Email, Reputasi No. HP, Validitas Alamat).
    *   Perintahkan model untuk merespon **hanya dalam format JSON terstruktur** dengan format:
        ```json
        {
          "risk_score": 85,
          "verdict": "WASPADA / BAHAYA / AMAN",
          "reasons": [
            "Domain email baru dibuat kurang dari 30 hari.",
            "PT yang dicantumkan tidak terdaftar di database resmi AHU Kemenkumham."
          ],
          "explainable_ai_summary": "Sistem mendeteksi adanya indikasi penipuan karena ketidakcocokan badan hukum dan pembuatan situs web rekrutmen yang sangat baru."
        }
        ```

### Langkah 5: Integrasi Database Graf (Neo4j)
Simpan data relasional untuk melacak jaringan sindikat penipuan berulang.
*   [ ] **Skema Node & Relasi:**
    *   Rancang skema Neo4j yang menghubungkan entitas: `(Perusahaan)-[MENGGUNAKAN]->(Telepon)`, `(Perusahaan)-[MENGGUNAKAN]->(Domain)`, `(User)-[MELAPORKAN]->(Lowongan)`.
*   [ ] **Neo4j Ingestion Agent:**
    *   Buat handler asinkron di backend untuk menulis data ke Neo4j setiap kali ada laporan baru dari user.
*   [ ] **Network Risk Scoring (PyG GNN - Opsional / Bertahap):**
    *   Jika nomor telepon *A* terhubung dengan PT fiktif *X* yang telah dilaporkan bahaya, maka nomor telepon *A* otomatis memiliki reputasi buruk di sistem.

### Langkah 6: Implementasi Background Workers & Scrapers
Jalankan crawler untuk memanen data awal (*seed data*) dan sinkronisasi database.
*   [ ] Gunakan **Celery & Redis** untuk menjadwalkan tugas latar belakang:
    *   **Scraper Loker:** Scrape berkas loker publik (LinkedIn/JobStreet) secara periodik.
    *   **Gov DB Sync:** Sinkronisasi berkala data AHU/OSS dengan database lokal backend.

### Langkah 7: Ekspos API Endpoint & Integrasi ke Frontend
Buka endpoint API FastAPI yang aman untuk dikonsumsi oleh Next.js Frontend dan WhatsApp Gateway.
*   [ ] `POST /api/v1/verify/text` -> Input teks mentah.
*   [ ] `POST /api/v1/verify/image` -> Input berkas gambar screenshot.
*   [ ] `GET /api/v1/dashboard/stats` -> Data visualisasi graf Neo4j untuk Dashboard admin/analis.

---

## 📈 Indikator Keberhasilan (Definition of Done)
1. Modul OCR & NER dapat mengekstrak PT dan No. HP dari screenshot gambar loker dalam waktu < 2 detik.
2. Modul OSINT berhasil melakukan pencarian secara paralel ke WHOIS, DNS, dan DB lokal.
3. Model Hermes LLM berhasil menghasilkan output analisis forensik berupa JSON valid tanpa terpotong atau error parsing.
4. Data laporan tersimpan secara otomatis dan terhubung di graf Neo4j.
