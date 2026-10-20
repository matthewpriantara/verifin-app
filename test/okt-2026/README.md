# Loker uji Oktober 2026

Kumpulan loker nyata untuk menguji tiga kanal input Verifin (teks, link, poster). T1, T2, L1, L2, dan P1 diambil dari postingan publik Threads pada 18 Okt 2026, lalu dicek manual tanpa Verifin. T3–T8 adalah lowongan penipuan yang sudah dibantah resmi oleh perusahaan atau instansi yang namanya dicatut. T9–T11 adalah lowongan asli dari pusat karier UAD (`cdc.uad.ac.id`). Set lama di `test/` (The Biker Shop, VinFast, PT SISI) tetap disimpan karena dipakai di Laporan Akhir Bab G.

> Label "kesimpulan manual" adalah hasil pengecekan tim, bukan kebenaran mutlak. Untuk kasus yang tidak bisa dipastikan, labelnya ditulis apa adanya.

| ID | Kanal | Input | Sumber | Kesimpulan manual | Verdict yang diharapkan |
|---|---|---|---|---|---|
| T1 | Teks | `T1-teks-hotel-new-saphir.txt` | [Threads @jogjalowker_official, 16 Okt 2026](https://www.threads.com/@jogjalowker_official/post/DejIohQkerQ) | Kemungkinan asli, tapi posisi belum terkonfirmasi | AMAN atau WASPADA |
| T2 | Teks | `T2-teks-packing-pasar-kemis.txt` | [Threads @fahadhamzah_, 9 Okt 2026](https://www.threads.com/@fahadhamzah_/post/DeQi-aTAX0G) | Kemungkinan asli (rekrutmen outsourcing PT IGS), tetapi teksnya sendiri tidak menyebut perusahaan | WASPADA (dari teks saja identitas tidak bisa dicek) |
| T3 | Teks | `T3-teks-surat-panggilan-pertamina.txt` | [IDN Times, 2 Mar 2026](https://www.idntimes.com/business/economy/cek-fakta-waspada-surat-panggilan-seleksi-palsu-atas-nama-pertamina-00-bvq5c-pypb8n) | **Penipuan terkonfirmasi** (dicap HOAX oleh Pertamina) | BAHAYA |
| T4 | Teks | `T4-teks-loker-pos-indonesia.txt` | [Jalahoaks DKI, 22 Mei 2026](https://jalahoaks.jakarta.go.id/detail/Hoaks-Pendaftaran-Lowongan-Pekerjaan-PT-Pos-Indonesia-2026-Melalui-Whatsapp) | **Penipuan terkonfirmasi** (dibantah Pos Indonesia) | WASPADA atau BAHAYA |
| T5 | Teks | `T5-teks-loker-adaro.txt` | [TurnBackHoax, 10 Okt 2026](https://turnbackhoax.id/articles/37115-penipuan-tautan-lowongan-kerja-adaro-andalan-indonesia) | **Penipuan terkonfirmasi** (Adaro tidak membuka lowongan; tautan meminta KTP dan Telegram) | WASPADA atau BAHAYA |
| T6 | Teks | `T6-teks-loker-ultra-milk.txt` | [TurnBackHoax, 20 Jul 2026](https://turnbackhoax.id/articles/35741-penipuan-tautan-pendaftaran-lowongan-ultra-milk-2026) | **Penipuan terkonfirmasi** (rekrutmen resmi hanya lewat DigitalCV) | WASPADA atau BAHAYA |
| T7 | Teks | `T7-teks-loker-lansia.txt` | [TurnBackHoax, 11 Agu 2026](https://turnbackhoax.id/articles/36089-penipuan-tautan-lowongan-kerja-untuk-lansia-2026) | **Penipuan terkonfirmasi** (tiruan program Kemnaker; tautan phishing) | WASPADA atau BAHAYA |
| T8 | Teks | `T8-teks-loker-pos-indonesia-gaji.txt` | [TurnBackHoax, 5 Mei 2026](https://turnbackhoax.id/articles/34055-penipuan-lowongan-kerja-pos-indonesia) | **Penipuan terkonfirmasi** (Pos Indonesia tidak membuka lowongan) | WASPADA atau BAHAYA |
| T9 | Teks | `T9-teks-aam-sdp-2026.txt` | [CDC UAD](https://cdc.uad.ac.id/jobs/anugrah-argon-medica-aam-supervisory-development-program-sdp-2026) | Asli (situs `anugrah-argon.com` aktif; bagian dari grup Medela Potentia) | AMAN |
| T10 | Teks | `T10-teks-komitrando-hr.txt` | [CDC UAD](https://cdc.uad.ac.id/jobs/pt-komitrando-emporio-hr-generalist) | Asli (situs `komitrando.com`: pabrik tas di Yogyakarta sejak 1990) | AMAN |
| T11 | Teks | `T11-teks-dekayu-fulltime.txt` | [CDC UAD](https://cdc.uad.ac.id/jobs/dekayu-loker-full-time) | Asli menurut listing kampus; memakai email Gmail (identitas belum dicek ke luar listing) | AMAN atau WASPADA |
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

### T3 · Surat panggilan seleksi palsu atas nama PT Pertamina (Persero)
- Sumber: gambar surat dan isi artikel IDN Times (2 Mar 2026). Pertamina menandai surat ini dengan cap "HOAX" di Instagram resminya dan menegaskan informasi resmi hanya di `recruitment.pertamina.com`.
- Isi surat ditranskripsi dari gambar artikel tanpa cap HOAX. Bagian yang tertutup cap ditulis `[...]`. Daftar 40 nama peserta di surat **tidak** disalin. Tiga baris terakhir (wajib pesan tiket sebelum 22.15 WIB lewat "agen perjalanan resmi", biaya diganti setelah tiba, konfirmasi ke WA +62 822-2133-3836, nama "Ketua Tim Recruitment") disusun dari kutipan artikel karena bagian itu tidak terlihat di gambar.
- Pola: dinyatakan lulus tanpa melamar, wajib bayar tiket dengan janji *reimburse*, konfirmasi lewat WhatsApp pribadi.

### T4 · Lowongan palsu PT Pos Indonesia 2026
- Sumber: unggahan Facebook halaman "Loker Indonesia" yang dimuat Jalahoaks DKI Jakarta (22 Mei 2026, mengutip Tirto 30 Apr 2026). Pos Indonesia menegaskan pendaftaran tidak pernah lewat WhatsApp pribadi atau akun media sosial tidak resmi; kanal resminya `posindonesia.co.id/id/karir` dan `posindonesia.rakamin.com`.
- Teks ditranskripsi dari takarir dan poster pada gambar Jalahoaks (tanpa label HOAKS). Nomor WhatsApp tidak terlihat di gambar.
- Pola: mencatut BUMN, daftar lewat "WhatsApp admin" dan "link di bio", tidak ada permintaan biaya di teks. Dari teks saja tidak ada bukti keras (biaya, nomor terlapor), sehingga WASPADA adalah batas atas yang jujur untuk input ini.

### T5–T8 · Penipuan dari arsip TurnBackHoax (Mafindo)
- Artikel TurnBackHoax hanya mengutip sebagian narasi unggahan. Teks uji disusun dari kutipan tersebut tanpa menambah klaim baru; baris yang tidak dikutip artikel tidak ditulis. Untuk T8, baris "Daftar lewat link di bio" diambil dari deskripsi artikel bahwa pendaftaran diarahkan ke tautan di bio akun.
- Tidak satu pun dari keempat teks meminta biaya secara langsung; modusnya mengarahkan ke formulir yang meminta data pribadi (nama sesuai KTP, nomor Telegram).

### T9–T11 · Lowongan asli dari pusat karier UAD
- Disalin dari halaman CDC UAD pada 18 Okt 2026, disingkat tanpa mengubah isi (bagian benefit dan tautan flyer dibuang).
- T9 dan T10 dicek ke situs perusahaan. T11 (Dekayu) memakai email Gmail dan hanya dicek sampai listing kampus.

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

Dijalankan lewat antarmuka web (Playwright) terhadap backend yang terhubung ke Supabase. Screenshot dan JSON run terakhir ada di `hasil/`; run sebelumnya diarsipkan di `hasil/run1/` dan `hasil/run2/`. Sebelum tiap run ulang, baris `job_cases` hasil run sebelumnya dihapus supaya tidak terbaca dari cache.

| ID | Status sebenarnya | Run 1 | Run 2 | Run 3 | Run 5 | **Run 6–7 (final, 20 Okt)** | Durasi run 6–7 |
|---|---|---|---|---|---|---|---|
| T1 | Asli | AMAN 8 | AMAN 10 | AMAN 10 | AMAN 10 | **AMAN 12** | 39 dtk |
| T9 | Asli | — | — | — | AMAN 15 | **AMAN 30** | 39 dtk |
| T10 | Asli | — | — | — | AMAN 8 | **AMAN 12** | 32 dtk |
| T11 | Asli | — | — | — | AMAN 15 | **AMAN 20** | 39 dtk |
| L1 | Asli | AMAN 10 | AMAN 12 | AMAN 12 | AMAN 12 | **AMAN 15** | 47 dtk |
| P1 | Asli | AMAN 25 | AMAN 20 | AMAN 24 | AMAN 20 | **AMAN 28** | 36 dtk |
| T2 | Abu-abu (perusahaan nyata, teks anonim) | AMAN 28 | WASPADA 52 | WASPADA 50 | WASPADA 50 | **WASPADA 50** | 20 dtk |
| L2 | Abu-abu (pola sewa akun, belum terkonfirmasi) | WASPADA 60 | WASPADA 60 | WASPADA 60 | WASPADA 55 | **WASPADA 58** | 19 dtk |
| T3 | Penipuan | — | — | BAHAYA 95 | BAHAYA 95 | **BAHAYA 95** | 33 dtk |
| T4 | Penipuan | — | — | WASPADA 68 | WASPADA 65 | **WASPADA 73** (run 8) | 32 dtk |
| T5 | Penipuan | — | — | — | WASPADA 65 | **WASPADA 73** | 32 dtk |
| T6 | Penipuan | — | — | — | WASPADA 55 | **WASPADA 72** | 44 dtk |
| T7 | Penipuan | — | — | — | WASPADA 45 | **WASPADA 45** | 15 dtk |
| T8 | Penipuan | — | — | — | WASPADA 52 | **WASPADA 72** | 31 dtk |

Run 4 (arsip tidak disimpan) dipakai untuk menemukan dua celah yang diperbaiki sebelum run 5: frasa "link di. bio" tidak terbaca sebagai jalur tidak resmi, dan label XAI "Pendaftaran via WhatsApp" ikut muncul pada kasus tautan bio.

**Run 6–7 (20 Okt 2026, server produksi `verifin.web.id`)** dijalankan langsung ke API backend setelah perbaikan audit-003: query cek hoaks baru (`scam_check`), geocoder yang mencoba nama usaha, dan prompt yang disusun ulang. Baris `job_cases` tidak dihapus; run ulang memperbarui baris yang sama. Run 7 mengulang T1, T3–T6, T8–T10 setelah penyaring peringatan diperketat. JSON: `hasil/run6.json` dan `hasil/run7.json`.
- Penipuan yang ditandai: **6 dari 6**, dan skornya naik mendekati batas BAHAYA. T4, T5, T6, dan T8 kini WASPADA 72–73 (run 5: 52–65), karena pencarian kini menemukan artikel bantahan atas nama perusahaan yang dicatut (mis. Komdigi dan RRI untuk Pos Indonesia). T3 tetap satu-satunya BAHAYA karena hanya T3 yang meminta biaya.
- Lowongan asli yang dinilai AMAN: **6 dari 6**. T9 (Medela Potentia) naik ke AMAN 30 karena perusahaan itu sendiri pernah menerbitkan peringatan pencatutan namanya. Ini dicatat sebagai faktor ringan, bukan bahaya.
- Titik peta T10 sekarang tepat di POI "Komitrando" pada OSM (run 5: ruas jalan, 0,36 km). Kecocokan tingkat wilayah (T3) hanya menampilkan kelurahan, kota, dan kode pos.
- Durasi tanpa cache: 15–47 detik. Dengan cache: 0,5 detik.

**Run 8 (20 Okt 2026, sore): T3 dan T4 diulang** setelah bug "(Persero)" diperbaiki. Sebelumnya `resolve_entity` memakai isi kurung sebagai nama, jadi T3 dan T4 dicari sebagai "Persero" dan bukti peringatan T4 berisi artikel hoaks Pertamina dan PLN, bukan Pos Indonesia. Setelah perbaikan, T3 dicari sebagai "Pertamina" (5 artikel bantahan Pertamina; tetap BAHAYA 95) dan T4 sebagai "Pos Indonesia" (5 artikel bantahan Pos Indonesia dari Komdigi, RRI, dan pemda; WASPADA 73). JSON: `hasil/run8.json`. Klaim run 6–7 bahwa "Komdigi dan RRI untuk Pos Indonesia" ditemukan berlaku untuk T8; untuk T4 baru benar sejak run 8.

**Run 9 (20 Okt 2026, malam): seluruh 14 kasus dijalankan ulang di produksi setelah audit-006** (`570583c` → `0ce41d9`). Versi skema cache naik, jadi setiap kasus dihitung ulang dan baris yang sama diperbarui (`case_id` tetap). JSON: `hasil/run9.json`.

| ID | Status sebenarnya | Run 6–8 | **Run 9** | Durasi |
|---|---|---|---|---|
| T1 | Asli | AMAN 12 | **AMAN 12** | 40 dtk |
| T9 | Asli | AMAN 30 | **AMAN 25** | 49 dtk |
| T10 | Asli | AMAN 12 | **AMAN 10** | 37 dtk |
| T11 | Asli | AMAN 20 | **AMAN 22** | 31 dtk |
| L1 | Asli | AMAN 15 | **AMAN 18** | 43 dtk |
| P1 | Asli | AMAN 28 | **AMAN 28** | 52 dtk |
| T2 | Abu-abu | WASPADA 50 | **WASPADA 52** | 38 dtk |
| L2 | Abu-abu | WASPADA 58 | **WASPADA 55** | 21 dtk |
| T3 | Penipuan | BAHAYA 95 | **BAHAYA 92** | 46 dtk |
| T4 | Penipuan | WASPADA 73 | **WASPADA 73** | 31 dtk |
| T5 | Penipuan | WASPADA 73 | **WASPADA 74** | 33 dtk |
| T6 | Penipuan | WASPADA 72 | **WASPADA 72** | 42 dtk |
| T7 | Penipuan | WASPADA 45 | **WASPADA 45** | 15 dtk |
| T8 | Penipuan | WASPADA 72 | **WASPADA 72** | 27 dtk |

- Penipuan yang ditandai: **6 dari 6**. Lowongan asli yang dinilai AMAN: **6 dari 6**. Durasi tanpa cache 15–52 dtk; dengan cache 0,5 dtk.
- Artikel bantahan kini punya kontribusi XAI sendiri ("Nama pernah dicatut", +15), jadi porsi "Penyesuaian Penalaran AI" mengecil (T4: +26 → +11).
- T3 sekarang membawa nomor WhatsApp-nya (`+62 822-2133-3836`, Kaspersky NETRAL). Pada run pertama hari ini nomor itu sempat hilang karena baris di atasnya menyebut "admin grup"; diperbaiki di `0ce41d9` dan T3 dihitung ulang.
- Percobaan pertama run 9 (`hasil/run9-percobaan1`, tidak disimpan) dihentikan karena tiga bug: kota penempatan "Wilayah Kerja PT. Pos Indonesia (Persero)" dipetakan ke Tuban, "Indonesia" dipetakan ke titik tengah negara, dan "Kirim CV terbaik Anda" terbaca sebagai badan usaha. Saat itu penyedia LLM juga sempat membalas error 520, sehingga T11 jatuh ke penilaian aturan. Ketiga bug diperbaiki (`f5be179`) sebelum run final.
- Laporan komunitas nyata untuk nomor T3 (sumber: IDN Times) dikirim lewat form produksi dan berstatus *menunggu* moderasi; laporan T3 menampilkannya sebagai "1 laporan menunggu tinjauan admin", belum dipakai sebagai bukti.

**Ringkasan run 5** (kasus abu-abu tidak dihitung):
- Penipuan yang ditandai (WASPADA atau BAHAYA): **6 dari 6**. Yang sampai BAHAYA hanya 1 dari 6 (T3, satu-satunya yang meminta biaya). Lima lainnya hanya mengarahkan ke WhatsApp/tautan bio tanpa bukti keras, sehingga berhenti di WASPADA.
- Lowongan asli yang dinilai AMAN: **6 dari 6**; tidak ada lowongan asli yang ditandai.
- Kalau T2 dihitung sebagai lowongan asli, ada 1 penandaan keliru (WASPADA) dari 7. Penandaan ini disengaja: dari teksnya saja, identitas pemberi kerja tidak bisa diperiksa.
- Durasi analisis lengkap tanpa cache: 18–72 detik (poster P1 paling lama karena OCR).
- Set ini masih kecil (14 kasus) dan dipilih tim, sehingga belum bisa dipakai untuk mengklaim akurasi umum.

Celah yang masih terlihat: pada T6 (Ultra Milk) dan T8 (POS INDONESIA tanpa "Persero"), nama merek yang dicatut tidak memakai akhiran Persero/Tbk, sehingga sinyal pencatutan BUMN tidak menyala. Di T6, jejak web merek asli masih tercatat sebagai "Hasil Web Relevan Ditemukan" (−10). LLM tetap menilai keduanya WASPADA.

### Bug yang ditemukan run 1 (diperbaiki sebelum run 2)
1. Penalti "Tidak Ada SPF/DMARC pada Domain Korporat" (+12) terpicu walau lowongan tidak punya domain sama sekali (T2).
2. Nama perusahaan hasil OCR terpecah (`PT.INDOKARYA`, `GLOBALSINERGI`, `iGS`), sehingga pencarian web memakai potongan nama.
3. Pola "lamar via WhatsApp" tidak mengenali "Kirim CV: 0896…" dan "pesan WhatsApp".
4. Kasus WASPADA ikut dihitung sebagai penipuan di Fraud Network Graph, sehingga P1 sempat diberi label "terhubung ke jaringan penipuan" hanya karena nomornya sama dengan T2.

### Akar masalah yang diperbaiki sebelum run 3
Run 2 sudah benar, tetapi sebagian perbaikannya masih tambalan. Akar masalahnya:
- **T2 AMAN 28 bukan karena prompt kurang aturan.** Regex badan usaha membaca "Kirim **CV**" sebagai CV (badan usaha), sehingga sinyal "gaji tanpa nama perusahaan" mati. Regex alamat `jl\.` juga tidak pernah cocok karena `\b` setelah titik. Keduanya diperbaiki; nama perusahaan hasil NER sekarang ikut dipakai classifier.
- **LLM tidak pernah menerima sinyal teks deterministik**, dan jalur `url/stream` sama sekali tidak menjalankan classifier (XAI tautan tidak punya kontribusi teks). Sinyal sekarang dikirim ke prompt di keempat jalur, dan aturan prompt khusus T2 diganti aturan yang merujuk sinyal tersebut (`anonymous_employer_claim`).
- **Spasi OCR hilang** (`GLOBALSINERGI`, `LOWONGANKERJA`) berasal dari model rekognisi `latin` PP-OCRv3. Diganti model `en` PP-OCRv4; inferensi juga lebih cepat (13 dtk vs 21 dtk pada P1).
- **Urutan baca OCR mencampur kolom poster.** Teks sekarang disusun per blok tata letak, sehingga baris kedua nama di logo selalu tepat di bawah baris pertama dan sel tabel ("SHIFT PAGI / Rp120.000") tetap berpasangan.
- **Nama BUMN dihitung sebagai sinyal aman** (`persero`, `bumn`, `tbk` di daftar kata aman), padahal penipu justru mencatut nama itu. Dihapus, diganti sinyal `brand_unofficial_channel` (nama BUMN/Tbk + daftar hanya lewat WhatsApp/tautan di bio). Kata "gratis" saja juga tidak lagi dihitung aman, dan jejak web atau alamat milik BUMN yang dicatut tidak lagi dihitung sebagai bukti aman di XAI.
- Varian nama yang sama ("PT POS INDONESIA", "PT Pos Indonesia (Persero)") sekarang disatukan.

### Perubahan sebelum run 5
- Masking data pribadi: nomor telepon, bagian lokal email, NIK, dan rekening diganti token sebelum teks dikirim ke LLM.
- OCR: `requirements.txt` dulu meminta PaddleOCR 3.x untuk semua platform, sedangkan uji lokal memakai 2.8.1. Di image Docker, Paddle 3.3 tanpa oneDNN butuh 90–125 dtk per poster, dan oneDNN-nya crash. Sekarang Linux/Windows dikunci ke Paddle 3.1.1 + PaddleOCR 3.7.0 dengan oneDNN dan model mobile (17,8 dtk per poster di container setelah model dimuat), sedangkan macOS Intel tetap 2.6.2 + 2.8.1.
