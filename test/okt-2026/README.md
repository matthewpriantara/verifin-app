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

**Run 10 (27 Okt 2026): seluruh 14 kasus dengan LLM lokal `gemma4:12b-it-qat`** (Ollama 0.40.10 di VPS, commit `c167f2a`). Run 9 memakai `ag/gemini-3.8-flash-medium`. JSON: `hasil/run10-gemma.json`.

Percobaan pertama hari ini (sebelum `c167f2a`) gagal: Gemma 4 berpikir dulu secara default, jawabannya masuk ke `reasoning_content` dan `content` kosong, sehingga penalaran gagal validasi tiga kali dan jatuh ke penilaian aturan (T9, T4, T5), dan NER LLM jatuh ke regex. Bukan timeout. Hasil penilaian aturan itu juga tersimpan di cache (T3 terbaca BAHAYA 100 dari cache). Perbaikan: `LLM_REASONING_EFFORT=none` (uji kecil: 696 → 30 token, 7,2 → 0,4 dtk), cache tidak lagi memakai hasil penilaian aturan, dan `VERIFY_CACHE_ENABLED=false` selama uji ulang.

| ID | Status sebenarnya | Run 9 (Gemini) | **Run 10 (Gemma)** | Durasi | Penyesuaian AI |
|---|---|---|---|---|---|
| T1 | Asli | AMAN 12 | **AMAN 12** | 28 dtk | −1 |
| T9 | Asli | AMAN 25 | **WASPADA 70** | 17 dtk | +53 |
| T10 | Asli | AMAN 10 | **AMAN 15** | 16 dtk | +27 |
| T11 | Asli | AMAN 22 | **AMAN 25** | 19 dtk | 0 |
| L1 | Asli | AMAN 18 | **AMAN 15** | 33 dtk | +5 |
| P1 | Asli | AMAN 28 | **AMAN 15** | 36 dtk | −30 |
| T2 | Abu-abu | WASPADA 52 | **WASPADA 55** | 9 dtk | −8 |
| L2 | Abu-abu | WASPADA 55 | **WASPADA 55** | 6 dtk | +43 |
| T3 | Penipuan | BAHAYA 92 | **BAHAYA 98** | 25 dtk | −72 |
| T4 | Penipuan | WASPADA 73 | **WASPADA 74** | 13 dtk | +12 |
| T5 | Penipuan | WASPADA 74 | **WASPADA 74** | 17 dtk | +12 |
| T6 | Penipuan | WASPADA 72 | **WASPADA 72** | 17 dtk | +35 |
| T7 | Penipuan | WASPADA 45 | **WASPADA 55** | 4 dtk | +43 |
| T8 | Penipuan | WASPADA 72 | **WASPADA 72** | 11 dtk | +20 |

- Penipuan yang ditandai: **6 dari 6**. Lowongan asli yang dinilai AMAN: **5 dari 6**. T9 (Anugrah Argon Medica) naik ke WASPADA 70: bukti terukur hanya +5 (artikel pencatutan +15, jejak web −10), sisanya +53 dari penalaran Gemma yang menimbang "nama pernah dicatut" dan pendaftaran lewat bit.ly terlalu berat.
- Durasi tanpa cache 4–36 dtk (run 9: 15–52 dtk).
- "Penyesuaian AI" Gemma lebih besar daripada Gemini pada kasus dengan sedikit bukti (L2, T7: +43). Pada T3, nilai −72 hanya karena jumlah bukti melebihi 100 dan skor dipotong.
- T3 tidak punya `safe_factors` dan `recommendations` (keluaran Gemma kosong di dua kolom itu).
- "Entitas Muncul di Beberapa Kasus" (+15) muncul pada T1, T11, T2, T8, P1. Hash cache memuat nama model, jadi teks yang sama kini tersimpan sebagai baris Gemini dan baris Gemma, dan keduanya saling terhitung sebagai kasus lain.

**Run 11 (27 Okt 2026): Gemini kembali jadi LLM utama** (commit `62c9dee`). Produksi kini memakai `ag/gemini-3.8-flash-medium` lewat Octane sebagai utama dan `gemma4:12b-it-qat` sebagai cadangan (`LLM_FALLBACK_REASONING_EFFORT=none`). Cache tetap dimatikan selama run. JSON: `hasil/run11-gemini.json`.

| ID | Status sebenarnya | Run 9 (Gemini) | Run 10 (Gemma) | **Run 11 (Gemini)** | Durasi |
|---|---|---|---|---|---|
| T1 | Asli | AMAN 12 | AMAN 12 | **AMAN 12** | 42 dtk |
| T9 | Asli | AMAN 25 | WASPADA 70 | **AMAN 25** | 41 dtk |
| T10 | Asli | AMAN 10 | AMAN 15 | **AMAN 10** | 31 dtk |
| T11 | Asli | AMAN 22 | AMAN 25 | **AMAN 24** | 31 dtk |
| L1 | Asli | AMAN 18 | AMAN 15 | **AMAN 16** | 39 dtk |
| P1 | Asli | AMAN 28 | AMAN 15 | **AMAN 28** | 52 dtk |
| T2 | Abu-abu | WASPADA 52 | WASPADA 55 | **WASPADA 52** | 23 dtk |
| L2 | Abu-abu | WASPADA 55 | WASPADA 55 | **WASPADA 58** | 14 dtk |
| T3 | Penipuan | BAHAYA 92 | BAHAYA 98 | **BAHAYA 96** | 43 dtk |
| T4 | Penipuan | WASPADA 73 | WASPADA 74 | **WASPADA 73** | 28 dtk |
| T5 | Penipuan | WASPADA 74 | WASPADA 74 | **WASPADA 72** | 29 dtk |
| T6 | Penipuan | WASPADA 72 | WASPADA 72 | **WASPADA 70** | 31 dtk |
| T7 | Penipuan | WASPADA 45 | WASPADA 55 | **WASPADA 45** | 19 dtk |
| T8 | Penipuan | WASPADA 72 | WASPADA 72 | **WASPADA 72** | 27 dtk |

- Penipuan yang ditandai: **6 dari 6**. Lowongan asli yang dinilai AMAN: **6 dari 6**. Semua verdict sama dengan run 9; skor bergeser paling banyak 4 poin (T3 92 → 96).
- Durasi tanpa cache 14–52 dtk (run 9: 15–52 dtk; run 10 Gemma: 4–36 dtk).
- Semua kasus lewat Evidence Reasoning Gemini; tidak ada yang jatuh ke cadangan Gemma atau penilaian aturan.

**Run 12 (27 Okt 2026, stack home, cache mati): tahap "Memeriksa isi" + pembacaan vision** (commit `69a50c9`–`d71d837`). Tujuannya memastikan gerbang baru tidak menghentikan lowongan normal dan aturan pengaman domain tidak menjatuhkan lowongan asli. L1 dan L2 (tautan) tidak diulang.

| ID | Status sebenarnya | Run 11 | **Run 12** | Catatan |
|---|---|---|---|---|
| T1 | Asli | AMAN 12 | **AMAN 12** | |
| T9 | Asli | AMAN 25 | **AMAN 25** | |
| T10 | Asli | AMAN 10 | **AMAN 8** | |
| T11 | Asli | AMAN 24 | **AMAN 20** | |
| P1 | Asli | AMAN 28 | **AMAN 28** | Poster; OCR + vision |
| T2 | Abu-abu | WASPADA 52 | **WASPADA 50** | |
| T3 | Penipuan | BAHAYA 96 | **BAHAYA 95** | |
| T4 | Penipuan | WASPADA 73 | **WASPADA 73** | Catatan I-05: ada promo akun di luar lowongan |
| T5 | Penipuan | WASPADA 72 | **WASPADA 72** | |
| T6 | Penipuan | WASPADA 70 | **WASPADA 72** | |
| T7 | Penipuan | WASPADA 45 | **WASPADA 50** | |
| T8 | Penipuan | WASPADA 72 | **WASPADA 72** | |

Poster palsu dari LokerJogja.ID (sudah divalidasi palsu oleh tim mereka; tiga di antaranya ada di daftar penipu mereka):

| ID | Poster | Produksi sebelum perubahan | **Run 12** | Catatan |
|---|---|---|---|---|
| F1 | New Trendy | WASPADA 65 | **WASPADA 55** | Domain baru, situs "Tiktok Task" |
| F2 | Guardian Indonesia | WASPADA 45 | **AMAN 28 / WASPADA 45** | Tidak stabil: dua kali dijalankan, hasil berbeda. Gmail + WA atas nama ritel besar; AI kadang menilainya wajar |
| F3 | Sociolla | WASPADA 52 | **WASPADA 55** | Tautan tinyurl hanya terbaca vision (OCR salah baca), jadi dicatat "hanya terbaca AI" |
| F4 | Roemah Boenga | WASPADA 45 (nama terbaca "SBOENGA") | **WASPADA 45** | Nama kini benar dari vision. Tanpa aturan pengaman, IG toko bunga asli membuat AI memberi AMAN 28; domain `roemahboenga.store` tidak punya DNS → aturan "Domain Lamaran Tanpa DNS" menaikkan ke 45 |
| F5 | Sharp Electronics | WASPADA 50 | **WASPADA 55** | `sharp-career.my.id` |

Uji tepi ulang (dulu E1–E5):

| Input | Dulu | **Run 12** |
|---|---|---|
| Berita harga cabai | AMAN 15 | **Berhenti I-01** "Ini sepertinya bukan lowongan kerja" (3 dtk) |
| "loker admin wa 0812 3456 7890" | WASPADA 50 | **Berhenti I-03** "Informasinya terlalu sedikit" (3 dtk) |
| T1 + T10 + T11 digabung | BAHAYA 75 | **Berhenti I-04**, 3 kartu (New Saphir, Komitrando, Dekayu) dengan kontak masing-masing (6 dtk). Memilih kartu Komitrando → AMAN 8 |
| Berita + "Tetap periksa" | — | AMAN 10, catatan "tidak dipakai di graf penipuan dan pencarian publik" |

Tangkapan layar kartu I-04 di produksi: `hasil/I04-kartu-intervensi.jpg`.

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

## Run 13 (27 Okt 2026 malam, stack home, validasi data LokerJogja)

Cache dimatikan (`VERIFY_CACHE_ENABLED=false`), model `ag/gemini-3.8-flash-medium`. Kode `75d5719`, tes otomatis 199 lulus. Set lengkap dijalankan dua kali (pass 1 dan pass 3); pass 2 dibuang karena LLM sedang tidak tersedia dan guard isi website belum ada saat itu.

| ID | Pass 1 | Pass 3 | Harapan | Catatan |
|---|---|---|---|---|
| LJ1 Malio Gelato | AMAN 18 | AMAN 15 | AMAN | |
| LJ2 PACC | AMAN 18 | AMAN 18 | AMAN | tautan LokerJogja |
| LJ3 Morgans Kebab | AMAN 18 | AMAN 18 | AMAN | poster |
| LJ4 Excelland | AMAN 24 | AMAN 20 | AMAN | |
| LJ5 Al-Kautsar | AMAN 15 | AMAN 18 | AMAN | |
| V1 Envipedia | AMAN 20 | AMAN 20 | AMAN | PT memakai WA tidak dihukum |
| F1 New Trendy | WASPADA 65 | BAHAYA 78 | ≥ WASPADA 45 | isi situs "akun kerja"/tugas; guard WASPADA 55 |
| F2 Guardian | WASPADA 50 | WASPADA 50 | stabil | nomor 0 tag GetContact (+10); sebelumnya AMAN 28 / WASPADA 45 |
| F3 Sociolla | WASPADA 50 | WASPADA 55 | ≥ 45 | |
| F4 Roemah Boenga | WASPADA 45 | WASPADA 45 | ≥ 45 | domain tanpa DNS |
| F5 Sharp | WASPADA 55 | WASPADA 55 | ≥ 45 | `sharp-career.my.id` |
| TG1 (teks sintetis + Telegram) | WASPADA 65 | WASPADA 60 | ≥ 55 | baris "Aturan Pengaman: Lamaran via Telegram" |
| TG2 (= T5 Adaro) | WASPADA 72 | WASPADA 72 | tidak turun | |
| T1 / T9 / T10 / T11 (asli) | 12 / 25 / 6 / 22 | 12 / 25 / 7 / 24 | AMAN | |
| T3 (penipuan) | BAHAYA 95 | BAHAYA 95 | BAHAYA | |
| T2, T4–T8 (abu-abu/penipuan) | 50–74 | 45–74 | WASPADA | |
| P1 | AMAN 25 | AMAN 28 | regresi | |

Kesimpulan: 6/6 lowongan asli AMAN, 5/5 poster palsu ≥ WASPADA 45, Telegram ≥ WASPADA 55, dan regresi T1–T11/P1 tetap.

Dua bug ditemukan saat run ini:
- F1 sempat AMAN 12 ketika LLM gagal dan penilaian aturan tidak memakai isi website. Guard "Isi Website Penipuan" sekarang berlaku di jalur LLM maupun fallback; F1–F5 diuji ulang dua putaran: 65/78, 52/50, 55/52, 45/45, 52/55.
- T11 sempat WASPADA 42 karena `spamInfo.degree = "green"` dibaca sebagai spam. Hanya `type` spam/scam/fraud atau degree merah/oranye yang dihitung sekarang.

## Run 14 (28 Okt 2026 dini hari, stack home, uji ulang oleh Claude)

Kode `75d5719`, cache mati, `ag/gemini-3.8-flash-medium`, dua pass penuh. Tambahan kasus: TG3 (Telegram + "dijamin bukan penipuan"), TG4 ("chat Tele: @…"), S1 (NIK + rekening + biaya seragam, sintetis).

| ID | Pass A | Pass B |
|---|---|---|
| LJ1–LJ5 | AMAN 16/18/18/20/18 | AMAN 18/18/18/18/18 |
| V1 | AMAN 20 | AMAN 18 |
| F1–F5 | WASPADA 65/50/52/45/58 | WASPADA 65/50/50/45/60 |
| TG1 / TG3 / TG4 | WASPADA 65/65/70 | WASPADA 68/65/70 |
| S1 | BAHAYA 90 | BAHAYA 90 |
| T1 / T9 / T10 / T11 / P1 | AMAN 12/28/8/24/25 | AMAN 12/25/8/20/28 |
| T3 | BAHAYA 95 | BAHAYA 95 |
| T2, T4–T8 | WASPADA 50/73/73/72/45/72 | WASPADA 50/73/74/70/45/72 |

Semua lowongan asli AMAN dan semua poster palsu ≥ WASPADA 45, tetapi belum ada poster palsu LokerJogja yang BAHAYA. Data sensitif S1 tidak muncul di respons. Blind spot yang ditemukan diperbaiki dan diuji di run 15 di bawah.

## Run 15 (28 Okt 2026, stack home, kode akhir)

Kode `7af2fd5` dan sesudahnya (perubahan sesudahnya hanya komentar, proxy timeout, dan trim pencarian). Cache mati, `ag/gemini-3.8-flash-medium`, dua pass penuh (A/B) ditambah satu pass konfirmasi (C) setelah perbaikan kasus negatif N1. 220–229 tes otomatis lulus.

Perubahan yang diuji:
- **Pencatutan merek.** Domain resmi dicari dari hasil pencarian (skor generik + umur domain) atau dari registri terverifikasi `app/data/employer_domains.json`. Lamaran walk-in di alamat fisik membatalkan aturan ini.
- **Daftar jenis situs** dipindah ke `app/data/site_kinds.json`.
- **Tautan pendek** dibuka, termasuk yang hanya terbaca AI dari gambar. Judul dan `og:description` situs ikut dicocokkan.
- **Regex Telegram** sekarang menangkap "tele"/"tg" dan negasi palsu ("dijamin bukan penipuan").
- **Masking** mencakup rekening tanpa kata "rekening", bank digital, NIK berspasi, dan nama pemilik rekening.
- **Isi tag GetContact** dibaca maksimal 1/hari; yang keluar hanya hitungan kata penipuan.
- **Frontend home** sekarang same-origin ke backend home (sebelumnya diam-diam memanggil API produksi).

| ID | Pass A | Pass B | Pass C (kode akhir) |
|---|---|---|---|
| LJ1–LJ5 (tayang di LokerJogja) | AMAN 18/18/18/18/18 | AMAN 18/20/18/18/18 | AMAN 16/18/18/20/18 |
| V1 Envipedia | AMAN 22 | AMAN 25 | AMAN 22 |
| F1 New Trendy | BAHAYA 82 | BAHAYA 82 | BAHAYA 80 |
| F2 Guardian | WASPADA 68 | WASPADA 68 | WASPADA 68 |
| F3 Sociolla | WASPADA 68 | WASPADA 68 | WASPADA 68 |
| F4 Roemah Boenga | WASPADA 45 | WASPADA 45 | WASPADA 45 |
| F5 Sharp | WASPADA 68 | WASPADA 68 | WASPADA 68 |
| N1 cabang ritel + Gmail + walk-in (negatif) | WASPADA 68 | WASPADA 68 | **AMAN 25** (setelah perbaikan) |
| TG1 / TG3 / TG4 (Telegram) | WASPADA 65/65/70 | WASPADA 65/65/70 | – |
| S1 / S2 (NIK, rekening, biaya) | BAHAYA 92/90 | BAHAYA 92/90 | – |
| T1, T9, T10, T11, P1 (asli) | AMAN 12/25/8/22/28 | AMAN 12/25/8/22/28 | T11 AMAN 22 |
| T3 | BAHAYA 95 | BAHAYA 96 | – |
| T2, T4–T8 | WASPADA 50/74/73/72/45/72 | WASPADA 50/73/73/70/45/72 | – |

Kesimpulan:
- **Lowongan asli:** 12/12 AMAN di pass akhir (LJ1–LJ5, V1, T1, T9–T11, P1, N1).
- **Poster yang ditolak LokerJogja:** 5/5 ≥ WASPADA 45. F1 BAHAYA. F2, F3, dan F5 WASPADA 68 dengan baris "Aturan Pengaman: Pencatutan Merek".
- **Telegram:** semua kasus kena aturan pengaman. TG3 dan TG4 sekarang tertangkap regex, bukan hanya oleh LLM.
- **Data sensitif:** NIK, rekening, dan nama pemilik rekening tidak muncul di respons maupun DB.
- **Stabilitas:** variasi antar-pass ≤ 3 poin.

F2, F3, dan F5 tidak dinaikkan ke BAHAYA karena tidak ada bukti keras di poster. Jalur naiknya adalah ≥ 2 tag GetContact berkata penipuan, nomor terlapor, atau laporan komunitas.
