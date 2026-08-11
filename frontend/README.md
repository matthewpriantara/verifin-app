# 🎨 Verifin Frontend (Next.js 16)

UI Verifin — verifikasi lowongan kerja, lapor komunitas, dan dashboard admin.
Stack: Next.js 16 (App Router) · React 19 · TypeScript · Tailwind CSS 4 ·
motion/react · Phosphor Icons.

> **Catatan integritas:** visualisasi **Fraud Network Graph interaktif belum
> diimplementasikan** di frontend (belum memakai React Flow/D3). Halaman hasil
> menampilkan breakdown OSINT, kontribusi XAI (`ShapChart`), dan faktor risiko.
> Tidak ada infrastruktur unit test (Jest/Vitest) saat ini.

---

## 🚀 Menjalankan

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000 (hot-reload)
```

Build produksi: `npm run build` · serve: `npm start` · lint: `npm run lint`
(Tidak ada script `test` — proyek belum memiliki runner Jest/Vitest.)

### Environment (`frontend/.env.local`)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000   # base URL backend (tanpa trailing slash)

# Admin panel (hanya server-side, tanpa prefix NEXT_PUBLIC_)
ADMIN_PASSWORD=verifin2026                 # ganti di produksi!
ADMIN_SESSION_SECRET=verifin-admin-secret-change-me
```

---

## 🗂️ Halaman

| Route | Modul | Catatan |
| :--- | :--- | :--- |
| `/` | `modules/home/HomePage` | Landing + VerifyBox (input teks/gambar/URL) |
| `/report` | `modules/report/ReportPage` | Hasil verifikasi (render dari sessionStorage) |
| `/report-job` | `modules/report-job/ReportJobPage` | Form lapor lowongan → `POST /community/report` |
| `/admin` | `modules/admin/AdminPage` | Riwayat kasus + moderasi laporan komunitas |
| `/verify` | — | redirect ke `/` |

Navigasi admin & lapor tersedia di footer.

---

## 🔌 Kontrak Backend

Semua panggilan API lewat `lib/api.ts` (verifikasi, status, community) dan
`lib/admin.ts` (riwayat kasus):

- `POST /api/v1/verify/text` · `POST /api/v1/verify/image` · `POST /api/v1/verify/url`
- `GET /api/v1/verify/status`
- `GET /api/v1/cases`
- `POST /api/v1/community/report`
- `GET /api/v1/community/reports`
- `PATCH /api/v1/community/reports/{id}`

Tipe kontrak di `types/verify.ts` & `types/admin.ts` — sinkron dengan schema
Pydantic backend. `osint.timing.ocr` (latency OCR) dan `persistence_status`
ditampilkan di report.

---

## 🔐 Admin

Login via Next.js API route (`app/api/admin/*`) — password dari env
`ADMIN_PASSWORD`, sesi cookie httpOnly 8 jam. **Backend tidak punya konsep role**;
endpoint `/cases` dan `/community/reports` bersifat publik (data moderasi
sebaiknya dilindungi reverse-proxy/auth bila dideploy publik).
