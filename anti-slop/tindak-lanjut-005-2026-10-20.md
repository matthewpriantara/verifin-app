# Tindak lanjut audit 005 (konsistensi tombol)

Tanggal: 20 Okt 2026. User menyetujui nomor 1–5. Nomor 6 (halaman admin) tidak disentuh.

| No | Status | Yang diubah |
|---|---|---|
| 1 | Selesai | Semua tombol utama di laporan, `/cari`, dan `/report-job` memakai `buttonClass()` dari `components/ui/Button.tsx`: `rounded-lg`, `h-11`, teks 14px, hover sama. Kolom cari ikut `rounded-lg` supaya serasi dengan tombol "Cari". |
| 2 | Selesai | `<Link><Button/></Link>` di laporan (aksi bawah dan tampilan "laporan tidak ditemukan") diganti `<Link className={buttonClass(...)}>`. Dicek: `document.querySelectorAll('a button').length` = 0. |
| 3 | Selesai | Google Maps = primary, OpenStreetMap = secondary. |
| 4 | Selesai | Label tombol jadi huruf kecil biasa: "Laporkan kasus ini", "Kembali ke laporan", "Kembali ke beranda", "Kirim laporan lain", "Kirim laporan". "Verifikasi Sekarang" sengaja tidak diubah karena tampil di screenshot Laporan Akhir dan video. |
| 5 | Selesai | Kartu laporan dan skeleton loading (`app/loading.tsx`, `report/[caseId]/loading.tsx`, `report-job/loading.tsx`) semuanya `rounded-2xl`. Modal di VerifyBox tetap `rounded-3xl` (jendela modal, bukan kartu). |

Verifikasi: `tsc` dan `eslint` bersih. Frontend lokal dengan API produksi, desktop 1280 dan HP 375: laporan T4 dan T10, `/cari`, `/report-job`; lebar gulir sama dengan lebar layar.

Catatan di luar audit: `/cari` menampilkan dua baris untuk PT Indokarya (AMAN 28 dan AMAN 20) dan Qhomemart (AMAN 15 dan AMAN 12). Teks OCR poster dan hasil ekstraksi tautan dari run berbeda menghasilkan hash berbeda. Belum dihapus; menunggu keputusan user.
