# Verifin App — Codebase Guidelines, Architecture & Deployment SOP

Full-stack codebase untuk **Verifin: Platform Deteksi Lowongan Kerja Palsu Berbasis AI & OSINT**.
Repositori ini mengintegrasikan FastAPI (backend), Next.js 16 (frontend), on-premise LLM Gemma 4 di GPU RTX 5080, multi-channel OSINT probes, dan automated failover.

---

## 1. Hubungan Antar-Workspace & Repositori

| Path Folder | Peran & Lingkungan | Remote / Target |
| :--- | :--- | :--- |
| `../gemastik19` | Dokumen lomba, proposal, materi finalis | `hafidzrizqullahprasetya/gemastik19` (`main`) |
| `verifin-app` (local) | Codebase lokal pengerjaan di macOS | `matthewpriantara/verifin-app` (`main`) |
| `verifin-app-server` | Mirror live VPS Produksi (`praktikum-beta`) | `praktikan@100.118.206.100:/home/praktikan/projects/verifin` |
| `verifin-app-home` | Mirror live Home Server (`fizualinux`) | `hafidzprasetya@100.82.95.50:/home/hafidzprasetya/Project/verifin-app` |

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
- **Keamanan Ollama:** Port `11434` **DILARANG** diekspos ke Cloudflare karena tidak memiliki otentikasi. Backend di VPS memanggil Ollama secara internal. Service `cloudflared` di VPS `praktikum-beta` dinonaktifkan (`disabled`).

---

## 3. Stack & Komponen Sistem

- **Backend:** FastAPI (Python 3.11), SQLAlchemy, PostgreSQL 17 Alpine, NetworkX (Fraud Graph), SHAP (Explainable AI), PaddleOCR (OCR).
- **Frontend:** Next.js 16 (React 19, App Router, TypeScript), Tailwind CSS v4, Motion, Phosphor Icons.
- **Database:** Self-hosted PostgreSQL 17 (`verifin-db`) dengan automated daily backup (`verifin-db-backup`). Semua jejak Supabase cloud telah dihapus total.
- **LLM Provider Utama:** On-premise `gemma4:12b-it-qat` (Ollama di GPU RTX 5080 16GB, `OLLAMA_KEEP_ALIVE=-1` pinned di VRAM).
- **LLM Provider Cadangan (Failover Otomatis):** Octane AI Cloud (`https://api.octane.web.id/v1`, model `ag/gemini-3.8-flash-medium` & `low`). Otomatis aktif jika Ollama lokal down/timeout.

---

## 4. Alur Pipeline Verifikasi (`/api/v1/verify/`)

1. **Ingestion & Text Extraction:**
   - Text direct (`/text`), Image OCR (`/image` via `app.services.ocr`), URL scraping (`/url-stream` via `app.services.web_fetcher`).
2. **Hybrid NER:**
   - Heuristik regex + ekstraksi LLM (`app.services.ner` & `app.services.llm.entity_extraction`).
   - Normalisasi nomor telepon (+62) dan sanitasi domain/email.
3. **Multi-Channel OSINT Probes (`app.services.osint.runner`):**
   - Telepon: Whocalls / Kaspersky & Kredibel (`phone_validator.py`)
   - Legalitas: Profil perusahaan & AHU/Pemerintah via SearXNG (`company_validator.py`)
   - Domain & Email: WHOIS/RDAP, usia domain, SPF/DKIM/MX (`whois_handler.py`)
   - Google Forms: Deteksi formulir rekrutmen mencurigakan (`gform_inspector.py`)
   - Lokasi: OpenStreetMap geocoding via Nominatim (`address_validator.py`)
4. **Graph & Explainable AI (XAI):**
   - Korelasi graf penipuan heterogen (`app.services.graph.fraud_network`).
   - SHAP local explanation waterfall (`app.services.xai.shap_explainer`).
5. **LLM Synthesis & Scoring Verdict:**
   - Multi-factor synthesis reasoning prompt (`app.services.llm.verifin_reasoning`).
   - Klasifikasi verdict: `AMAN` (0–29), `WASPADA` (30–69), `BAHAYA` (70–100).
   - Real-time stage updates dikirim ke frontend via Server-Sent Events (SSE).

---

## 5. SOP Deployment & Sinkronisasi Kode (Best Practice)

### Standar Industri (Anti-Desync)
1. **Dilarang Deploy Buta dengan `:latest`:** Tag `:latest` bersifat ambigu. Gunakan Git SHA atau skrip deploy yang menginjeksi commit metadata.
2. **Wajib Tambahkan `--build`:** Jika menjalankan `docker compose`, selalu sertakan flag `--build` agar Docker meng-compile ulang file source code terbaru, bukan menjalankan image lama di cache.

### Perintah Deploy Standar (`deploy.sh`)
Gunakan skrip [`./deploy.sh`](file:///Users/fizualstd/Documents/GitHub/_LOMBA/verifin-app/deploy.sh) di root repo:

```bash
# Opsi 1: Deploy dengan kode yang sudah ada di lokal server
./deploy.sh

# Opsi 2: Tarik commit terbaru dari GitHub lalu deploy otomatis (SOP Utama)
./deploy.sh --pull

# Opsi 3: Deploy service tertentu saja (misal hanya backend)
./deploy.sh verifin-backend
```

### Bypass Jaringan Kampus (Push Langsung via SSH Tailscale)
Jika koneksi internet kampus di VPS mengalami *TLS handshake reset* saat `git pull` dari GitHub:
```bash
# Push langsung dari laptop Mac ke VPS (instan ~1 detik):
git -C verifin-app push praktikum-beta:/home/praktikan/projects/verifin main
```
*(Repo di VPS sudah dikonfigurasi `receive.denyCurrentBranch = updateInstead`)*.

---

## 6. SOP Pengecekan & Verifikasi Hasil Deploy

Setelah deploy, lakukan verifikasi melalui salah satu cara berikut:

1. **Cek Endpoint Publik Health:**
   Buka `https://api.verifin.web.id/api/v1/health`.
   Pastikan metadata berikut sesuai:
   - `"git_commit"`: Menampilkan short hash commit aktif (misal `"9e4bb31"`).
   - `"build_time"`: Waktu build UTC terbaru.
   - `"database"`: `{"postgres": "healthy"}`.
   - `"llm"`: `{"target_model": "gemma4:12b-it-qat", "reachable": true}`.
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

## 7. Konvensi Kode & Keamanan

- **Status Contract:** Modul OSINT wajib mengembalikan status string baku dari `app.services.status_contract` (`COMPLETED`, `FOUND`, `NO_RESULTS`, `UNAVAILABLE`, dsb).
- **Caching:** Cache verifikasi berbasis SHA-256 content hash di `app.services.db_cache` & `app.services.hasher`.
- **Admin Security:** Endpoint admin wajib dilindungi oleh `ADMIN_API_TOKEN` yang sama persis di `backend/.env` dan `frontend/.env`.
- **Git Isolation:** Setiap perubahan kode di repo aplikasi WAJIB diisolasi dengan flag `-C verifin-app`.
