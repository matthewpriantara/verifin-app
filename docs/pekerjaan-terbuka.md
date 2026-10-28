# Pekerjaan terbuka di luar kode

Semua temuan audit kode Oktober 2026 sudah dikerjakan dan diuji (run 15, TestSprite; hasil di
`test/okt-2026/README.md`). Yang tersisa di bawah ini tidak bisa diselesaikan dengan kode saja.

| Item | Pemilik | Yang dibutuhkan |
|---|---|---|
| Kalibrasi bobot skor dengan data berlabel | Tim + LokerJogja.id | Izin tertulis LokerJogja untuk memakai daftar loker yang mereka tolak/terima. Setelah ada, isi juga `backend/app/data/employer_domains.json` dari perusahaan yang lolos validasi mereka |
| Kebijakan retensi data (`job_cases`, cuplikan teks) | TEDI SV UGM | Keputusan berapa lama kasus disimpan; halaman `/privasi` lalu diperbarui |
| Uji ulang pemahaman "AMAN bukan jaminan" | Tim | Responden baru (uji sebelumnya 64% paham) |
| Rotasi kunci API TestSprite | Tim | Setelah penjurian; kunci hanya ada di `~/.claude.json` milik tim, tidak di repo |
| Ganti model produksi ke Gemma sebelum penjurian | Tim | Sesuai keputusan 27 Okt; vision tetap Gemini |

## Keputusan desain yang sengaja dipertahankan

- **BAHAYA tetap butuh bukti keras.** Contohnya permintaan biaya/KTP/rekening, nomor terlapor, minimal 2 tag GetContact berkata penipuan, laporan komunitas, atau entitas di graf penipuan. Poster pencatutan merek tanpa bukti keras berhenti di WASPADA 68.
- **Kontak HP/email yang hanya terbaca AI dari gambar tidak dicek ke GetContact/Kaspersky.** Salah baca AI bisa membuat Verifin memeriksa nomor orang lain. Tautan pendek tetap dibuka, karena membukanya tidak mengirim data pribadi.
- **Isi tag GetContact dibaca maksimal 1 nomor per hari.** Yang keluar dari layanan home hanya hitungan dan kata dari daftar tetap; teks tag dan nama pemilik tidak pernah disimpan.
- **GetContact di produksi lewat reverse SSH tunnel home → VPS (unix socket).** Bila home mati, sinyalnya `UNAVAILABLE` dan skor tidak berubah. Lihat `infra/getcontact-api/README.md`.
