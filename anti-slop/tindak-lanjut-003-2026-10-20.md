# Tindak lanjut audit 003 (laporan, kevalidan data, prompt, Lightpanda)

Tanggal: 20 Okt 2026. User menyetujui semua nomor 1–28. Semua sudah dikerjakan, di-push ke `main` dan `hafidz`, lalu dideploy ke `verifin.web.id`. Atas permintaan user, `job_cases` tidak dikosongkan; run ulang memperbarui baris yang sama.

| No | Status | Ringkasan |
|---|---|---|
| 1, 4, 7 | Selesai | `EvidencePanel` ditulis ulang. Badge mode dibuang, label berbahasa Indonesia, umur domain "14 tahun (terdaftar …)", kartu datar tanpa gradien, teks ≥12px. |
| 2, 16 | Selesai | Kecocokan token lokasi kini jadi satu catatan netral, bukan sinyal aman per hasil. |
| 3 | Selesai | Kartu "Lokasi Terverifikasi" dihapus dari Bukti OSINT. Lencana lokasi: Titik presisi / Tempat usaha di peta / Tingkat jalan / Hanya wilayah/kode pos. |
| 5, 17 | Selesai | Kartu peta ganda dihapus; satu angka hasil web dipakai di semua tempat. |
| 6, 18 | Selesai | Saringan ringkasan menangani "valid", dan frasa "email resmi perusahaan" tidak lagi rusak. |
| 8 | Selesai | Badge angka rekomendasi `aria-hidden`. |
| 9 | Selesai | Label atribusi: "Nomor Alamat Belum Pasti di Peta". |
| 10 | Catatan | "Penyesuaian Penalaran AI" tetap; siapkan jawaban untuk tanya jawab. |
| 11 | Selesai | `osint_failed` kini mendeteksi pencarian/probe `UNAVAILABLE`/`TIMEOUT`, dan hasil seperti itu tidak dipakai sebagai cache. Terbukti saat pre-run: Lowongan 1 sempat gagal di cek hoaks, lalu diulang otomatis sampai bersih. |
| 12, 24 | Selesai | Geocoder: nama usaha (lengkap dan pendek) + wilayah, 5 kandidat, utamakan ruas jalan, tanpa POI acak; usaha harus berada di wilayah alamat. Lowongan 1 kini tepat di POI "Komitrando" (sebelumnya meleset 0,36 km). |
| 13, 19 | Selesai | Prompt alamat mengikuti `match_level` apa adanya; tingkat `area` dilarang disebut jalan terkonfirmasi. |
| 14 | Selesai | Hash cache menormalkan spasi; baris dengan hash lama diperbarui di tempat. Baris duplikat lama `70530a53` (Komitrando) **masih ada**, menunggu izin user untuk dihapus. |
| 15 | Selesai | Gaji di-dedupe berdasarkan angka. |
| 20, 21 | Selesai | Prompt disusun ulang (DATA, BUKTI OSINT, ATURAN, BAND SKOR, URUTAN, FORMAT). Aturan "Kaspersky gagal = aman" dihapus. |
| 22 | Selesai | Query cek hoaks baru: "lowongan <nama> hoaks penipuan". Peringatan dihitung bila kata peringatan ada di judul atau "mengatasnamakan/mencatut <nama>" ada di snippet. Aturan band: bantahan + kanal WhatsApp/bio → minimal WASPADA 60–74, walau tanpa Persero/Tbk. |
| 23 | Selesai | `official` hanya untuk host yang sama dengan domain email/link lowongan. |
| 25 | Selesai | Varian bahasa halaman (booking.com `.id.html`/`.html`) dihitung sekali. |
| 26 | Selesai | Akun medsos yang ditemukan lewat pencarian nama ditandai `found_by_name_only`; prompt dan halaman menyebut akun itu bukan bukti lowongan asli. |
| 27 | Selesai | `/cases/{id}` tidak lagi mengirim `osint_summary`, `llm_output`, dan `raw_text_hash`. |
| 28 | Selesai | Lightpanda dihapus (modul, config, env, dokumentasi, dan cabang fallback). |

## Bug yang ketemu saat uji ulang dan sudah diperbaiki

- "Jalan Batu Saphir" (Jakarta) dan SPBU "Pertamina 44 543 21" (Lampung) sempat dianggap tempat usaha. Pencocokan usaha kini menolak jalan/wilayah dan mewajibkan wilayah yang sama.
- Cek hoaks awalnya tidak menemukan bantahan Pertamina karena mewajibkan kata "persero". Kini cukup kata merek utama.
- Kecocokan tingkat wilayah sempat menampilkan nama jalan acak. Kini hanya kelurahan, kota, dan kode pos.

## Verifikasi

- Backend: 101 tes lulus. Frontend: `tsc`, `eslint`, dan `next build` bersih.
- Uji ulang 14 lowongan di produksi (run 6–7, `test/okt-2026/README.md`): 6/6 scam ditandai (T3 BAHAYA 95; lima lainnya WASPADA 45–73), 6/6 asli AMAN (12–30).
- Pre-run 4 lowongan form tersimpan tanpa pemeriksaan gagal dan keluar dari cache dalam 0,5 detik: Lowongan 1 AMAN 12, Lowongan 2 BAHAYA 95, Lowongan 3 AMAN 12, Lowongan 4 WASPADA 72.
- Tampilan baru halaman laporan belum dicek ulang di browser produksi.
