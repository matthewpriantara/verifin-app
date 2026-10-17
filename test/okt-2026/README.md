# Loker uji Oktober 2026

Kumpulan loker nyata untuk menguji tiga kanal input Verifin (teks, link, poster). Semua diambil dari postingan publik Threads pada 18 Okt 2026, lalu dicek manual tanpa Verifin. Set lama di `test/` (The Biker Shop, VinFast, PT SISI) tetap disimpan karena dipakai di Laporan Akhir Bab G.

> Label "kesimpulan manual" adalah hasil pengecekan tim, bukan kebenaran mutlak. Untuk kasus yang tidak bisa dipastikan, labelnya ditulis apa adanya.

| ID | Kanal | Input | Sumber | Kesimpulan manual | Verdict yang diharapkan |
|---|---|---|---|---|---|
| T1 | Teks | `T1-teks-hotel-new-saphir.txt` | [Threads @jogjalowker_official, 16 Okt 2026](https://www.threads.com/@jogjalowker_official/post/DejIohQkerQ) | Kemungkinan asli, tapi posisi belum terkonfirmasi | AMAN atau WASPADA |
| T2 | Teks | `T2-teks-packing-pasar-kemis.txt` | [Threads @fahadhamzah_, 9 Okt 2026](https://www.threads.com/@fahadhamzah_/post/DeQi-aTAX0G) | Kemungkinan asli (rekrutmen outsourcing PT IGS), tetapi teksnya sendiri tidak menyebut perusahaan | WASPADA (dari teks saja identitas tidak bisa dicek) |
| L1 | Link | `https://www.threads.com/@jogjalowker_official/post/DegeamfkV1w` | Threads @jogjalowker_official, 13 Okt 2026 | Asli | AMAN |
| L2 | Link | `https://www.threads.com/@pastidapatuangg/post/DekRfpYEzzW` | Threads @pastidapatuangg, 17 Okt 2026 | Sangat mencurigakan (pola sewa akun LinkedIn) | WASPADA atau BAHAYA |
| P1 | Poster | `P1-poster-packing-pasar-kemis.jpg` | Gambar lampiran postingan T2 (Threads @fahadhamzah_, 9 Okt 2026) | Kemungkinan asli (PT Indokarya Global Sinergi, perusahaan outsourcing di Cikupa, Tangerang) | AMAN atau WASPADA |

## Catatan pengecekan manual

### T1 · Hotel New Saphir Yogyakarta (Chef de Partie)
- Alamat Jl. Laksda Adisucipto No. 38 cocok dengan situs resmi `newsaphirhotel.com`.
- Email lamaran memakai domain resmi hotel (`@newsaphirhotel.com`).
- Halaman lowongan resmi (`/lowongan-pekerjaan/`, dicek 18 Okt 2026) hanya memuat lowongan magang. Posisi Chef de Partie **tidak tercantum** di sana.
- Nomor WA `0823 2386 3434` tidak tercantum di situs resmi. Telepon resmi hotel: +62 274 566222.
- Kesimpulan: identitas perusahaan nyata dan kanal lamaran resmi, tapi posisinya belum bisa dipastikan. Kasus abu-abu yang bagus untuk menguji apakah Verifin jujur soal ketidakpastian.

### T2 · Operator Packing, Pasar Kemis
- Teks tidak menyebut nama perusahaan, hanya "pabrik baru"; kontak hanya nomor WA. Gaji Rp120–130 rb/hari untuk 11 jam kerja; tidak ada permintaan biaya.
- Ada komentar publik yang menuduh penipuan, dan satu komentar menyebut pelamar dimintai KTP serta nama ibu kandung lalu nomornya berganti.
- **Koreksi setelah pengecekan lanjutan (lihat P1):** pengunggah adalah Operations Manager PT Indokarya Global Sinergi, perusahaan outsourcing yang nyata. KTP dan nama ibu kandung lazim diminta untuk pendaftaran BPJS, jadi komentar itu bukan bukti penipuan. Nomor WA pada lowongan berbeda dari kontak resmi di situs perusahaan.
- Kesimpulan: kemungkinan rekrutmen outsourcing yang sah. Namun dari **teks ini saja** identitas pemberi kerja tidak bisa diperiksa, sehingga WASPADA ("cek dulu") adalah keluaran yang wajar.

### L1 · Qhomemart (Videographer)
- Alamat Jl. Raya Janti No. 96, email `recruitment@qhomemart.co.id`, dan WA `0857-0129-9095` **semuanya cocok** dengan listing Qhomemart di pusat karier UAD (`cdc.uad.ac.id/jobs/qhomemart-5-positions`).
- Kesimpulan: asli.

### L2 · "Open job WFH, syarat punya LinkedIn usia 1 tahun"
- Isi postingan hanya tiga baris: kerja WFH, syarat akun LinkedIn berumur 1 tahun, bayaran 192 per minggu.
- Meminta akun LinkedIn berumur tertentu adalah pola sewa atau jual akun. Ini melanggar ketentuan LinkedIn dan sering dipakai untuk penipuan.
- Tidak ada nama perusahaan, kontak, atau alamat. Entitas yang bisa dicek sangat sedikit.
- Kesimpulan: sangat mencurigakan. Kasus uji untuk input yang hampir tanpa entitas.

### P1 · Poster Operator Packing "PT. Indokarya Global Sinergi"
- Gambar lampiran postingan T2, diunduh 18 Okt 2026 (1086×1448, JPEG). Gambar jelas buatan AI.
- Poster menyebut **PT. Indokarya Global Sinergi (IGS)**. Pencarian awal lewat mesin pencari umum tidak menemukannya, tetapi pencarian SearXNG Verifin menemukan situs `ptigs.com` dan profil LinkedIn pengunggah.
- **Diverifikasi langsung (`ptigs.com`):** PT Indokarya Global Sinergi bergerak di outsourcing dan penyediaan tenaga kerja, kantor di Bizpoint Modern Multi Business Blok R2 No. 03, Cikupa, Kabupaten Tangerang (bersebelahan dengan Pasar Kemis). Situs tidak memuat lowongan ini dan tidak menyebut pungutan biaya. Nomor WA lowongan berbeda dari kontak resmi situs.
- Kesimpulan: kemungkinan asli. Pelajaran: pengecekan manual awal kami keliru karena hanya mengandalkan satu mesin pencari.

## Hasil uji Verifin (18 Okt 2026, aplikasi lokal)

Dijalankan lewat antarmuka web (Playwright) terhadap backend yang terhubung ke Supabase. Screenshot dan JSON lengkap ada di `hasil/`; hasil run pertama diarsipkan di `hasil/run1/`.

| ID | Run 1 | Run 2 | Durasi run 2 | Sesuai cek manual? |
|---|---|---|---|---|
| T1 | AMAN 8 | AMAN 10 | 44 dtk | Ya |
| T2 | AMAN 28 | **WASPADA 52** | 24 dtk | Run 1 terlalu longgar; run 2 ya |
| L1 | AMAN 10 | AMAN 12 | 41 dtk | Ya |
| L2 | WASPADA 60 | WASPADA 60 | 21 dtk | Ya |
| P1 | AMAN 25 | AMAN 20 | 58 dtk | Ya |

Run 1 memperlihatkan empat bug, yang diperbaiki sebelum run 2:
1. Penalti "Tidak Ada SPF/DMARC pada Domain Korporat" (+12) terpicu walau lowongan tidak punya domain sama sekali (T2).
2. Nama perusahaan hasil OCR terpecah (`PT.INDOKARYA`, `GLOBALSINERGI`, `iGS`), sehingga pencarian web memakai potongan nama dan menemukan perusahaan lain bernama mirip.
3. Pola "lamar via WhatsApp" tidak mengenali "Kirim CV: 0896…" dan "pesan WhatsApp".
4. Kasus WASPADA ikut dihitung sebagai kasus penipuan di Fraud Network Graph, sehingga P1 sempat diberi label "terhubung ke jaringan penipuan" hanya karena nomornya sama dengan T2.

Selain itu prompt LLM ditambah aturan: lowongan yang mengaku perusahaan/pabrik tetapi tidak menyebut nama badan usaha dan hanya memberi nomor WhatsApp pribadi dinilai WASPADA. Aturan ini dirumuskan setelah melihat kasus T2, jadi perlu divalidasi pada set uji yang lebih besar agar tidak hanya cocok untuk kasus ini.

Catatan: kelima kasus belum memuat lowongan penipuan yang terkonfirmasi, sehingga jalur verdict BAHAYA belum teruji pada data nyata di set ini.
