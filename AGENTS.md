# Verifin App — Codebase Guidelines, Architecture & Deployment SOP

Full-stack codebase untuk **Verifin: Platform Deteksi Lowongan Kerja Palsu Berbasis AI & OSINT**.
Repositori ini mengintegrasikan FastAPI (backend), Next.js 16 (frontend), LLM Gemini 3.8 Flash (utama) dengan cadangan on-premise Gemma 4 di GPU RTX 5080 VPS, multi-channel OSINT probes, dan automated failover.

---

## 1. Hubungan Antar-Workspace & Repositori

| Path Folder | Peran & Lingkungan | Remote / Target |
| :--- | :--- | :--- |
| `../gemastik19` | Dokumen lomba, proposal, materi finalis | `hafidzrizqullahprasetya/gemastik19` (`main`) |
| `verifin-app` (local) | Codebase lokal pengerjaan di macOS | `matthewpriantara/verifin-app` (`main`) |
| `verifin-app-server` | Clone lokal yang melacak repo VPS Produksi (`praktikum-beta`), remote `vps` | `praktikan@100.118.206.100:/home/praktikan/projects/verifin` |
| `verifin-app-home` | Clone lokal yang melacak repo Home Server (`fizualinux`), remote `home` | `hafidzprasetya@100.82.95.50:/home/hafidzprasetya/Project/verifin-app` |

`verifin-app-server` dan `verifin-app-home` **bukan mount live**. Keduanya clone git biasa dengan upstream `main` diarahkan ke remote SSH (Tailscale) masing-masing, jadi `git pull` / `git push` tanpa argumen langsung ke repo di server. Kedua repo server memakai `receive.denyCurrentBranch = updateInstead`, sehingga push langsung memperbarui working tree server. Yang tidak ikut git: `backend/.env` (di-ignore) dan status container; untuk itu tetap pakai SSH. Push hanya memperbarui kode; jalankan `./deploy.sh` di server agar aktif.

### Peta Dokumentasi AGENTS.md
- `backend/AGENTS.md`: Arsitektur FastAPI, struktur modul `backend/app/`, urutan pipeline verifikasi, konvensi status contract, aturan skema cache, perintah tes CI, dan variabel lingkungan backend.
- `frontend/AGENTS.md`: Panduan Next.js 16, pemetaan rute `frontend/src/app` ke `frontend/src/modules`, alur otentikasi admin, konsumsi API & SSE, perintah build/lint/typecheck, dan konfigurasi API URL.

### Peran Host
| Host | IP Tailscale | Isi |
| :--- | :--- | :--- |
| `praktikum-beta` (VPS kampus) | `100.118.206.100` | **Stack produksi** Verifin (backend, frontend, db, db-backup), **GPU RTX 5080 + Ollama** (`gemma4:12b-it-qat`, port `11434`). |
| `fizualinux` (Home Server) | `100.82.95.50` | **Cloudflare Tunnel** (`cloudflared`, dua token), **SearXNG** (`searxng-core`, `searxng-valkey`), container `octane-ai` / `octane-app`, dan **stack Verifin cadangan** (tidak melayani publik). Tidak ada GPU maupun Ollama. |

---

## 2. Topologi Jaringan, Port Resmi & Domain Publik

### Port Resmi Layanan
Untuk mencegah tabrakan port (*port collision*) dengan layanan lain di host server, port resmi yang digunakan adalah:
- **Backend API (FastAPI):** Port `8019` (internal container `:8000`)
- **Frontend (Next.js):** Port `3019` (internal container `:3000`)
- **Database (PostgreSQL 17):** Port `5433` (internal container `:5432`)
- **LLM Engine (Ollama):** Port `11434` (khusus Tailscale/localhost, TIDAK dibuka publik)
- **Web Search Engine (SearXNG):** Port `8888` / `https://search.hafidzprasetya.web.id`

### Arsitektur Edge Gateway (Cloudflare Tunnel via Tailscale)
- **Domain Publik:** `https://verifin.web.id` & `https://api.verifin.web.id`
- **Edge Ingress:** Tunnel `hafidz-server` berjalan di **Home Server (`fizualinux`)** karena jaringan kampus VPS (`praktikum-beta`) memblokir outbound port `7844` yang diwajibkan Cloudflare Tunnel.
- **Routing:** Cloudflare Tunnel di `fizualinux` meneruskan traffic publik melalui jaringan mesh **Tailscale** langsung ke VPS:
  - `verifin.web.id` $\rightarrow$ `http://100.118.206.100:3019` (Frontend Next.js di VPS)
  - `api.verifin.web.id` $\rightarrow$ `http://100.118.206.100:8019` (Backend FastAPI di VPS)
- **Keamanan Ollama:** Port `11434` **DILARANG** diekspos ke Cloudflare karena tidak memiliki otentikasi. Backend di VPS memanggil Ollama lewat `http://100.118.206.100:11434/v1`. Per 27 Okt 2026 Ollama mendengarkan di semua interface (`*:11434`), bukan hanya Tailscale; batasi ke IP Tailscale atau firewall bila jaringan kampus bisa menjangkaunya. Service `cloudflared` di VPS `praktikum-beta` dinonaktifkan (`disabled`).

---

## 3. Stack & Komponen Sistem

- **Backend:** FastAPI (Python 3.11), SQLAlchemy, PostgreSQL 17 Alpine, NetworkX (Fraud Graph), XAI atribusi bukti aditif berbobot poin (bukan pustaka SHAP, walau berkasnya bernama `backend/app/services/xai/shap_explainer.py`), PaddleOCR (OCR).
- **Frontend:** Next.js 16 (React 19, App Router, TypeScript), Tailwind CSS v4, Motion, Phosphor Icons.
- **Database:** Self-hosted PostgreSQL 17 (`verifin-db`) dengan automated daily backup (`verifin-db-backup`). Semua jejak Supabase cloud telah dihapus total.
- **LLM Provider Utama:** Octane AI Cloud (`https://api.octane.web.id/v1`), `ag/gemini-3.8-flash-medium` untuk penalaran dan `ag/gemini-3.8-flash-low` untuk ekstraksi entitas. Angka uji 14 lowongan (run 9 dan run 11 di `test/okt-2026/README.md`) dihasilkan model ini.
- **LLM Provider Cadangan (Failover Otomatis):** On-premise `gemma4:12b-it-qat` (Ollama di GPU RTX 5080 16GB pada VPS, `OLLAMA_KEEP_ALIVE=-1` pinned di VRAM). Otomatis aktif jika Gemini gagal/timeout.
- **Thinking Gemma 4:** Gemma 4 berpikir dulu secara default, jawabannya masuk ke `reasoning_content` dan `content` kosong, sehingga penalaran jatuh ke Rule-Based Fallback. Wajib `LLM_FALLBACK_REASONING_EFFORT=none` (atau `LLM_REASONING_EFFORT=none` bila Gemma dijadikan utama). Uji Gemma sebagai utama (run 10): T9 lowongan asli dinilai WASPADA 70; lihat README uji.
- **Cache Verifikasi:** `VERIFY_CACHE_ENABLED=true` di produksi. Set `false` sementara saat uji ulang agar setiap kasus dihitung ulang, lalu kembalikan. Hash cache memuat nama model, jadi mengganti `LLM_MODEL` otomatis membuat cache baru. Hasil Rule-Based Fallback tidak pernah dipakai ulang dari cache.

---

## 4. Alur Pipeline Verifikasi (`/api/v1/verify/`)

1. **Ingestion & Text Extraction:**
   - Text direct (`/verify/text`), Image OCR (`/verify/image` via `backend/app/services/ocr.py`), URL scraping (`/verify/url` dan SSE stream `/verify/url/stream` via `backend/app/services/web_fetcher.py`), seluruhnya dengan prefix `/api/v1` (`/api/v1/verify/text`, `/api/v1/verify/image`, `/api/v1/verify/url`, `/api/v1/verify/url/stream`).
   - `/api/v1/verify/image` menerima satu atau beberapa gambar (field `files`, maks 5) sebagai SATU lowongan; frontend menanyakan lebih dulu apakah gambar-gambar itu satu lowongan. Teks yang diisi bersamaan dikirim sebagai konteks tambahan.
   - Gambar dibaca OCR dan model vision (`backend/app/services/llm/vision.py`, `LLM_VISION_MODEL`, default = model ekstraksi) bersamaan. Bacaan vision ditempel setelah penanda `[PEMBACAAN AI DARI GAMBAR]`; kontak (nomor, email, URL) hanya dipakai bila juga terbaca OCR/regex, sisanya dicatat sebagai `ai_only_contacts`. Gemma 4 QAT di Ollama tidak menerima gambar, jadi vision punya penyedia sendiri (`LLM_VISION_BASE_URL`, `LLM_VISION_API_KEY`, `LLM_VISION_MODEL`) yang di produksi dan home dikunci ke Gemini Octane; saat penalaran pindah ke Gemma, vision tetap ke Gemini. Bila penyedia vision gagal, OCR saja yang dipakai.
   - OCR berjalan di satu thread khusus dan diulang sekali bila oneDNN melempar `std::exception`.
2. **Hybrid NER:**
   - Heuristik regex + ekstraksi LLM (`backend/app/services/ner.py` & `backend/app/services/llm/entity_extraction.py`).
   - Normalisasi nomor telepon (+62) dan sanitasi domain/email.
3. **Memeriksa Isi (`backend/app/services/precheck.py`):** sebelum OSINT. Berhenti dengan respons `verdict="PERLU_INPUT"` + `needs_input` (SSE: event `needs_input`) bila input bukan lowongan (I-01), terlalu pendek (I-03), atau berisi beberapa pemberi kerja dengan kontak berbeda (I-04, dipotong per lowongan). Frontend menampilkan kartu intervensi di modal loading, lalu memanggil `/api/v1/verify/text` dengan `intervention=segment|force`. Hasil `force` ditandai `input_quality="forced"` dan dikecualikan dari graf penipuan, `/cari`, dan cache. Klasifikasinya ikut panggilan ekstraksi entitas LLM (`entities["_content"]`), tanpa panggilan AI tambahan.
4. **Multi-Channel OSINT Probes (`backend/app/services/osint/runner.py`):**
   - Telepon: Sumber data di kode adalah Kaspersky Who Calls (`"source": "kaspersky"` di `backend/app/services/osint/phone_validator.py` via `https://whocalls.id.kaspersky.com`) dengan fallback pencarian SERP publik laporan penipuan; nama fungsi `check_phone_kredibel` / `*_kredibel` hanya nama fungsi lama di kode. Ditambah GetContact lewat layanan `getcontact-api` di home (`backend/app/services/osint/getcontact.py`, `GETCONTACT_URL`). GetContact memberi jumlah tag dan label spam; untuk paling banyak 1 nomor/hari (nomor 1–99 tag + teks berisiko) isi tag dibaca di layanan home dan yang keluar hanya hitungan kata penipuan. Nama pemilik dan teks tag tidak pernah disimpan atau dikembalikan. Kosongkan `GETCONTACT_URL` untuk mematikan. Kuota `search` 300/bulan (10 baru/hari + cache 14 hari), `numberDetail` 40/bulan; captcha diselesaikan manual (`python3 ~/Project/getcontact-cli/gtc.py captcha`). Produksi memanggilnya lewat reverse SSH tunnel home→VPS yang berakhir di unix socket (`GETCONTACT_UDS`), lihat `infra/getcontact-api/README.md`.
   - Jenis situs (email gratisan, pemendek URL, marketplace, portal loker, domain bebas daftar) hanya di `backend/app/data/site_kinds.json`; domain resmi pemberi kerja yang sudah diverifikasi di `backend/app/data/employer_domains.json`. Jangan menulis daftar host di kode; tes `test_no_host_lists_left_in_code` akan gagal.
   - Legalitas: Profil perusahaan & AHU/Pemerintah via SearXNG (`backend/app/services/osint/company_validator.py`)
   - Domain & Email: WHOIS/RDAP, usia domain, SPF/DKIM/MX (`backend/app/services/osint/whois_handler.py`)
   - Google Forms: Deteksi formulir rekrutmen mencurigakan (`backend/app/services/osint/gform_inspector.py`)
   - Lokasi: OpenStreetMap geocoding via Nominatim (`backend/app/services/osint/address_validator.py`)
5. **Graph & Explainable AI (XAI):**
   - Korelasi graf penipuan heterogen (`backend/app/services/graph/fraud_network.py`).
   - Atribusi kontribusi bukti + waterfall (`backend/app/services/xai/shap_explainer.py`): skor dari LLM, nilai dasar 12, bobot poin tetap, selisih = "Penyesuaian Penalaran AI".
   - Sinyal teks tambahan: lamaran lewat Telegram (`has_telegram_apply`, aturan pengaman minimal WASPADA 55), domain bebas daftar atas nama badan usaha, isi website berpola penipuan tugas/komisi, lokasi profil publik berbeda dari alamat poster.
6. **LLM Synthesis & Scoring Verdict:**
   - Multi-factor synthesis reasoning prompt (`backend/app/services/llm/verifin_reasoning.py`).
   - Klasifikasi verdict: `AMAN` (0–39), `WASPADA` (40–74), `BAHAYA` (75–100), sesuai `backend/app/services/constants.py`.
   - Real-time stage updates dikirim ke frontend via Server-Sent Events (SSE).

---

## 5. Fitur Lain

1. **Laporan Komunitas & Moderasi Admin:** Publik dapat melaporkan indikasi lowongan palsu beserta bukti via `POST /api/v1/community/report` (`frontend/src/modules/report-job/`, `backend/app/api/v1/community/`), memeriksa agregasi laporan entitas via `GET /api/v1/community/check`, dan admin memoderasi laporan (approve/reject) via antarmuka `frontend/src/modules/admin/` melalui server proxy `frontend/src/app/api/admin/` (`GET /api/v1/community/reports`, `PATCH /api/v1/community/reports/{report_id}`). Laporan yang disetujui otomatis disinkronkan ke kasus tersimpan dan memperbarui atribusi risiko XAI tanpa perlu verifikasi ulang (`backend/app/services/community_refresh.py`).
2. **Pencarian Kasus Publik:** Layanan pencarian riwayat lowongan yang telah diverifikasi pada halaman `/cari` (`frontend/src/modules/search/`, `frontend/src/app/cari/page.tsx`) melalui endpoint `GET /api/v1/cases/search` (`backend/app/services/case_search.py`), yang otomatis mengklasifikasikan tipe kueri (URL, telepon, email, nama perusahaan) serta mengembalikan ringkasan aman tanpa membocorkan teks mentah atau kontak personal.
3. **Keamanan & Privasi:** Masking data pribadi (nomor HP, NIK, nomor rekening/VA, local-part email) sebelum diteruskan ke LLM eksternal dan de-masking kembali pada hasil akhir (`backend/app/services/pii.py`), validasi URL publik serta pencegahan SSRF terhadap IP privat/loopback/metadata internal (`backend/app/services/url_guard.py`), dan otentikasi token admin dengan perbandingan constant-time serta pembatas laju (rate limiting) sliding-window berbasis IP (`backend/app/services/security.py`).

---

## 6. SOP Deployment & Sinkronisasi Kode (Best Practice)

### Standar Industri (Anti-Desync)
1. **Dilarang Deploy Buta dengan `:latest`:** Tag `:latest` bersifat ambigu. Gunakan Git SHA atau skrip deploy yang menginjeksi commit metadata.
2. **Wajib Tambahkan `--build`:** Jika menjalankan `docker compose`, selalu sertakan flag `--build` agar Docker meng-compile ulang file source code terbaru, bukan menjalankan image lama di cache.

### Frontend home vs produksi
`NEXT_PUBLIC_API_URL` dipanggang saat build. Produksi memakai nilai bawaan `https://api.verifin.web.id`. Home memakai `.env` di root repo (tidak di-commit) berisi `NEXT_PUBLIC_API_URL=` (kosong) dan `BACKEND_INTERNAL_URL=http://host.docker.internal:8000`, sehingga frontend home memanggil `/api/v1` di origin yang sama dan Next meneruskannya ke backend home. Tanpa `.env` itu, frontend home diam-diam menulis ke DB produksi.

### Perintah Deploy Standar (`deploy.sh`)
Gunakan skrip [`./deploy.sh`](./deploy.sh) di root repo:

```bash
# Opsi 1: Deploy dengan kode yang sudah ada di lokal server
./deploy.sh

# Opsi 2: Tarik commit terbaru dari GitHub lalu deploy otomatis (SOP Utama)
./deploy.sh --pull

# Opsi 3: Deploy service tertentu saja (misal hanya backend)
./deploy.sh verifin-backend
```

### Push Langsung via SSH Tailscale (Tanpa Lewat GitHub)
Jika koneksi internet kampus di VPS mengalami *TLS handshake reset* saat `git pull` dari GitHub, push langsung dari laptop:
```bash
# Dari verifin-app (remote eksplisit):
git -C verifin-app push praktikan@100.118.206.100:/home/praktikan/projects/verifin main
git -C verifin-app push hafidzprasetya@100.82.95.50:/home/hafidzprasetya/Project/verifin-app main

# Atau dari folder pelacak (upstream sudah diarahkan ke server):
git -C verifin-app-server pull   # tarik isi repo VPS
git -C verifin-app-home pull     # tarik isi repo Home
```
Lalu deploy di server terkait (`ssh ... 'cd <repo> && ./deploy.sh verifin-backend'`). Kedua repo server memakai `receive.denyCurrentBranch = updateInstead`.

---

## 7. SOP Pengecekan & Verifikasi Hasil Deploy

Setelah deploy, lakukan verifikasi melalui salah satu cara berikut:

1. **Cek Endpoint Publik Health:**
   Buka `https://api.verifin.web.id/api/v1/health`.
   Pastikan metadata berikut sesuai:
   - `"git_commit"`: Menampilkan short hash commit aktif (misal `"9e4bb31"`).
   - `"build_time"`: Waktu build UTC terbaru.
   - `"database"`: `{"postgres": "healthy"}`.
   - `"llm"`: `{"provider": "cloud", "target_model": "ag/gemini-3.8-flash-medium", "reachable": true}`.
2. **Cek Badge Footer Frontend:**
   Buka `https://verifin.web.id`. Pada footer bagian bawah tertulis nomor build `#<short-sha>`.
3. **Cek Waktu Build Container di Host:**
   ```bash
   docker inspect verifin-backend --format 'Built: {{.Created}}'
   ```
4. **Cek Baris Kode Spesifik di Dalam Container:**
   ```bash
   docker exec verifin-backend grep -n "NAMA_FUNGSI" app/path/file.py
   ```

---

## 8. Konvensi Kode & Keamanan

- **Status Contract:** Modul OSINT wajib mengembalikan status string baku dari `backend/app/services/status_contract.py` (`COMPLETED`, `FOUND`, `NO_RESULTS`, `UNAVAILABLE`, dsb).
- **Caching:** Cache verifikasi berbasis SHA-256 content hash di `backend/app/services/db_cache.py` & `backend/app/services/hasher.py`.
- **Admin Security:** Endpoint admin wajib dilindungi oleh `ADMIN_API_TOKEN` yang sama persis di `backend/.env` dan `frontend/.env`.
- **Git Isolation:** Setiap perubahan kode di repo aplikasi WAJIB diisolasi dengan flag `-C verifin-app`.

---

## 9. Perintah Pengujian & CI

Sesuai alur otomatisasi di `.github/workflows/test.yml`:

### Backend (Python 3.11)
- Instalasi paket OS (Ubuntu):
  ```bash
  sudo apt-get update && sudo apt-get install -y --no-install-recommends libgl1 libglib2.0-0
  ```
- Instalasi dependensi Python:
  ```bash
  pip install -r backend/requirements.txt pytest pytest-asyncio pytest-cov
  ```
- Jalankan pengujian unit & coverage (dari direktori `backend`):
  ```bash
  pytest -q --cov=app --cov-report=term --cov-report=xml
  ```
  *(Catatan CI: env `DATABASE_URL=""`, `LLM_API_KEY=""`, dan `ADMIN_API_TOKEN=""` diset kosong agar menguji jalur fallback/fail-closed).*

### Frontend (Node.js 22 & pnpm)
- Instalasi dependensi (dari direktori `frontend`):
  ```bash
  pnpm install --frozen-lockfile
  ```
- Pemeriksaan tipe TypeScript:
  ```bash
  pnpm exec tsc --noEmit
  ```
- Linter kode ESLint:
  ```bash
  pnpm lint
  ```
- Kompilasi build produksi Next.js:
  ```bash
  pnpm build
  ```
  *(Catatan CI: build dijalankan dengan `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`).*
