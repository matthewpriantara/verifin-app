# Panduan Implementasi Frontend - Verifin 🚀

Dokumen ini berisi panduan langkah demi langkah (step-by-step) yang terstruktur dan berurutan untuk mengembangkan bagian frontend dari platform **Verifin** (Platform Verifikasi Lowongan Kerja Berbasis Heterogeneous Graph, OCR, dan Explainable AI) menggunakan **Next.js (App Router), TypeScript, Tailwind CSS, dan Vis.js/React Flow**.

---

## 🗺️ Peta Aliran Halaman & Fitur Utama Frontend

Berikut adalah halaman-halaman yang harus diimplementasikan:
1. **Landing Page:** Edukasi publik, statistik penipuan, dan tombol Call to Action (CTA).
2. **Verification Portal (Dashboard Input):** Area untuk mengunggah screenshot loker (OCR), memasukkan teks loker (NER), dan form input manual parameter OSINT (No. HP, Domain/Email, Alamat).
3. **Result & Forensic Report:** Menampilkan *Risk Score*, verdict, penjelasan berbasis AI (Hermes LLM), rincian OSINT, grafik kontribusi fitur (SHAP), dan visualisasi jaringan 2D.
4. **Explorer/Analyst Dashboard:** Untuk melacak total sindikat penipuan yang terdeteksi dan menjelajahi graf hubungan antar-laporan secara global.

---

## 🛠️ Langkah-Langkah Implementasi Urut (Step-by-Step)

### 📌 Langkah 1: Setup Proyek & Environment
Mempersiapkan workspace frontend dengan standar Next.js modern, TypeScript, dan pustaka UI.
* **Inisialisasi Project:** Jalankan `npx create-next-app@latest frontend --typescript --tailwind --app --eslint` di root directory.
* **Integrasi UI Component Library:** Install **shadcn/ui** untuk mempercepat pembangunan komponen yang konsisten dan rapi.
  * Jalankan `npx shadcn-ui@latest init`
  * Install komponen yang dibutuhkan: `button`, `card`, `dialog`, `input`, `textarea`, `progress`, `tabs`, `toast`, `badge`.
* **Install Core Dependencies:**
  * Visualisasi Graf: `lucide-react` (ikon), `vis-network` / `reactflow` (visualisasi graf 2D).
  * Charts (XAI SHAP): `recharts` / `chart.js` (untuk visualisasi kontribusi fitur/SHAP).
  * State & API Fetching: `axios` / `swr` / `@tanstack/react-query` untuk integrasi API backend FastAPI.

---

### 📌 Langkah 2: Struktur Folder & Konfigurasi Dasar
Atur struktur folder Next.js agar mudah dimaintain.
* Pastikan struktur folder seperti berikut:
  ```text
  frontend/
  ├── src/
  │   ├── app/                 # Next.js App Router Pages
  │   │   ├── layout.tsx       # Main layout (Navbar, Footer)
  │   │   ├── page.tsx         # Landing Page
  │   │   ├── verify/
  │   │   │   └── page.tsx     # Portal input verifikasi
  │   │   ├── report/[id]/
  │   │   │   └── page.tsx     # Halaman hasil analisis detail
  │   │   └── dashboard/
  │   │       └── page.tsx     # Explorer dashboard untuk analis
  │   ├── components/          # Reusable UI Components
  │   │   ├── ui/              # shadcn/ui components
  │   │   ├── Graph2D.tsx      # Komponen visualisasi Neo4j Graph
  │   │   ├── ShapChart.tsx    # Komponen visualisasi SHAP Explainer
  │   │   └── FileUpload.tsx   # Dropzone untuk upload screenshot
  │   ├── hooks/               # Custom React hooks (e.g. useVerify)
  │   ├── lib/                 # Utility functions & API Clients
  │   └── types/               # TypeScript interfaces
  ```

---

### 📌 Langkah 3: Desain Landing Page (`src/app/page.tsx`)
Landing page harus berfokus pada kemudahan akses bagi pengguna awam dan menyajikan kredibilitas platform.
* **Hero Section:** Judul yang kuat ("Verifikasi Keaslian Lowongan Kerja Anda dalam Hitungan Detik"), deskripsi singkat, dan tombol CTA utama yang mengarah ke `/verify`.
* **Stats Section:** Tampilkan data visual fiktif/aktual tentang jumlah penipuan terdeteksi, total kerugian yang berhasil diselamatkan, dan PT terverifikasi.
* **How It Works Section:** Ilustrasi 3 langkah sederhana (Unggah/Tulis -> Sistem Melakukan OSINT & AI -> Laporan Risiko Keluar).
* **Footer:** Informasi tentang platform, disclaimer hukum, dan link ke organisasi keamanan siber / BP2MI.

---

### 📌 Langkah 4: Bangun Verification Portal (`src/app/verify/page.tsx`)
Halaman ini adalah pintu masuk utama input data dari pengguna.
* **Tab Navigation:** Sediakan 2 tab utama:
  1. **Unggah Screenshot (OCR):** Area drag-and-drop file gambar screenshot chat WhatsApp, Telegram, atau pamflet loker.
  2. **Teks & Info Manual (NER + OSINT):** Text area untuk menyalin isi loker beserta input field opsional (Nama PT, Nomor WhatsApp, Website/Email Pengirim, Alamat Kantor).
* **Upload State Handling:** Buat feedback visual yang jelas saat proses upload sedang berlangsung (loading spinner, progress bar).
* **Real-time Processing Indicator:** Tampilkan animasi/stepper proses backend yang sedang berjalan:
  * 🔲 Ekstraksi Teks (PaddleOCR)
  * 🔲 Identifikasi Entitas (IndoBERT NER)
  * 🔲 Investigasi Otomatis (OSINT Harvester)
  * 🔲 Analisis Keaslian (Reasoning LLM)
  * 🔲 Finalisasi Laporan

---

### 📌 Langkah 5: Halaman Laporan Hasil Analisis (`src/app/report/[id]/page.tsx`)
Halaman ini menyajikan hasil analisis forensik secara mendalam namun tetap mudah dipahami pengguna awam.
* **Risk Meter (Gauge Chart):** Visualisasi melingkar atau bar horizontal berwarna gradasi dari Hijau (Aman), Kuning (Waspada), hingga Merah (Bahaya) yang menampilkan *Risk Score* (0-100%).
* **Verdict & AI Summary:** Kotak khusus berisi kesimpulan utama (misal: "BAHAYA - Terindikasi Penipuan Loker Palsu") disertai ringkasan penjelasan dari Hermes LLM dalam bahasa manusia yang kasual namun tegas.
* **Forensic Breakdown (Hasil OSINT):**
  * **Status Hukum:** Apakah PT terdaftar di database lokal AHU/OSS? (Status: Terdaftar / Tidak Terdaftar).
  * **Reputasi Kontak:** Hasil tracking nomor HP (tag GetContact).
  * **Umur & Keamanan Domain:** Umur domain email (WHOIS) dan status verifikasi SPF/DMARC (untuk mendeteksi phishing).
  * **Validitas Lokasi:** Hasil cek koordinat alamat kantor (apakah ruko kosong/tanah kosong).
* **SHAP Explainer (Explainable AI):** Bagan batang horizontal (`Recharts`) yang menggambarkan fitur mana saja yang paling berkontribusi menaikkan skor risiko (misal: "Domain email baru < 30 hari" menambah +40 risiko).

---

### 📌 Langkah 6: Visualisasi Jaringan Hubungan Jaringan (`src/components/Graph2D.tsx`)
Membantu pengguna melihat jika entitas (No. HP/Domain/PT) terhubung dengan jaringan penipuan lain yang pernah dilaporkan.
* **Integrasi Vis.js / React Flow:** Rancang grafik node-relasional sederhana.
* **Simpul (Nodes):** Bedakan warna node berdasarkan tipe entitas (Perusahaan = Biru, Nomor Telepon = Hijau, Tautan = Orange, Laporan Scam = Merah).
* **Sisi (Edges):** Hubungkan node dengan relasi berarah seperti `MELAPORKAN`, `MENGGUNAKAN`, atau `BERALAMAT_DI`.
* **Interaktivitas:** Buat node dapat diklik untuk memunculkan modal informasi detail relasi entitas tersebut.

---

### 📌 Langkah 7: Hubungkan API Backend (FastAPI Integration)
Sambungkan interaksi user ke backend agar dinamis.
* Buat file `src/lib/api.ts` yang mendefinisikan *endpoint call*:
  * `verifyText(payload: TextVerifyPayload)`
  * `verifyImage(file: File)`
  * `getReportDetail(id: string)`
  * `getDashboardStats()`
* Terapkan manajemen error yang baik: jika backend timeout (karena LLM lokal atau scrapers memakan waktu), tampilkan pesan ramah kepada user dan tawarkan opsi *retry*.

---

### 📌 Langkah 8: Dashboard Analis & Global Graph Explorer (`src/app/dashboard/page.tsx`)
Halaman opsional untuk menampilkan demo kapabilitas sistem secara keseluruhan.
* **Global Network Graph:** Tampilkan peta relasi besar dari seluruh laporan penipuan yang masuk ke sistem untuk melihat kluster sindikat penipuan terbesar.
* **Tabel Laporan Terbaru:** Daftar antrean laporan masuk, status verifikasi, dan skor risiko yang dapat difilter berdasarkan status (Aman, Waspada, Bahaya).
* **Monitor Agen:** Status keaktifan 5 Autonomous Agents (Job Portal Scraper, Gov DB Sync, WA Monitor, dll).

---

## 📈 Indikator Kesiapan Frontend (Definition of Done)
1. [ ] Responsif (Mobile-friendly) karena sebagian besar korban membuka penawaran loker lewat HP/WhatsApp.
2. [ ] Kecepatan muat halaman hasil dioptimalkan dengan loading skeleton.
3. [ ] Visualisasi graf Neo4j 2D berjalan lancar tanpa membuat browser lag/hang.
4. [ ] Penjelasan SHAP (XAI) tersaji dengan visualisasi chart yang mudah dicerna dalam sekali lihat.
