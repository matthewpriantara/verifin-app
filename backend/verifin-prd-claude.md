# Product Requirement Document (PRD)
# Verifin — Sistem Deteksi & Verifikasi Penipuan Lowongan Kerja Berbasis AI

**Tim:** Check IN — Universitas Gadjah Mada
**Kompetisi:** GEMASTIK XIX (2026) — Divisi Pengembangan Perangkat Lunak
**Versi Dokumen:** v3.0 (Full-Stack, turunan dari `prd-summary-v2.md`)
**Status:** Draft untuk referensi pengembangan `verifin-app`

---

## Daftar Isi

1. Pendahuluan
2. Ringkasan Produk
3. Tujuan & Sasaran Proyek
4. Ruang Lingkup (Scope)
5. Persona Pengguna & User Stories
6. Arsitektur Sistem
7. Spesifikasi Fungsional — Backend & AI Engine
8. Spesifikasi Fungsional — Website (Frontend)
9. Skema Data & Kontrak API
10. Zero-Cost Technology Stack
11. Non-Functional Requirements
12. Keamanan & Privasi Data
13. Metrik Keberhasilan & Kriteria Evaluasi
14. Roadmap & Milestone Pengembangan
15. Risiko & Mitigasi
16. Lampiran

---

## 1. Pendahuluan

### 1.1 Latar Belakang

Penipuan berkedok lowongan kerja (*job scam*) merupakan salah satu modus penipuan daring yang paling masif di Indonesia. Modusnya berkembang dari pesan berantai WhatsApp, unggahan poster di media sosial, hingga situs *phishing* yang meniru portal loker resmi. Korban umumnya kesulitan memverifikasi keaslian sebuah tawaran kerja karena keterbatasan akses ke basis data resmi (AHU Kemenkumham), keterbatasan waktu, dan minimnya literasi digital untuk melakukan investigasi OSINT (*Open Source Intelligence*) secara mandiri.

**Verifin** hadir sebagai *anti-fraud detection engine* yang mengotomasi proses investigasi tersebut: pengguna cukup mengunggah tangkapan layar atau menempel teks lowongan kerja, dan sistem akan mengembalikan vonis (*verdict*) beserta penjelasan yang dapat dipertanggungjawabkan (*explainable*) dalam hitungan detik.

### 1.2 Tujuan Dokumen

Dokumen ini merupakan pengembangan penuh (*full-stack expansion*) dari `prd-summary-v2.md`, yang sebelumnya berfokus pada arsitektur backend dan *Case Memory*. PRD ini melengkapi cakupan tersebut dengan:

* Spesifikasi produk dari sisi bisnis dan pengguna (persona, user story, sasaran kompetisi).
* Spesifikasi **website/frontend** secara menyeluruh — sitemap, user flow, komponen UI, dan integrasi visualisasi graph — yang belum dibahas pada dokumen v2.
* Kontrak API antara frontend dan backend agar tim dapat bekerja paralel (*parallel development*).
* Kriteria keberhasilan yang diselaraskan dengan rubrik penilaian GEMASTIK XIX Divisi Pengembangan Perangkat Lunak.

Dokumen ini menjadi **rujukan tunggal (single source of truth)** bagi tim Check IN maupun AI coding assistant dalam membangun `verifin-app`.

### 1.3 Definisi & Istilah

| Istilah | Definisi |
|---|---|
| OSINT | *Open Source Intelligence*, investigasi menggunakan sumber data publik (Nominatim, Overpass, WHOIS, DNS). |
| Case Memory | Mekanisme sistem untuk "mengingat" kasus yang pernah dianalisis agar tidak perlu inferensi LLM ulang. |
| Verdict | Hasil vonis akhir sistem: `AMAN`, `WASPADA`, atau `BAHAYA`. |
| XAI | *Explainable AI*, penjelasan natural language atas keputusan model (berbasis SHAP). |
| NER | *Named Entity Recognition*, ekstraksi entitas (nama organisasi, lokasi, dsb) dari teks. |
| Sindikat | Kumpulan entitas (`Company`) berbeda yang terhubung ke kontak (`Phone`/`Email`) yang sama, terdeteksi via graph. |

---

## 2. Ringkasan Produk

### 2.1 Pernyataan Masalah (Problem Statement)

> Pencari kerja di Indonesia — terutama mahasiswa/fresh graduate — tidak memiliki cara cepat dan gratis untuk memverifikasi keabsahan sebuah lowongan kerja sebelum menyerahkan data pribadi atau membayar biaya administrasi palsu.

### 2.2 Solusi

Verifin adalah **web application** yang memungkinkan pengguna:

1. Mengunggah *screenshot* poster loker/chat rekruter, **atau** menempel teks lowongan secara langsung.
2. Menerima **vonis instan** (AMAN/WASPADA/BAHAYA) beserta skor risiko 0–100.
3. Melihat **penjelasan eksplainabel** (XAI) mengapa sistem memberi vonis tersebut — bukan sekadar *black box*.
4. Menjelajahi **peta jaringan (graph)** yang memperlihatkan apakah kontak pada loker tersebut terhubung ke sindikat penipuan lain yang pernah terdeteksi.
5. Melihat riwayat pengecekan pribadi dan berkontribusi pada basis pengetahuan komunitas (*crowdsourced case memory*).

### 2.3 Proposisi Nilai (Value Proposition)

| Untuk | Verifin memberikan |
|---|---|
| Pencari kerja / mahasiswa | Kepastian keamanan sebuah tawaran kerja dalam **< 15 detik**, gratis, tanpa perlu keahlian OSINT. |
| Komunitas | Peta visual sindikat penipuan yang terus bertumbuh secara kolektif (*network effect* dari Case Memory). |
| Institusi (kampus/pemerintah) | Dasbor agregat tren modus penipuan loker terbaru untuk keperluan edukasi & kebijakan publik. |

### 2.4 Diferensiator terhadap Solusi Sejenis

* Menggunakan **Graph Database** untuk mendeteksi pola sindikat lintas-postingan — bukan sekadar klasifikasi teks per-kasus.
* **Zero operational cost**: seluruh AI berjalan lokal (Ollama, IndoBERT, PaddleOCR), tidak bergantung API berbayar, sehingga dapat di-*deploy* berkelanjutan pasca-kompetisi tanpa beban biaya.
* **Explainable AI**: hasil bukan hanya label, tetapi disertai alasan berbasis kontribusi fitur (SHAP) yang diterjemahkan ke bahasa natural.

---

## 3. Tujuan & Sasaran Proyek

### 3.1 Tujuan Utama (mewarisi dari PRD v2, Bagian 1.A)

1. **Optimalisasi Kecepatan Pengguna** — cache hit < 100 ms, cache miss (inferensi baru) < 15 detik.
2. **Efisiensi Komputasi Lokal** — hindari pemanggilan LLM berulang untuk pola loker yang identik/mirip via Case Memory.
3. **Zero-Cost Operasional** — seluruh komponen open-source, tidak ada dependensi API berbayar.
4. **Dev & AI-Readable** — dokumentasi dan skema data konsisten agar mudah dipelihara oleh tim maupun AI coding assistant.

### 3.2 Tujuan Tambahan (Cakupan Produk & Kompetisi)

5. **Kejelasan Pengalaman Pengguna (UX Clarity)** — antarmuka harus dapat dipahami oleh pengguna awam (bukan hanya developer), mengingat target pengguna akhir adalah masyarakat umum/mahasiswa.
6. **Visual Storytelling melalui Graph** — visualisasi jaringan sindikat menjadi *unique selling point* saat demo juri, sehingga harus interaktif dan mudah dibaca dalam waktu presentasi terbatas.
7. **Kesiapan Demo (Demo-Readiness)** — sistem harus memiliki data seed yang cukup (lihat Bagian 7.E) agar graf tidak kosong saat dinilai juri.

### 3.3 Sasaran Terukur (Success Metrics)

Lihat detail lengkap pada **Bagian 13**.

---

## 4. Ruang Lingkup (Scope)

### 4.1 Dalam Cakupan (In-Scope — MVP untuk GEMASTIK XIX)

* Autentikasi pengguna dasar (email/password + opsi Google OAuth).
* Upload gambar (OCR) & input teks manual untuk verifikasi loker.
* Pipeline deteksi 3-level (Redis exact match → pgvector semantic match → LLM inference).
* Halaman hasil verifikasi dengan skor risiko, verdict, dan penjelasan XAI.
* Visualisasi graph interaktif (Vis.js/D3.js) untuk entitas terkait suatu kasus.
* Riwayat pengecekan pribadi pengguna (histori).
* Dasbor statistik agregat (jumlah kasus, tren verdict per waktu).
* Laporan komunitas (*community report*) — pengguna dapat menandai/melaporkan loker mencurigakan secara manual.

### 4.2 Luar Cakupan (Out-of-Scope untuk MVP)

* Aplikasi mobile native (iOS/Android) — cukup *responsive web*.
* Integrasi pembayaran atau model bisnis berbayar.
* Verifikasi otomatis dokumen resmi (KTP/NPWP) pelamar — di luar fokus anti-fraud loker.
* Multi-bahasa selain Bahasa Indonesia & Inggris dasar.
* Panel admin *full-fledged* dengan role-based access control kompleks (cukup admin sederhana untuk moderasi laporan komunitas).

### 4.3 Kandidat Pengembangan Lanjutan (Post-Competition Roadmap)

* Ekstensi browser untuk verifikasi langsung dari halaman portal loker.
* Integrasi bot WhatsApp/Telegram untuk verifikasi via chat.
* API publik agar portal loker resmi (mis. kampus) dapat mengintegrasikan Verifin sebagai *pre-screening*.

---

## 5. Persona Pengguna & User Stories

### 5.1 Persona

**Persona 1 — "Dinda", Mahasiswa Tingkat Akhir (Target Utama)**
* Usia 21–24 tahun, aktif mencari kerja paruh waktu/magang via media sosial.
* Pain point: sering menerima tawaran loker "kerja santai gaji besar" via WhatsApp, tidak yakin cara mengecek keasliannya.
* Kebutuhan: proses cepat, tidak ribet, cukup screenshot lalu tempel.

**Persona 2 — "Pak Broto", Orang Tua / Masyarakat Umum**
* Usia 45–55 tahun, literasi digital menengah.
* Pain point: anaknya atau dirinya sendiri menerima tawaran kerja mencurigakan, butuh validasi sebelum mengambil keputusan finansial (mis. transfer "biaya admin").
* Kebutuhan: antarmuka sederhana, bahasa hasil analisis mudah dipahami (bukan istilah teknis AI).

**Persona 3 — "Admin Verifikator" (Internal/Community Moderator)**
* Memantau laporan komunitas dan pola sindikat baru yang terdeteksi otomatis oleh graph engine.
* Kebutuhan: dasbor ringkas untuk meninjau *alert* sindikat (*degree* kontak > 1) dan memvalidasi data whitelist AHU.

### 5.2 User Stories Utama

| ID | Sebagai | Saya ingin | Sehingga |
|---|---|---|---|
| US-01 | Dinda | mengunggah screenshot poster loker | mendapat vonis keamanan tanpa mengetik ulang teks |
| US-02 | Dinda | menempel teks loker langsung | bisa cek cepat tanpa perlu screenshot |
| US-03 | Pengguna | melihat skor risiko & alasan dalam bahasa sederhana | memahami *mengapa* loker dinilai berbahaya |
| US-04 | Pengguna | melihat visualisasi graph entitas terkait | tahu apakah kontak ini pernah dipakai di loker penipuan lain |
| US-05 | Pengguna | melihat riwayat pengecekan saya sebelumnya | bisa membandingkan atau melapor ulang |
| US-06 | Pengguna | melaporkan loker yang menurut saya penipuan | membantu memperkaya basis data komunitas |
| Pak Broto | melihat hasil dalam bahasa non-teknis dengan indikator warna (hijau/kuning/merah) | cepat mengambil keputusan tanpa membaca detail teknis |
| US-08 | Admin Verifikator | melihat daftar *alert* sindikat otomatis | dapat memvalidasi dan menindaklanjuti pola penipuan terorganisir |
| US-09 | Pengguna | membagikan hasil verifikasi (link/gambar) | dapat memperingatkan teman/keluarga |

---

## 6. Arsitektur Sistem

Arsitektur inti **diwarisi penuh** dari `prd-summary-v2.md` (Hybrid Architecture: Real-Time Layer + Background Layer). Ringkasan:

### 6.1 Lapisan Real-Time (Synchronous)

```
Input (Gambar/Teks)
   → OCR & Extraction (PaddleOCR)
   → SHA-256 Hash
   → Redis Exact Match (Level 1, <2ms)
        ├─ HIT  → return cached verdict
        └─ MISS → Embedding (MiniLM-L12) → pgvector Semantic Match (Level 2, ≥95% cosine sim)
                ├─ HIT  → cache to Redis → return verdict
                └─ MISS → Live OSINT + NER → LLM Inference (Level 3, Hermes3)
                          → Simpan ke PostgreSQL + pgvector + Redis (TTL policy)
                          → Enqueue Celery task → Neo4j graph write (async)
                          → return verdict ke pengguna
```

### 6.2 Lapisan Background (Asynchronous — Celery + Redis Broker)

* Penulisan relasi entitas ke Neo4j (non-blocking terhadap respons user).
* Sinkronisasi mingguan whitelist AHU Kemenkumham.
* *Pattern learning scraper* dari portal loker publik (Glints, Jobstreet, Kalibrr) untuk data seed & benign training data.
* Pemindaian berkala pola sindikat (Cypher query *degree* kontak > 1) → memicu alert ke Admin Verifikator.

### 6.3 Diagram Alur Sistem

Diagram *mermaid* lengkap tersedia pada `prd-summary-v2.md` Bagian 2.A dan tetap berlaku tanpa perubahan pada v3 ini. Perbedaan pada v3 adalah **penambahan Presentation Layer (Website)** yang mengonsumsi seluruh endpoint dari Real-Time Layer di atas — lihat Bagian 8 & 9.

### 6.4 Arsitektur Tingkat Tinggi (High-Level, 3-Tier)

```
┌─────────────────────────┐
│   Presentation Layer     │  Next.js 16 (App Router) + TypeScript + Tailwind + Shadcn/ui
│   verifin-app (frontend) │  Vis.js / D3.js untuk graph visualization
└─────────────┬────────────┘
              │ REST / JSON (HTTPS)
┌─────────────▼────────────┐
│   Application Layer       │  FastAPI (async) — REST API + AI microservices orchestration
└─────────────┬────────────┘
              │
┌─────────────▼────────────────────────────────────────┐
│   Data & AI Layer                                       │
│   Redis (cache+broker) | PostgreSQL+pgvector | Neo4j     │
│   PaddleOCR | IndoBERT NER | Ollama(Hermes3) | PyG GNN   │
└───────────────────────────────────────────────────────┘
```

---

## 7. Spesifikasi Fungsional — Backend & AI Engine

*(Bagian ini merangkum & mengonsolidasikan `prd-summary-v2.md` Bagian 3, tanpa mengubah substansi teknis, sebagai konteks bagi tim frontend.)*

### 7.A Pipeline Pemrosesan Berkas & Teks
* OCR via **PaddleOCR PP-OCRv6**, maks 20MB, validasi resolusi ≤4000px, upscaling 2x (`cv2.INTER_CUBIC`) bila <800px.
* NER via **IndoBERT** (`cahya/bert-base-indonesian-NER`) untuk `ORG`/`LOC` + regex kustom untuk email, kontak (`+62` normalization), URL, dan nominal gaji.
* Cleanup logic: standarisasi prefiks badan usaha (PT/CV), filter kata benda umum, deduplikasi entitas alamat.

### 7.B Validasi OSINT & Proximity Match
* **Nominatim API** — geocoding alamat.
* **Overpass API** — proximity search radius 250m (exact) / 3000m (name search, similarity ≥55%).

### 7.C Analisis AI Heuristik & Vonis (Ollama/Hermes3)
* Dynamic prompting menggabungkan output NER + OSINT.
* Pembedaan kategori usaha: UMKM/Informal (skor 15–35, AMAN) vs Formal/PT-CV yang memakai email gratisan (skor 40–55, WASPADA).
* Konfigurasi determinasi: `temperature: 0.1`, `top_p: 0.9`.
* **Output JSON wajib** (selaras dengan Rule #2 project instructions):

```json
{
  "risk_score": 0,
  "verdict": "AMAN | WASPADA | BAHAYA",
  "corrected_company_name": "string",
  "summary": "string",
  "reasons": ["string", "..."],
  "risk_factors": ["string", "..."],
  "safe_factors": ["string", "..."],
  "recommendations": ["string", "..."],
  "explainable_ai": "string (penjelasan natural dari SHAP values)",
  "osint_failed": false
}
```

### 7.D Knowledge Graph (Neo4j)
* Node: `User`, `JobPost`, `Company`, `Phone`, `Email`, `Address`, `Tautan`.
* Relationship: `POSTED_BY`, `PROVIDES_CONTACT`, `PROVIDES_EMAIL`, `LOCATED_AT`.
* Deteksi sindikat: Cypher query mencari kontak dengan *degree* relasi > 1 → auto-flag "Sindikat Penipuan Loker Terorganisir".
* **Wajib**: nomor telepon/data sensitif di-hash **SHA-256 satu arah** sebelum masuk ke node graph (Rule #4).

### 7.E Background Intelligence Workers
* Sync mingguan whitelist AHU Kemenkumham → PostgreSQL.
* Scraper terjadwal (Playwright, async) untuk data seed loker fiktif & data benign guna menghindari *cold start* graf kosong saat demo (Rule #5).

*(Detail teknis lengkap — SLA, TTL policy Redis, fallback OSINT — tetap merujuk `prd-summary-v2.md` Bagian 2.B–2.C dan 3.)*

---

## 8. Spesifikasi Fungsional — Website (Frontend)

Bagian ini adalah **cakupan baru** yang melengkapi PRD v2, mendetailkan aplikasi web `verifin-app` yang dibangun dengan **Next.js 16 (App Router) + TypeScript + Tailwind CSS + Shadcn/ui**.

### 8.1 Sitemap / Struktur Halaman

| Route | Nama Halaman | Akses | Deskripsi Singkat |
|---|---|---|---|
| `/` | Landing Page | Publik | Value proposition, CTA "Cek Loker Sekarang", statistik agregat (jumlah kasus terdeteksi). |
| `/verify` | Halaman Verifikasi | Publik (guest boleh, riwayat perlu login) | Form upload gambar / paste teks. |
| `/verify/[caseId]` | Halaman Hasil Verifikasi | Publik | Verdict, skor risiko, XAI, graph mini-preview. |
| `/graph/[caseId]` | Graph Explorer | Publik | Visualisasi graph penuh (fullscreen, interaktif). |
| `/history` | Riwayat Saya | Login required | Daftar histori pengecekan pengguna. |
| `/dashboard` | Dasbor Statistik | Publik | Tren verdict, peta sebaran modus, jumlah sindikat terdeteksi. |
| `/report` | Lapor Komunitas | Login required | Form pelaporan manual loker mencurigakan. |
| `/login`, `/register` | Autentikasi | Publik | Email/password + Google OAuth. |
| `/admin` | Panel Verifikator | Role: admin | Daftar alert sindikat, moderasi laporan komunitas, sinkronisasi whitelist AHU. |
| `/about` | Tentang Verifin | Publik | Penjelasan tim, metodologi, disclaimer. |

### 8.2 User Flow Utama

**Flow A — Verifikasi Cepat (Guest, US-01/US-02)**
```
Landing Page → klik "Cek Loker Sekarang" → /verify
   → pilih mode: [Upload Gambar] atau [Tempel Teks]
   → submit → loading state (progress indicator level 1/2/3)
   → redirect ke /verify/[caseId] → tampilkan Verdict Card
   → opsi: [Lihat Graph Lengkap] / [Bagikan Hasil] / [Simpan ke Riwayat*]
      (*hanya jika login; jika guest, prompt login untuk simpan)
```

**Flow B — Eksplorasi Graph (US-04)**
```
/verify/[caseId] (mini-preview graph, 1-hop)
   → klik "Lihat Graph Lengkap" → /graph/[caseId] (fullscreen, multi-hop)
   → klik node Company/Phone/Email → panel detail sisi (side panel)
   → highlight jalur relasi ke kasus BAHAYA lain (jika ada)
```

**Flow C — Pelaporan Komunitas (US-06)**
```
Halaman Hasil / Dashboard → tombol "Laporkan sebagai Penipuan"
   → form konfirmasi (alasan, bukti tambahan opsional)
   → submit → masuk antrean moderasi Admin Verifikator
```

**Flow D — Admin Moderasi (US-08)**
```
/admin → tab "Alert Sindikat" (auto-generated dari Neo4j degree query)
   → tinjau detail graph → tombol [Validasi] / [Tolak]
   → tab "Laporan Komunitas" → tinjau laporan manual pengguna
```

### 8.3 Komponen UI Kunci (Shadcn/ui + Tailwind)

| Komponen | Deskripsi | Library Basis |
|---|---|---|
| `VerdictCard` | Kartu hasil dengan warna semantik (hijau/kuning/merah), skor risiko dalam bentuk gauge/progress ring | Shadcn `Card`, `Badge`, custom SVG gauge |
| `UploadDropzone` | Drag-and-drop gambar + preview + validasi ukuran (maks 20MB) di sisi klien sebelum upload | Shadcn `Input`, custom hook |
| `ProcessingStepper` | Indikator progres 3-level (Redis → pgvector → LLM) selama menunggu respons, agar UX tidak terasa "diam" saat inferensi berjalan hingga 15 detik | Shadcn `Progress`, custom stepper |
| `GraphCanvas` | Visualisasi graph interaktif (pan/zoom, klik node, highlight jalur) | Vis.js Network (rekomendasi utama untuk kecepatan implementasi) atau D3.js *force-directed graph* (untuk kontrol visual lebih detail) |
| `RiskFactorList` | Daftar `risk_factors` / `safe_factors` dengan ikon check/warning | Shadcn `Accordion`, `Alert` |
| `HistoryTable` | Tabel riwayat dengan filter verdict & tanggal | Shadcn `Table`, `DataTable` (tanstack table) |
| `StatChart` | Grafik tren verdict per waktu di dashboard | Recharts atau D3.js |
| `ReportDialog` | Modal form pelaporan komunitas | Shadcn `Dialog`, `Form` (react-hook-form + zod) |

### 8.4 Spesifikasi Detail: Graph Visualization (GraphCanvas)

Karena visualisasi jaringan sindikat adalah *unique selling point* Verifin, komponen ini memerlukan spesifikasi presisi:

* **Library:** Vis.js Network direkomendasikan untuk MVP kompetisi (kurva belajar lebih cepat, physics engine bawaan untuk *force-directed layout* otomatis). D3.js dapat dipertimbangkan sebagai *stretch goal* bila tim membutuhkan kustomisasi visual lebih dalam untuk sesi demo juri.
* **Encoding visual node:**
  * `JobPost` → bentuk persegi, warna sesuai verdict (hijau/kuning/merah).
  * `Company` → bentuk lingkaran, ukuran proporsional terhadap jumlah `JobPost` terkait.
  * `Phone`/`Email` → bentuk diamond; **diberi highlight merah tebal** otomatis jika *degree* > 1 (indikasi sindikat, selaras Rule #3 backend).
  * `Address` → bentuk pin/marker.
* **Interaksi:** klik node membuka side panel detail (data ter-hash untuk kontak sensitif — lihat Bagian 12); double-klik untuk *expand* relasi 1-hop tambahan (lazy loading dari API, hindari memuat seluruh graf sekaligus demi performa).
* **Data source:** endpoint `GET /api/v1/graph/{caseId}?depth=1` mengembalikan subset node & edge dalam format siap-konsumsi Vis.js (`{nodes: [...], edges: [...]}`).

### 8.5 Desain Sistem & Prinsip UI/UX

* **Design tokens:** gunakan skala warna semantik konsisten — `--verdict-safe` (hijau), `--verdict-warning` (kuning/oranye), `--verdict-danger` (merah) — didefinisikan sebagai CSS variable Tailwind agar dapat dipakai lintas komponen (termasuk di dalam SVG graph).
* **Aksesibilitas & bahasa awam:** mengingat Persona 2 (Pak Broto) memiliki literasi digital menengah, salinan (*copy*) hasil verifikasi wajib menghindari jargon AI (hindari istilah seperti "SHAP value" di UI utama — istilah teknis hanya muncul di tooltip/detail lanjutan).
* **Mobile-first & responsif:** mengingat mayoritas akses awal (screenshot loker WhatsApp) terjadi dari perangkat mobile, alur upload dan hasil verifikasi wajib dioptimalkan untuk layar kecil sebelum layar desktop.
* **Loading state yang jujur:** karena Level 3 (inferensi baru) bisa memakan waktu hingga 15 detik, `ProcessingStepper` wajib menampilkan progres bertahap (bukan spinner statis) agar pengguna tidak mengira aplikasi *hang*.

### 8.6 Manajemen State & Integrasi API (Frontend)

* **Data fetching:** gunakan React Server Components (Next.js App Router) untuk data non-interaktif (dashboard statistik publik), dan client-side fetching (`fetch`/`SWR`/`TanStack Query`) untuk alur interaktif (upload, polling status verifikasi).
* **Autentikasi:** session/JWT disimpan via `httpOnly` cookie (dikelola backend FastAPI) — hindari penyimpanan token sensitif di `localStorage` demi keamanan.
* **Validasi form:** `react-hook-form` + `zod` untuk validasi sisi klien sebelum permintaan dikirim ke backend (ukuran file, format email, dsb).

---

## 9. Skema Data & Kontrak API

### 9.1 Skema PostgreSQL (Ringkas)

| Tabel | Kolom Kunci | Catatan |
|---|---|---|
| `users` | id, email, password_hash, role, created_at | role: `user` \| `admin` |
| `job_cases` | id, raw_text_hash (SHA-256), embedding (`vector(384)`), verdict, risk_score, llm_output (JSONB), osint_failed, created_at | Sumber utama Level 2/3 lookup |
| `case_history` | id, user_id, job_case_id, created_at | Relasi many-to-many riwayat pengguna ↔ kasus |
| `community_reports` | id, user_id, job_case_id, reason, status (`pending`/`validated`/`rejected`), created_at | Flow C |
| `ahu_whitelist` | id, company_name, legal_type (PT/CV), synced_at | Hasil sync mingguan Celery |

### 9.2 Skema Neo4j

Mengikuti `prd-summary-v2.md` Bagian 3.D — node `JobPost`, `Company`, `Phone`, `Email`, `Address`, dengan seluruh nilai `Phone`/`Email` disimpan dalam bentuk **hash SHA-256** (bukan plaintext) sesuai Rule #4.

### 9.3 Kontrak API Utama (FastAPI ↔ Next.js)

| Method | Endpoint | Fungsi |
|---|---|---|
| `POST` | `/api/v1/verify/image` | Upload gambar (multipart) → OCR → pipeline verifikasi |
| `POST` | `/api/v1/verify/text` | Submit teks langsung → pipeline verifikasi |
| `GET` | `/api/v1/cases/{caseId}` | Detail hasil verifikasi (verdict, skor, XAI) |
| `GET` | `/api/v1/graph/{caseId}` | Subgraph entitas terkait (format nodes/edges Vis.js) |
| `GET` | `/api/v1/history` | Riwayat pengguna (login required) |
| `POST` | `/api/v1/reports` | Submit laporan komunitas |
| `GET` | `/api/v1/dashboard/stats` | Statistik agregat publik |
| `GET` | `/api/v1/admin/alerts` | Daftar alert sindikat (role: admin) |
| `POST` | `/api/v1/auth/login`, `/register` | Autentikasi |

*Catatan: seluruh endpoint verifikasi bersifat asinkron dari sisi UX (polling atau WebSocket opsional) mengingat Level 3 dapat memakan waktu hingga 15 detik — lihat Bagian 8.5.*

---

## 10. Zero-Cost Technology Stack

*(Diwarisi penuh dari `prd-summary-v2.md` Bagian 4, ditambah lapisan frontend.)*

### 10.A Frontend (Baru pada v3)
* **Next.js 16 (App Router)** — SSR/RSC untuk performa awal (First Contentful Paint) yang cepat, penting untuk kesan pertama juri saat demo.
* **TypeScript** — type-safety lintas kontrak API.
* **Tailwind CSS + Shadcn/ui** — konsistensi desain tanpa membangun design system dari nol, mempercepat *development velocity* selama masa kompetisi yang terbatas.
* **Vis.js / D3.js** — visualisasi graph (lihat Bagian 8.4).
* **TanStack Query / SWR** — caching & sinkronisasi data sisi klien, mengurangi *request* berulang ke backend (selaras filosofi efisiensi PRD v2).

### 10.B Backend & Database — *(reuse dari v2)*
FastAPI, Redis, PostgreSQL+pgvector, Neo4j Community Edition.

### 10.C Machine Learning & AI Lokal — *(reuse dari v2)*
Ollama (Hermes3-8B), Sentence-Transformers (MiniLM-L12-v2), PaddleOCR (PP-OCRv6), IndoBERT NER.

### 10.D Sumber Data OSINT Gratis — *(reuse dari v2)*
Nominatim, Overpass API, python-whois, dnspython.

---

## 11. Non-Functional Requirements

### 11.1 Performa & SLA — *(reuse dari v2 Bagian 5.A)*
* Redis exact match: < 50ms · pgvector semantic match: < 200ms · inferensi baru: < 15 detik.

### 11.2 Performa Frontend (Baru)
* **First Contentful Paint (FCP):** target < 1.8 detik pada koneksi 4G rata-rata Indonesia.
* **Lighthouse Performance Score:** target ≥ 85 untuk halaman `/` dan `/verify`.
* **Graph rendering:** subgraph awal (depth=1) harus dapat dirender < 1 detik untuk ≤ 50 node; graf lebih besar wajib menggunakan *lazy loading* (Bagian 8.4).

### 11.3 Konkurensi & Thread-Safety — *(reuse dari v2 Bagian 5.B)*
`threading.Lock()` pada modul PaddleOCR & IndoBERT NER untuk mencegah race condition.

### 11.4 Stabilitas Sumber Daya (OOM Prevention) — *(reuse dari v2 Bagian 5.C)*
Batas resolusi gambar 4000×4000px, `maxmemory` Redis untuk broker Celery.

### 11.5 Aksesibilitas
* Kontras warna verdict (hijau/kuning/merah) wajib memenuhi rasio WCAG AA minimum, dengan indikator tambahan berupa ikon/label teks (bukan warna semata) demi pengguna dengan gangguan penglihatan warna.

### 11.6 Kompatibilitas Browser
* Dukungan penuh untuk Chrome, Firefox, Edge, Safari versi 2 tahun terakhir; graph visualization wajib memiliki *fallback* pesan yang sopan bila WebGL/Canvas tidak didukung.

---

## 12. Keamanan & Privasi Data

*(Reuse penuh dari v2 Bagian 5.D, ditambah ketentuan khusus frontend.)*

* **Hashing satu arah SHA-256** wajib diterapkan pada nomor telepon/data sensitif sebelum masuk ke Neo4j (Rule #4) — termasuk saat data tersebut ditampilkan kembali di `GraphCanvas` (frontend **tidak pernah** menerima/menampilkan nomor telepon mentah dari kontak pihak ketiga, hanya versi ter-hash atau parsial-mask, mis. `0812****678`).
* Kredensial (PostgreSQL, Neo4j, Redis, API keys) disimpan di `.env`, di-*gitignore* secara ketat.
* Autentikasi sesi via `httpOnly` cookie, bukan `localStorage`.
* Docker Compose untuk portabilitas environment tim (`docker-compose up -d`).
* **Data pribadi pengunggah** (screenshot loker yang mungkin memuat data pengguna itu sendiri, mis. CV) disimpan dengan retensi terbatas dan tidak dipublikasikan ke graph publik tanpa anonimisasi.

---

## 13. Metrik Keberhasilan & Kriteria Evaluasi

### 13.1 Metrik Produk (Internal)

| Metrik | Target |
|---|---|
| Cache hit rate (Level 1+2) setelah seeding | ≥ 60% dari total request saat demo |
| Akurasi vonis (dibanding ground-truth dataset uji) | ≥ 80% pada tahap MVP |
| Waktu rata-rata end-to-end (cache miss) | < 15 detik |
| Jumlah node graph seed sebelum demo | ≥ 200 node lintas 5+ kasus sindikat simulasi |

### 13.2 Keselarasan dengan Rubrik GEMASTIK XIX (Indikatif)

| Aspek Penilaian (umum) | Bagaimana Verifin Menjawab |
|---|---|
| Inovasi & orisinalitas solusi | Kombinasi Case Memory hierarkis + Graph-based syndicate detection + XAI — bukan sekadar klasifikasi teks tunggal |
| Kelayakan teknis & implementasi | Arsitektur *zero-cost*, sepenuhnya dapat dijalankan lokal via Docker Compose, dapat didemokan tanpa API berbayar |
| Manfaat & dampak sosial | Menjawab masalah nyata & masif di Indonesia (penipuan loker), berpotensi diadopsi kampus/komunitas |
| Kualitas UI/UX & presentasi | Visualisasi graph interaktif sebagai *demo highlight*, bahasa hasil analisis ramah pengguna awam |
| Kelengkapan dokumentasi | PRD ini + dokumentasi teknis backend (v2) sebagai bukti proses rekayasa yang matang |

---

## 14. Roadmap & Milestone Pengembangan

*Catatan: sesuaikan tanggal aktual dengan jadwal resmi GEMASTIK XIX 2026 dari panitia.*

| Fase | Fokus | Output Kunci |
|---|---|---|
| **Fase 0 — Fondasi** | Setup Docker Compose (Postgres+pgvector, Redis, Neo4j), skeleton FastAPI & Next.js, skema DB | Environment tim berjalan lokal |
| **Fase 1 — Core Pipeline** | OCR + NER + hashing + Redis Level 1 match | Verifikasi teks dasar berjalan end-to-end (tanpa LLM dulu) |
| **Fase 2 — Semantic & LLM Layer** | pgvector Level 2, integrasi Ollama Hermes3, prompt engineering + JSON output | Vonis lengkap dengan skor & XAI |
| **Fase 3 — Frontend MVP** | Halaman `/verify`, `/verify/[caseId]`, komponen `VerdictCard`, `UploadDropzone` | Alur verifikasi end-user dapat didemokan |
| **Fase 4 — Graph & Visualisasi** | Neo4j writes async (Celery), endpoint graph, `GraphCanvas` (Vis.js) | Visualisasi sindikat interaktif |
| **Fase 5 — Seed Data & Cold Start Mitigation** | Playwright scraper, data fiktif seed, sinkronisasi whitelist AHU | Graf tidak kosong saat demo |
| **Fase 6 — Fitur Pendukung** | Riwayat, dashboard statistik, laporan komunitas, panel admin | Fitur lengkap sesuai in-scope MVP |
| **Fase 7 — Polish & Demo Prep** | Optimasi performa, aksesibilitas, skenario demo, video/dokumentasi submission | Submission GEMASTIK siap |

---

## 15. Risiko & Mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Inferensi LLM lokal terlalu lambat di perangkat demo (tanpa GPU memadai) | UX buruk saat demo langsung | Siapkan Case Memory ter-*seed* penuh agar mayoritas skenario demo hit di Level 1/2 (<200ms), hindari mengandalkan Level 3 saat presentasi langsung |
| Graf kosong/tidak menarik saat dinilai juri | Kehilangan *unique selling point* | Fase 5 wajib selesai sebelum Fase 7 — data seed sindikat fiktif representatif |
| OSINT API publik (Nominatim/Overpass/WHOIS) mengalami rate-limit saat demo | Analisis gagal sebagian | Soft fallback sudah dirancang di v2 (flag `osint_failed`); pastikan UI menampilkan disclaimer transparan, bukan error mentah |
| Kompleksitas stack (5+ teknologi database/AI) melebihi kapasitas waktu tim | Fitur tidak selesai tepat waktu | Prioritaskan MVP sesuai Bagian 4.1; fitur Bagian 4.3 ditunda pasca-kompetisi |
| False positive/negative pada vonis merugikan kredibilitas | Kepercayaan pengguna turun | Selalu sertakan `explainable_ai` agar pengguna dapat menilai sendiri, bukan hanya mempercayai label mentah |

---

## 16. Lampiran

### 16.1 Referensi Dokumen Terkait
* `prd-summary-v2.md` — spesifikasi backend & Case Memory (sumber utama Bagian 6, 7, 9, 10, 11, 12).

### 16.2 Glosarium Verdict
* **AMAN (skor 0–35):** tidak ditemukan indikator penipuan signifikan.
* **WASPADA (skor 36–65):** ditemukan beberapa indikator mencurigakan, disarankan verifikasi manual tambahan.
* **BAHAYA (skor 66–100):** indikator kuat penipuan (mis. kontak terhubung sindikat, alamat fiktif, permintaan biaya di muka).

### 16.3 Catatan untuk AI Coding Assistant
Saat mengimplementasikan fitur dari dokumen ini, ikuti Rules & Coding Standards proyek (pemisahan peran NER vs LLM, output JSON terstruktur wajib, Cypher optimal, hashing SHA-256 data sensitif, dan mitigasi cold start via seed scraper) sebagaimana didefinisikan di system context tim Check IN.

---

*Dokumen ini bersifat hidup (living document) dan akan diperbarui seiring iterasi pengembangan `verifin-app`.*