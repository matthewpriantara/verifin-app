# Tindak lanjut 006

Tanggal: 20 Okt 2026 (malam). User: "Kerjakan semua". Semua 58 nomor audit-006 dikerjakan, ditambah satu temuan baru (no. 59) yang muncul saat perbaikan.

Status akhir: di-commit, di-push (main + hafidz), dan dideploy ke produksi (`0ce41d9`). Lihat bagian "Setelah deploy" di bawah.

**Verifikasi:**
- Backend: 127 tes lulus (105 lama + 22 regresi baru di `tests/test_audit006.py`); coverage 39%.
- Frontend: `tsc`, `eslint`, dan `next build` bersih.
- Uji skenario S1–S10 diulang di backend lokal tanpa database.
- Halaman laporan S4 dicek di browser.

## Yang diubah per nomor

| No | Perbaikan | File utama |
|---|---|---|
| 1 | `safe_get` / `resolve_public_url`: setiap URL dan setiap lompatan redirect divalidasi ke alamat publik. Dipakai di pembuka website, inspector form, pengambil tautan, dan unduhan gambar. Tautan internal berstatus `SKIPPED` dan tidak tampil di laporan. | `services/url_guard.py`, `osint/web_evidence.py`, `osint/gform_inspector.py`, `web_fetcher.py` |
| 2 | `/cases/lookup/by-entity` khusus admin; input LIKE di-escape (`like_escape`), juga di `/cases/search`. | `api/v1/verify/router.py`, `services/case_search.py` |
| 3 | Nomor laporan komunitas dicocokkan dalam format `+628…` (baris lama tanpa `+` ikut dicocokkan); nama perusahaan dicocokkan juga tanpa PT/Persero. | `api/v1/verify/pipeline.py` |
| 4 | Pencocokan nama memperhatikan urutan kata per bidang (URL, judul, cuplikan). Kata sama yang tertukar dianggap entitas lain; jenis usaha ("Hotel", "Toko") bebas posisi. | `osint/search_intelligence.py`, `osint/web_evidence.py` |
| 5 | Kalibrasi "pencarian kosong" tidak berlaku bila teks memuat sinyal kuat (biaya, luar negeri, pencatutan BUMN, pemberi kerja anonim). Fallback berbasis aturan memakai sinyal teks, laporan komunitas, riwayat kasus, dan artikel bantahan, serta tidak lagi mengklaim Kaspersky diperiksa bila tidak ada nomor. | `llm/verifin_reasoning.py` |
| 6 | Kunci cache URL mempertahankan parameter isi (`story_fbid`, `v`) dan membuang parameter pelacak; pencocokan persis, bukan awalan; `/verify/url` dengan teks tambahan tidak memakai cache. `CACHE_SCHEMA_VERSION` 13 → 14. | `services/db_cache.py`, `router.py` |
| 7 | SearXNG membedakan `empty` (semua engine menjawab, nol hasil) dari gagal. Pencarian kosong berstatus `NO_RESULTS`, bukan `UNAVAILABLE`, sehingga tidak lagi menandai kasus `osint_failed`. | `osint/searxng_client.py`, `web_evidence.py`, `search_intelligence.py` |
| 8 | WHOIS gagal → `is_new: None`. Prompt menulis "umur tidak diketahui", bukan "domain sudah lama"; label ambang memakai 90 hari. | `osint/runner.py`, `llm/prompt_builder.py` |
| 9 | `is_gform_url` mencocokkan host, bukan substring; daftar shortlink ditambah (lynk.id, cutt.ly, dll.). | `osint/gform_inspector.py` |
| 10 | Lokasi luar negeri tidak dicari di peta Indonesia (dicatat `foreign_locations`). "KM", RT/RW, dan kode pos bukan nomor bangunan. Hasil exact menampilkan nama jalan, bukan nama POI lain. | `osint/runner.py`, `osint/address_validator.py` |
| 11 | Alamat dari pencarian web tidak lagi ditulis ke `entities.addresses`; setiap validasi alamat diberi `address_source` (`posting_address`, `location_candidate`, `web_search`). Laporan menjelaskan bila titik peta bukan dari lowongan; XAI dan prompt membedakannya. | `pipeline.py`, `runner.py`, `prompt_builder.py`, `shap_explainer.py`, `ReportPage.tsx` |
| 12 | Nominatim: kunci global 1 permintaan/detik, maksimal 8 query per alamat; satu query gagal tidak membuang hasil terbaik. | `osint/address_validator.py` |
| 13 | URL gambar bukti diarahkan ke `API_BASE` backend. | `modules/admin/ModerationTable.tsx` |
| 14 | Form laporan divalidasi dengan `CommunityReportIn` (panjang kolom), whitelist jenis laporan, nomor dan email dicek; error tanpa teks exception. | `api/v1/community/router.py`, `schema.py` |
| 15 | `/community/check` hanya menghitung laporan `approved`. | `community/router.py` |
| 16 | Kontribusi baru "Nama Pernah Dicatut Lowongan Palsu" (+15) dari `scam_check`; "Hasil pencarian menunjukkan penipuan" (+25) kini membaca hasil pencarian dan SERP nomor. | `xai/shap_explainer.py` |
| 17 | Judul "Perusahaan" memakai nama dari lowongan; chip "Ada di Google Maps", "Nomor tanpa laporan", dan "Ada jejak publik" berwarna netral; label nomor "Bersih" → "Tanpa laporan". | `ReportPage.tsx`, `lib/phone-status.ts` |
| 18 | Status situs: `AVAILABLE`, `HTTP_ERROR`, `NOT_FOUND`, `BLOCKED` (anti-bot), `UNREACHABLE`, `SKIPPED`. Hanya `NOT_FOUND`/`HTTP_ERROR` yang menjadi risiko ("+28 situs tidak dapat diakses"). | `web_evidence.py`, `shap_explainer.py`, `EvidencePanel.tsx` |
| 19 | Query builder mengabaikan "(Persero)"/"(Tbk)" sebagai merek. | `osint/query_builder.py` |
| 20 | Unggahan dibaca maksimal 20 MB + 1 byte; ekstensi sementara dari content-type. | `router.py` |
| 21 | Pesan error 500 generik; detail hanya di log. | `router.py`, `community/router.py`, `health/router.py` |
| 22 | `/health` hanya melaporkan SearXNG yang benar-benar dicek. | `health/router.py` |
| 23 | Label Kaspersky tidak dikenal → probe dianggap gagal, bukan "mencurigakan". | `osint/phone_validator.py` |
| 24 | Catatan nomor: "nomor yang muncul di hasil pencarian", bukan "nomor resmi". | `osint/runner.py` |
| 25 | `official_social_found` selalu false (tidak ada verifikasi resmi); Linktree ikut ditelusuri. | `osint/social.py`, `web_evidence.py` |
| 26 | Validator teks LLM mengabaikan email, domain, dan URL saat mendeteksi tanda baca rusak. | `llm/verifin_reasoning.py` |
| 27 | Token sesi admin `<kedaluwarsa>.<HMAC>`: kedaluwarsa 8 jam dicek server; mengganti password membatalkan semua sesi. | `lib/adminAuth.ts`, `api/admin/login/route.ts` |
| 28 | Stream SSE membuka sesi DB sendiri dan menutupnya di akhir. | `router.py` |
| 29 | `/check-domain` memakai rate limit verifikasi. | `router.py` |
| 30 | Tombol "Buka di Google Maps" memakai `buttonClass`. | `ReportPage.tsx` |
| 31 | Nomor dianggap milik penyebar hanya bila kalimatnya (plus satu kalimat sebelumnya dan dua baris di atasnya) memuat frasa promosi ("pasang loker", "mau dipromosikan", "admin grup"), bukan sekadar kata "admin". | `services/ner.py` |
| 32 | Tautan tanpa skema diekstrak (`bit.ly/…`, `forms.gle/…`, `www.…`, domain `.id/.com/…`), kecuali domain email gratisan; tautan wa.me/t.me tidak dibuka sebagai situs. | `services/ner.py`, `web_evidence.py` |
| 33 | `strip_negated_fee` membuang frasa penyangkalan ("tidak dipungut biaya…", "gratis biaya tes") sebelum mencari biaya, di classifier dan regex NER; jarak antarkata dibatasi satu kalimat. | `services/ner.py`, `nlp/classifier.py` |
| 34 | Riwayat kasus dan laporan komunitas digabung ke bukti sebelum LLM (`_merge_network`), punya bagian sendiri di prompt, dan dihitung sebagai bukti keras. | `router.py`, `prompt_builder.py`, `verifin_reasoning.py` |
| 35 | Form lapor punya kolom nomor WhatsApp dan email; isi otomatis dari kasus (nama, nomor, email, tautan); laporan boleh hanya berisi nomor. | `ReportJobPage.tsx` |
| 36 | Panel "Riwayat Verifin dan laporan komunitas" di bukti laporan: laporan disetujui, menunggu, kasus lain, entitas yang cocok, alert sindikat. | `EvidencePanel.tsx`, `types/verify.ts` |
| 37 | Email gratisan ditulis "domain tidak diperiksa", tanpa status SPF/DMARC palsu. | `EvidencePanel.tsx` |
| 38 | Negara tujuan pekerja migran ditambahkan ke sinyal kerja luar negeri. | `nlp/classifier.py` |
| 39 | Anggaran waktu penalaran 55 dtk (retry 2 per panggilan); bila habis, langsung ke penilaian aturan. | `llm/verifin_reasoning.py` |
| 40 | Gambar > 4000 px diperkecil; screenshot memanjang memakai sisi panjang 1600 px. | `services/ocr.py` |
| 41 | Empty state jejak digital membedakan "mesin pencari tidak terjangkau" dan "tidak ada nama perusahaan". | `ReportPage.tsx` |
| 42 | Gagal memuat laporan → pakai salinan `sessionStorage` bila `case_id` sama; pesan "belum bisa dimuat" dibedakan dari "tidak ditemukan". | `ReportPage.tsx` |
| 43 | `/cases/{id}` tidak lagi mengirim `raw_text_preview`. Nomor dan email tetap dikirim karena halaman laporan menampilkannya. | `router.py` |
| 44 | Prefill form lapor mengambil kasus lewat API, atau `sessionStorage` yang `case_id`-nya cocok. | `ReportJobPage.tsx` |
| 45 | Stream yang putus tanpa `done` menampilkan pesan koneksi terputus. | `VerifyBox.tsx` |
| 46 | "Entitas muncul di beberapa kasus" hanya bila ada kasus lain berverdict WASPADA/BAHAYA; deskripsi diperbaiki. | `shap_explainer.py` |
| 47 | `verdictLabel` AMAN → "Aman (tidak ada tanda bahaya)". | `lib/utils.ts` |
| 48 | Login admin: pesan sesuai status (429/500/salah), label tersembunyi, `autocomplete`; sesi 401 kembali ke login. | `AdminPage.tsx` |
| 49 | Modal admin `role="dialog"`, Escape, error tampil di dalam modal, tombol dikunci saat menyimpan; field nomor/email ditampilkan. | `ModerationTable.tsx` |
| 50 | Tab menjadi "Cari & saring kasus" dengan penjelasan jujur; IP palsu "-" dihapus; waktu dikonversi ke WIB. | `AdminPage.tsx` |
| 51 | Grafik dikelompokkan per tanggal WIB, diurutkan lama → baru; tahun ditampilkan bila lintas tahun. | `ReportChart.tsx` |
| 52 | Pagination riwayat memakai halaman aman; `/cari` di luar jangkauan menampilkan tautan kembali ke halaman 1. | `SearchHistory.tsx`, `SearchCasesPage.tsx` |
| 53 | `not-found` memakai `buttonClass`; collapse laporan ber-`aria-expanded`; semua input form lapor berlabel. | `not-found.tsx`, `ReportPage.tsx`, `ReportJobPage.tsx` |
| 54 | NER LLM membaca sampai 10.000 karakter. | `llm/entity_extraction.py` |
| 55 | Prompt tidak mengklaim SERP nomor berjalan bila tidak ada hasil. | `llm/prompt_builder.py` |
| 56 | `cost_of_error` dihapus dari respons. | `shap_explainer.py` |
| 57 | Halaman `/privasi` (isi sesuai alur data sebenarnya) + tautan di footer. | `app/privasi/page.tsx`, `Footer.tsx` |
| 58 | `types/phosphor.d.ts` dihapus; tipe bawaan paket dipakai (tsc bersih). | — |
| 59 (baru) | XAI "Form minta data sensitif" membaca field `requests_sensitive_data` yang tidak pernah diisi inspector, sehingga tidak pernah menyala. Sekarang membaca `has_phishing_signals` dan memisahkan form yang meminta biaya (+35). | `shap_explainer.py` |

## Hasil uji skenario setelah perbaikan

| ID | Sebelum | Sesudah | Catatan |
|---|---|---|---|
| S1 remote, nama fiktif | AMAN 25 | AMAN 24–28 | Nomor kini dicek. Jejak hanya dari perusahaan bernama persis sama (memang ada); jejak "Digital Kreasi Nusantara" tidak lagi dihitung |
| S2 biaya 150rb | BAHAYA 95 | BAHAYA 95 | Nomor dicek; jejak "Sinar Abadi Rejeki" tidak dihitung |
| S3 cabang Indomaret | AMAN 12, Titik Presisi warung | AMAN 15, tingkat jalan | Situs Cloudflare `BLOCKED` (netral); +15 nama pernah dicatut |
| S4 catut KAI + bit.ly | WASPADA 73, nomor & bit.ly hilang | WASPADA 65–73 | Nomor dicek; bit.ly diinspeksi; peta berlabel "kota penempatan" |
| S5 Glints | AMAN 25, Glints dibaca formulir | AMAN 22 | Glints dibuka sebagai situs; domain fiktif `NOT_FOUND` (+28) |
| S6 Jepang + biaya | BAHAYA 90, peta Kudus | BAHAYA 92 | +25 kerja luar negeri; Jepang tidak dipetakan |
| S7 tanpa nama | WASPADA 55, nomor hilang | WASPADA 55 | Nomor dicek |
| S8 URL internal | WASPADA 50, isi internal terbaca | WASPADA 50 | Tautan `SKIPPED`, tidak dibuka |
| S9 "tidak dipungut biaya" (baru) | label BAHAYA +40 (uji fungsi) | AMAN 8 | Tanpa kontribusi biaya |
| S10 forms.gle/bit.ly tanpa skema (baru) | tidak terbaca | AMAN 25 | Kedua tautan diinspeksi |

## Yang perlu dilakukan setelah deploy (butuh persetujuan)

1. **Commit dan push** `verifin-app` (main + hafidz), lalu build ulang backend dan frontend di fizualinux.
2. **Run 9 set uji 14 kasus.** `CACHE_SCHEMA_VERSION` naik, jadi semua kasus produksi dihitung ulang saat dikirim lagi (baris yang sama diperbarui, `case_id` tetap). Angka di Laporan Akhir (Tabel uji-okt, tangkapan layar) dan contoh T4 di beranda (`HomePage.tsx`, `EXAMPLE_REPORT` + angka kontribusi) perlu disamakan dengan hasil run 9.
3. **Checklist admin** di `test/skema-fitur-2026-10-20.md` Bagian 4 dijalankan tim, karena login memakai password.
4. **Halaman Laporan Akhir.** Sebelum perubahan ini 33 halaman, sekarang 34. Panduan 2026 menyebut batas 30 halaman untuk proposal; untuk laporan akhir tidak ada batas tertulis. Perlu keputusan tim apakah tetap dipangkas ke 30.

## Setelah deploy (20 Okt 2026, malam)

User: "Langsung saja commit push lalu jalankan ulang, dan test semua skema fitur".

- **Commit:** `85268e2` (backend), `0124bc9` (frontend), `f14ee19` (dokumen), lalu dua perbaikan dari run 9: `f5be179` dan `0ce41d9`. Semua di-push ke main dan hafidz, lalu dideploy ke fizualinux.
- **Run 9:** seluruh 14 kasus dijalankan di produksi. 6/6 penipuan ditandai, 6/6 lowongan asli AMAN, durasi 15–52 dtk. Detail di `test/okt-2026/README.md`.

### Temuan baru dari run 9 (diperbaiki)

| No | Temuan | Perbaikan |
|---|---|---|
| 60 | Kota penempatan "Wilayah Kerja PT. Pos Indonesia (Persero)" dipetakan ke Tuban, dan "Indonesia" ke titik tengah negara | Wilayah yang memuat nama badan usaha, "seluruh", atau hanya "Indonesia" tidak dipetakan; hasil geocode setingkat negara dibuang (`runner.py`, `address_validator.py`) |
| 61 | "Kirim CV terbaik Anda" terbaca sebagai badan usaha CV (muncul saat LLM sempat error 520) | CV harus diikuti kata berhuruf kapital/angka; kata "terbaik", "lengkap", "kamu" dikecualikan (`ner.py`) |
| 62 | Regresi no. 31: nomor T3 hilang karena baris di atasnya menyebut "admin grup" | Baris di atas hanya dipakai bila baris nomor itu bukan kalimat rekrutmen (`ner.py`) |

Setiap temuan diberi tes regresi; total 130 tes lulus.

### Uji skema fitur di produksi

| Fitur | Hasil |
|---|---|
| Health, `/docs`, semua halaman (`/`, `/cari`, `/report-job`, `/admin`, `/privasi`, laporan, 404) | OK |
| Verifikasi teks, gambar (P1), tautan stream (L1); cache 0,5 dtk | OK |
| Validasi input: teks pendek 422, tipe gambar 400, URL internal ditolak | OK |
| Cari: nama, nomor, tautan; `%` ditolak sebagai terlalu pendek | OK |
| `/cases/{id}` tanpa teks mentah | OK |
| Endpoint admin tanpa sesi/token (cases, lookup, proxy, login salah) | 401 semua |
| Form lapor: panjang kolom, jenis laporan, dan format nomor divalidasi (422); laporan nyata nomor T3 tersimpan *pending* | OK |
| `/community/check` publik hanya menghitung laporan yang disetujui | OK (0) |
| Pencocokan nomor laporan ke verifikasi | OK: T3 menampilkan "1 laporan menunggu tinjauan admin" |
| Laporan T3 di browser: panel riwayat & komunitas, kontribusi "Nama pernah dicatut", reputasi nomor | OK |
| Login admin dengan password, moderasi, gambar bukti | **Belum**: login memakai password tim, dijalankan tim sesuai checklist di `test/skema-fitur-2026-10-20.md` Bagian 4 (termasuk menyetujui atau menolak laporan T3) |
