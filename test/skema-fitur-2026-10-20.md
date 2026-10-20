# Skema uji semua fitur Verifin

Dipakai untuk uji produksi, latihan demo, dan pengecekan sebelum rekam video. Status per 20 Okt 2026 (`570583c`). Nomor di kolom "Bug" merujuk ke `anti-slop/audit-006-2026-10-20.md`.

Status:
- **OK**: sudah diuji dan sesuai harapan.
- **BUG**: sudah diuji dan terbukti salah.
- **BELUM**: belum diuji, dengan alasan di kolom keterangan.

## 1. Peta fitur

| Area | Fitur | Halaman / endpoint |
|---|---|---|
| Input | Teks, gambar poster (OCR), tautan postingan; progres real-time hanya untuk tautan (SSE) | `/` → `POST /verify/text`, `/verify/image`, `/verify/url/stream` |
| Proses | Batal (abort), shortcut ⌘/Ctrl+Enter, timer, pesan "sumber lambat" setelah 75 dtk | `VerifyBox` |
| Laporan | Verdict + skor, faktor penilaian, rekomendasi, perusahaan & lokasi (peta), reputasi kontak, jejak digital, kontribusi bukti (XAI), panel bukti OSINT, tombol lapor | `/report/{id}` → `GET /cases/{id}` |
| Riwayat lokal | Daftar kasus yang pernah dicek di browser ini (tanpa akun) | `SearchHistory` (localStorage) |
| Cari riwayat | Cari berdasarkan nama PT, nomor, email, atau link; hanya ringkasan | `/cari` → `GET /cases/search` |
| Komunitas | Kirim laporan + bukti gambar; daftar laporan yang disetujui | `/report-job` → `POST /community/report`, `GET /community/recent` |
| Admin | Login password, statistik kasus, grafik, moderasi laporan (setujui/tolak + catatan), logout | `/admin` → `/api/admin/login`, `/api/admin/proxy/*` |
| API | Dokumentasi otomatis | `api.verifin.web.id/docs` |

## 2. Skenario profil perusahaan

Inti pertanyaan "bagaimana kalau tidak ada kantor, cabang, dan lain-lain". Kolom "Seharusnya" adalah perilaku yang benar menurut prinsip Verifin. Hasil S1–S8 berasal dari uji lokal tanpa DB; kasus T, L, dan P berasal dari set uji nyata di produksi.

| # | Situasi lowongan | Contoh | Seharusnya | Hasil sekarang | Bug |
|---|---|---|---|---|---|
| P-01 | Kantor jelas, email domain sendiri, alamat lengkap | T10 Komitrando, T1 New Saphir | AMAN; peta tingkat jalan atau POI usaha | OK (AMAN 12) | — |
| P-02 | Cabang merek besar, alamat cabang, daftar ke domain resmi | S3 Indomaret Sleman | AMAN; titik peta di cabang atau ruas jalan, bukan POI lain | Verdict OK (AMAN 12), titik peta salah POI | 10, 18 |
| P-03 | Tidak ada kantor (remote/WFH), email gratisan | S1 | WASPADA ringan: identitas tidak bisa dicek | AMAN 25 karena jejak perusahaan lain ikut terhitung; nomor WA dibuang | 4, 31 |
| P-04 | Hanya kota penempatan, tanpa alamat | S4 "Jakarta, Bandung, Surabaya" | Tanpa titik peta; ditulis "lowongan tidak mencantumkan alamat" | Diisi POI usaha di kota itu (Depo KAI) | 11 |
| P-05 | Kerja di luar negeri | S6 Jepang | Peta tidak dipakai; sinyal "kerja luar negeri" | Verdict OK (BAHAYA 90), peta ke Desa Jepang, Kudus; sinyal luar negeri tidak menyala | 10, 38 |
| P-06 | Tidak menyebut nama perusahaan | S7, L2, T2 | WASPADA: identitas tidak bisa dicek | Verdict OK (WASPADA 50–58), tetapi nomor WA dibuang bila sebaris dengan kata "admin" | 31 |
| P-07 | Nama fiktif mirip perusahaan lain | S1, S2 | Tidak boleh memakai jejak perusahaan lain | BUG | 4 |
| P-08 | Mencatut BUMN/Tbk, daftar via WA atau link bio | T4, T8, S4 | WASPADA–BAHAYA; artikel bantahan tampil | OK (WASPADA 72–73); bantahan tidak punya baris XAI | 16 |
| P-09 | Minta biaya, perusahaan tanpa jejak web | S2 (bila pencarian kosong) | BAHAYA | Bisa dipaksa AMAN 28 | 5, 7 |
| P-10 | Minta biaya, nominal format Rp | T3, S6 | BAHAYA | OK (BAHAYA 90–95) | — |
| P-11 | Link Google Form / shortlink | T5–T7 | Form diinspeksi; form login dicatat netral | OK bila ditulis dengan `https://`; `bit.ly/…`, `forms.gle/…` tanpa skema tidak terbaca | 32 |
| P-12 | Link portal kerja (Glints, Jobstreet) | S5 | Diperlakukan sebagai portal, bukan formulir | Diinspeksi sebagai formulir | 9 |
| P-13 | Website resmi diblokir Cloudflare | S3 | Netral: "situs tidak bisa dicek otomatis" | Dihitung website aktif | 18 |
| P-14 | Nomor HR berbeda dengan kontak resmi | T1, P1 | Catatan netral | OK (tetapi "nomor resmi" diambil dari cuplikan mana pun) | 24 |
| P-15 | Nomor pernah dilaporkan komunitas (disetujui admin) | — | +20 "Dilaporkan komunitas", tampil di laporan, skor naik | Form tidak punya kolom nomor; pencocokan nomor rusak; tidak tampil; skor tidak berubah | 3, 34, 35, 36 |
| P-16 | Teks sama dikirim ulang | semua T | Hasil dari cache < 1 dtk | OK (0,5 dtk) | — |
| P-17 | Dua postingan berbeda pada `permalink.php?story_fbid=` | — | Dua laporan berbeda | Bisa tertukar | 6 |
| P-18 | Mesin pencari sedang down | — | Ditulis "tidak tersedia"; verdict tidak dipaksa | OK untuk down; salah untuk "hasil kosong" | 7 |
| P-19 | URL internal/IP lokal di teks | S8 | Ditolak, tidak di-fetch | Di-fetch | 1 |
| P-20 | Lowongan asli menulis "tidak dipungut biaya pendaftaran" | uji fungsi | Sinyal aman | Dibaca sebagai permintaan biaya (+40) | 33 |
| P-21 | Poster difoto kamera HP (≥ 4032 px) | — | Diperkecil lalu dibaca | Error 500 | 40 |
| P-22 | Email Gmail | T11 Dekayu | "Email gratisan, domain tidak dicek" | Panel: "Server email tidak ada, SPF tidak ada" | 37 |

## 3. Skenario per fitur (produksi)

| # | Fitur | Langkah | Seharusnya | Status |
|---|---|---|---|---|
| F-01 | Health | `GET /api/v1/health` | DB dan LLM sehat | OK (status OSINT masih statis, no. 22) |
| F-02 | Verifikasi teks | Tempel T1 | Laporan terbuka, kasus tersimpan | OK (run 6–8) |
| F-03 | Verifikasi gambar | Unggah P1 | OCR, lalu laporan | OK (run 6–7) |
| F-04 | Verifikasi tautan + progres | L1 Threads | Tahap fetch → OCR → NER → OSINT → graf → AI | OK |
| F-05 | Batal saat proses | Esc atau tombol Batal | Fetch dibatalkan, form kembali | OK (dicek 20 Okt) |
| F-06 | Cache | Kirim ulang teks sama | Hasil langsung | OK |
| F-07 | Cari riwayat | `/cari?q=pos` | Ringkasan tanpa nomor/email | OK |
| F-08 | Lookup entitas | `GET /cases/lookup/by-entity` | Hanya admin | BUG: publik dan bocor (no. 2) |
| F-09 | Rate limit | 11 verifikasi dalam 1 menit | Ke-11 ditolak 429 | BELUM: butuh 11 kasus baru di DB produksi |
| F-10 | Kirim laporan komunitas | Isi form `/report-job` | Tersimpan `pending` | BELUM: menulis ke DB produksi |
| F-11 | Laporan masuk ke verifikasi | Setujui laporan nomor X, verifikasi teks bernomor X | +20 komunitas | BUG (no. 3, 34, 35, 36) |
| F-12 | `/community/check` | Cek entitas yang laporannya ditolak | Tidak dihitung | BUG (no. 15) |
| F-13 | Admin tanpa sesi | `GET /api/admin/proxy/cases` | 401 | OK |
| F-14 | Endpoint admin langsung | `GET /api/v1/cases` tanpa token | 401 | OK |
| F-15 | Login admin salah 5 kali | — | 429 selama 15 menit | BELUM: login harus dilakukan tim sendiri |
| F-16 | Moderasi | Setujui dan tolak satu laporan | Status berubah, catatan tersimpan | BELUM: login harus dilakukan tim sendiri |
| F-17 | Gambar bukti di admin | Buka laporan bergambar | Gambar tampil | BUG: 404 (no. 13) |
| F-18 | Logout admin | Logout, lalu pakai cookie lama | Ditolak | BUG: cookie lama tetap berlaku (no. 27) |
| F-19 | API docs | `/docs` | 200 | OK |

## 4. Checklist admin untuk tim (dijalankan sendiri)

Saya tidak mengetik password admin, jadi bagian ini dijalankan tim. Lakukan setelah no. 3, 13, 15, 34, 35, dan 36 diperbaiki. Laporan uji ini masuk ke produksi, jadi hapus setelah selesai.

1. Buka `verifin.web.id/admin`, coba password salah 5 kali → muncul pesan "Terlalu banyak percobaan".
2. Login yang benar → statistik dan grafik tampil, angka kasus = 14.
3. Dari HP lain, kirim satu laporan komunitas dengan gambar bukti, untuk nomor milik tim.
4. Di admin: gambar bukti tampil, lalu setujui laporan dengan catatan.
5. Verifikasi lowongan yang memuat nomor itu → laporan menampilkan "Dilaporkan komunitas".
6. Tolak laporan kedua → `/community/check` tidak menghitungnya.
7. Logout → buka `/admin` lagi, harus diminta login.
8. Hapus laporan uji dan kasus uji (backup dulu).
