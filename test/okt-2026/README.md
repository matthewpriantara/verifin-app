# Loker uji Oktober 2026

Kumpulan loker nyata untuk menguji tiga kanal input Verifin (teks, link, poster). Semua diambil dari postingan publik Threads pada 18 Okt 2026, lalu dicek manual tanpa Verifin. Set lama di `test/` (The Biker Shop, VinFast, PT SISI) tetap disimpan karena dipakai di Laporan Akhir Bab G.

> Label "kesimpulan manual" adalah hasil pengecekan tim, bukan kebenaran mutlak. Untuk kasus yang tidak bisa dipastikan, labelnya ditulis apa adanya.

| ID | Kanal | Input | Sumber | Kesimpulan manual | Verdict yang diharapkan |
|---|---|---|---|---|---|
| T1 | Teks | `T1-teks-hotel-new-saphir.txt` | [Threads @jogjalowker_official, 16 Okt 2026](https://www.threads.com/@jogjalowker_official/post/DejIohQkerQ) | Kemungkinan asli, tapi posisi belum terkonfirmasi | AMAN atau WASPADA |
| T2 | Teks | `T2-teks-packing-pasar-kemis.txt` | [Threads @fahadhamzah_, 9 Okt 2026](https://www.threads.com/@fahadhamzah_/post/DeQi-aTAX0G) | Mencurigakan, belum terbukti penipuan | WASPADA |
| L1 | Link | `https://www.threads.com/@jogjalowker_official/post/DegeamfkV1w` | Threads @jogjalowker_official, 13 Okt 2026 | Asli | AMAN |
| L2 | Link | `https://www.threads.com/@pastidapatuangg/post/DekRfpYEzzW` | Threads @pastidapatuangg, 17 Okt 2026 | Sangat mencurigakan (pola sewa akun LinkedIn) | WASPADA atau BAHAYA |
| P1 | Poster | `P1-poster-packing-pasar-kemis.jpg` | Gambar lampiran postingan T2 (Threads @fahadhamzah_, 9 Okt 2026) | Mencurigakan, belum terbukti penipuan | WASPADA atau BAHAYA |

## Catatan pengecekan manual

### T1 · Hotel New Saphir Yogyakarta (Chef de Partie)
- Alamat Jl. Laksda Adisucipto No. 38 cocok dengan situs resmi `newsaphirhotel.com`.
- Email lamaran memakai domain resmi hotel (`@newsaphirhotel.com`).
- Halaman lowongan resmi (`/lowongan-pekerjaan/`, dicek 18 Okt 2026) hanya memuat lowongan magang. Posisi Chef de Partie **tidak tercantum** di sana.
- Nomor WA `0823 2386 3434` tidak tercantum di situs resmi. Telepon resmi hotel: +62 274 566222.
- Kesimpulan: identitas perusahaan nyata dan kanal lamaran resmi, tapi posisinya belum bisa dipastikan. Kasus abu-abu yang bagus untuk menguji apakah Verifin jujur soal ketidakpastian.

### T2 · Operator Packing, Pasar Kemis
- Tidak ada nama perusahaan, hanya "pabrik baru". Kontak hanya nomor WA pribadi.
- Gaji Rp120–130 rb/hari untuk 11 jam kerja: rendah, bukan tidak realistis. Tidak ada permintaan biaya di teks.
- Ada komentar publik yang menuduh penipuan. Pengunggah membalas bahwa "nama PT resmi dan ada di maps", tapi tidak menyebut namanya.
- Kesimpulan: mencurigakan karena identitasnya tidak bisa diverifikasi. Belum ada bukti penipuan.

### L1 · Qhomemart (Videographer)
- Alamat Jl. Raya Janti No. 96, email `recruitment@qhomemart.co.id`, dan WA `0857-0129-9095` **semuanya cocok** dengan listing Qhomemart di pusat karier UAD (`cdc.uad.ac.id/jobs/qhomemart-5-positions`).
- Kesimpulan: asli.

### L2 · "Open job WFH, syarat punya LinkedIn usia 1 tahun"
- Isi postingan hanya tiga baris: kerja WFH, syarat akun LinkedIn berumur 1 tahun, bayaran 192 per minggu.
- Meminta akun LinkedIn berumur tertentu adalah pola sewa atau jual akun. Ini melanggar ketentuan LinkedIn dan sering dipakai untuk penipuan.
- Tidak ada nama perusahaan, kontak, atau alamat. Entitas yang bisa dicek sangat sedikit.
- Kesimpulan: sangat mencurigakan. Kasus uji untuk input yang hampir tanpa entitas.

### P1 · Poster Operator Packing "PT. Indokarya Global Sinergi"
- Gambar lampiran dari postingan yang sama dengan T2, diunduh 18 Okt 2026 (1086×1448, JPEG).
- Poster menyebut **PT. Indokarya Global Sinergi (IGS)**, nama yang tidak ada di teks postingan. Pencarian web (18 Okt 2026) tidak menemukan jejak publik perusahaan dengan nama ini.
- Gambar jelas buatan AI (wajah dan latar pabrik generik). Pelamar diminta mengirim nama, usia, domisili, serta tinggi dan berat badan lewat WhatsApp.
- Isi lain sama dengan T2: gaji Rp120–130 rb/hari, 11 jam kerja, khusus perempuan 18–28 tahun, WA `0896-7951-0296`.
- Kesimpulan: lebih mencurigakan daripada teks T2, karena nama PT-nya tidak terlacak. Tetap belum ada bukti penipuan.
- Catatan uji: kontennya tumpang tindih dengan T2, tapi teks hasil OCR berbeda, jadi tidak terkena cache teks. Bandingkan apakah poster (yang punya nama PT) dan teks (tanpa nama PT) menghasilkan verdict yang konsisten.
