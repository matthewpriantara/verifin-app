# Tindak lanjut audit 004 (section "Cara Verifin menilai risiko")

Tanggal: 20 Okt 2026. User meminta section ini dirombak dengan animasi yang menarik tapi ringan; semua nomor dikerjakan.

| No | Status | Yang diubah |
|---|---|---|
| 1 | Selesai | Langkah 02 kini "Tujuh pemeriksaan…" dan menyebut artikel bantahan atas nama perusahaan. |
| 2 | Selesai | Kartu tidak lagi template ikon-kotak seragam. Rail hero menjawab "cara pakai"; section ini menjawab "apa yang diperiksa" dengan contoh nyata, jadi tidak mengulang pesan. |
| 3 | Selesai | Tiap kartu memuat contoh dari laporan nyata T4 (run 8): yang terbaca, artikel Komdigi yang ditemukan, hasil pencocokan, WASPADA 73 dengan tiga kontribusi bukti. Tautan "Lihat laporan lengkapnya" ke `/report/1ec34af5…`. |
| 4 | Selesai | Kilau garis tanpa henti diganti rail yang terisi bergiliran 01 → 04 (interval 2,6 dtk). Hanya jalan saat section terlihat (IntersectionObserver) dan tab aktif, berhenti saat kursor di atas kartu. Gerakan hanya `transform` dan warna; framer-motion tidak dipakai di section ini. Reduce Motion: giliran tetap jalan, isian garis dan putaran ikon mati (`motion-reduce`). |
| 5 | Selesai | Efek hover border palsu dihapus; sorotan kartu mengikuti langkah aktif. Nomor ganda di kartu dihapus (nomor cukup di rail), kotak contoh tidak lagi bergaris putus-putus dan tidak ditarik setinggi kartu. |
| 6 | Selesai | Ikon `Cpu` diganti `Gauge`. |
| 7 | Selesai | Chip dipangkas: "Entity Extraction" (duplikat Hybrid NER), "Fraud Graph", "Evidence Attribution" dihapus; "Web & Social" diganti "SearXNG". |

Verifikasi: `tsc` dan `eslint` bersih; tangkapan desktop 1440 dan HP 375 (lebar gulir = lebar layar). Dark mode belum dicek.
