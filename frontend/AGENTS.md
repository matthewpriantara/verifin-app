# Frontend Verifin — Architecture, Routes & Guidelines

Dokumentasi teknis frontend Verifin (Next.js 16, React 19, TypeScript).

## 1. Stack & Dependensi (`package.json`)
- **Framework & Core:** Next.js 16.3.6 (App Router), React 19.3.0, React DOM 19.3.0, TypeScript 5.9.3.
- **Styling & Animasi:** Tailwind CSS v4 (`@tailwindcss/postcss`), Motion 13.4.4.
- **Ikon:** Phosphor Icons (`@phosphor-icons/react` 2.1.10).
- **Package Manager:** `pnpm@11.22.0`.

## 2. Peta Rute (`src/app/` $\rightarrow$ `src/modules/`)
- `src/app/page.tsx` (`/`) $\rightarrow$ `src/modules/home/HomePage.tsx`: Beranda, form input loker (teks/gambar/URL), modal proses verifikasi, dan riwayat lokal.
- `src/app/cari/page.tsx` (`/cari`) $\rightarrow$ `src/modules/search/SearchCasesPage.tsx`: Pencarian publik data kasus terverifikasi.
- `src/app/report-job/page.tsx` (`/report-job`) $\rightarrow$ `src/modules/report-job/ReportJobPage.tsx`: Formulir pengiriman laporan loker penipuan komunitas.
- `src/app/report/page.tsx` & `src/app/report/[caseId]/page.tsx` (`/report`, `/report/[caseId]`) $\rightarrow$ `src/modules/report/ReportPage.tsx`: Halaman rincian laporan hasil verifikasi loker.
- `src/app/admin/page.tsx` (`/admin`) $\rightarrow$ `src/modules/admin/AdminPage.tsx`: Dasbor moderasi admin (tinjau/setujui/tolak laporan komunitas).
- `src/app/privasi/page.tsx` (`/privasi`): Halaman statis kebijakan privasi dan transparansi data.
- `src/app/verify/page.tsx` (`/verify`): Rute pengalihan (redirect) otomatis ke `/`.
- `src/modules/verify/`: Komponen intervensi input, kartu bukti, dan progress tahap verifikasi.
- `src/modules/layout/`: Shell layout global (`src/modules/layout/Navbar.tsx`, `src/modules/layout/Footer.tsx`).

## 3. Alur Otentikasi Admin
- **Login Admin:** `src/app/api/admin/login/route.ts` memverifikasi `ADMIN_PASSWORD` dan menerbitkan cookie sesi `verifin_admin` bertanda tangan HMAC SHA-256 (`ADMIN_SESSION_SECRET` + hash password di `src/lib/adminAuth.ts`, kedaluwarsa 8 jam).
- **Proxy Server-Side:** Permintaan admin browser diarahkan ke `src/app/api/admin/proxy/[...path]/route.ts`. Handler memvalidasi cookie (`isAdminRequest`) lalu meneruskan request ke backend dengan menyuntikkan header `X-Admin-Token` dari `ADMIN_API_TOKEN`. Token backend tidak pernah terekspos ke bundle browser klien.

## 4. Konsumsi API & SSE
- Seluruh pemanggilan backend diatur melalui `src/lib/api.ts` (`verifyText`, `verifyImage`, `searchCases`, `verifyUrlStream`).
- `verifyUrlStream` (`POST /api/v1/verify/url/stream`) membaca stream `fetch` berbasis SSE, mem-parsing event `start`, `stage`, `needs_input`, `done`, dan `error` secara real-time.

## 5. Perintah Pengembangan & CI (sesuai `package.json` & CI)
- Jalankan server dev: `pnpm dev`
- Pengecekan tipe TypeScript: `pnpm exec tsc --noEmit`
- Linter kode: `pnpm lint`
- Build produksi: `pnpm build`

## 6. Catatan `NEXT_PUBLIC_API_URL`
- Nilai dipanggang ke output klien saat waktu build (`pnpm build`).
- **Produksi:** Menunjuk ke `https://api.verifin.web.id`.
- **Home Server:** Dikosongkan (`NEXT_PUBLIC_API_URL=`) bersama `BACKEND_INTERNAL_URL=http://host.docker.internal:8000` di `.env` root agar memanggil origin yang sama via reverse proxy.
- **CI / Tes Lokal:** Diset ke `http://127.0.0.1:8000`.
