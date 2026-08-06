# 🛡️ Analisis Kebutuhan Arsitektur Database & Caching: Verifin Engine

Laporan ini menganalisis urgensi penggunaan **Redis**, **pgvector**, dan **Neo4j** pada proyek **Verifin** untuk tahap pengembangan saat ini (MVP/Eksperimen Kompetisi Gemastik 26) dibandingkan dengan kebutuhan jangka panjang.

---

## 📊 Ringkasan Rekomendasi Cepat

| Teknologi | Status Saat Ini | Kegunaan Potensial | Urgensi Tahap Ini (MVP/Gemastik) | Rekomendasi Aksi |
| :--- | :--- | :--- | :--- | :--- |
| **Redis** | Belum di-import / digunakan di kode. | Caching API OSINT (WHOIS, OSM, Kredibel) & Background Jobs. | **Sedang** | **Nonaktifkan sementara** di lokal untuk hemat RAM, tapi **implementasikan caching sebelum demo** agar loading cepat. |
| **pgvector** | Dideklarasikan di `JobCase` tapi belum diisi data. | *Semantic Search* loker serupa / duplikat template scam. | **Tinggi (Wow Factor)** | **Pertahankan.** Tambahkan fungsi embedding ringan (mis. SentenceTransformers atau API) untuk mencocokkan kemiripan teks loker. |
| **Neo4j** | Belum digunakan di kode sama sekali. | Analisis graf untuk mendeteksi jaringan/sindikat pelaku fraud. | **Rendah** | **Hapus / Matikan.** Menghabiskan banyak RAM (>1-2GB) dan berisiko *over-engineering* kecuali ada halaman visualisasi graph. |

---

## 🔍 Pembahasan Mendalam per Komponen

### 1. Redis (Caching & Performance)
* **Mengapa ini ada?** Ditambahkan di [docker-compose.yml](file:///Users/matthewpriantara/Documents/Code/competition_project/gemastik26/verifin-app/backend/app/database/docker-compose.yml) sebagai penyedia key-value store cepat.
* **Analisis Kebutuhan:** 
  * Proses verifikasi Verifin saat ini melakukan scrape ke **Kredibel**, memvalidasi alamat ke **OpenStreetMap**, dan mengecek **WHOIS**. Proses live OSINT ini memakan waktu (bisa 5-15 detik) dan rentan terkena *rate limit* jika diuji berulang kali.
  * **Di tahap development:** Kamu belum memakainya, jadi tidak krusial.
  * **Di tahap demo juri:** Sangat penting. Juri tidak suka menunggu loading lama saat demo produk. Dengan Redis, pencarian terhadap entitas (misal nomor telepon atau domain yang sama) yang pernah dicek sebelumnya akan instan (<0.1 detik).
* **Aksi:** Nonaktifkan di docker-compose untuk menghemat RAM saat coding, namun pasang cache sederhana di backend (misal untuk cache fungsi OSINT) sebelum finalisasi demo.

### 2. pgvector (Semantic Search & Duplicate Detection)
* **Mengapa ini ada?** Kolom `embedding` didefinisikan pada model [JobCase](file:///Users/matthewpriantara/Documents/Code/competition_project/gemastik26/verifin-app/backend/app/database/models.py#L41) menggunakan pustaka `pgvector`.
* **Analisis Kebutuhan:**
  * Sindikat penipuan loker sering kali menggunakan template kalimat yang sama secara berulang-ulang, hanya mengganti nama perusahaan palsu, email gratisan, atau nomor kontak.
  * Jika hanya mengandalkan pencarian eksak (*exact match*) di SQL biasa, pelaku bisa dengan mudah lolos hanya dengan mengganti satu digit nomor telepon.
  * Dengan **pgvector**, kamu bisa membandingkan makna kalimat (*semantic similarity*). Jika ada loker baru yang mirip 90% dengan loker scam yang pernah dilaporkan sebelumnya, sistem bisa langsung memberikan verdict **BAHAYA** secara instan tanpa perlu memanggil API LLM yang mahal.
* **Aksi:** **Sangat direkomendasikan untuk diimplementasikan.** Ini adalah salah satu poin *intelijen* yang bisa kamu pamerkan ke juri Gemastik sebagai bukti implementasi AI yang efisien.

### 3. Neo4j (Graph Database & Syndicate Mapping)
* **Mengapa ini ada?** Dikonfigurasi di [config.py](file:///Users/matthewpriantara/Documents/Code/competition_project/gemastik26/verifin-app/backend/app/config.py#L36) dan dideklarasikan di docker-compose.
* **Analisis Kebutuhan:**
  * Neo4j sangat baik untuk memetakan hubungan kompleks, misalnya: *"Nomor WA ini pernah dipakai di loker palsu PT X, yang websitenya menggunakan server IP yang sama dengan loker palsu PT Y."*
  * Namun, untuk mengimplementasikan ini, kamu harus menulis adapter graph database baru, merancang skema node/edge, dan mempelajari bahasa query Cypher.
  * Jika di frontend ([frontend](file:///Users/matthewpriantara/Documents/Code/competition_project/gemastik26/verifin-app/frontend)) kamu tidak memiliki rencana untuk menampilkan **Visualisasi Graf Jaringan Sindikat Penipuan** yang interaktif, maka Neo4j **100% tidak terpakai** dan hanya menjadi beban resource sistem.
* **Aksi:** **Hapus/nonaktifkan dari docker-compose.** Kamu bisa menghemat memory RAM Docker laptop kamu sebesar 1-2 GB.

---

## 🛠️ Panduan Perubahan Praktis

Jika kamu memutuskan untuk menyederhanakan arsitektur database agar laptop lebih enteng selama pengembangan, berikut rekomendasi perubahan pada konfigurasi Docker kamu:

### A. Penyederhanaan [docker-compose.yml](file:///Users/matthewpriantara/Documents/Code/competition_project/gemastik26/verifin-app/backend/app/database/docker-compose.yml)
Kamu bisa mematikan service `neo4j` dan membiarkan `redis` (jika ingin diimplementasikan nanti) atau mematikan keduanya terlebih dahulu. Contoh konfigurasi minimalis:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: verifin-postgres
    ports:
      - "5432:5432"
    environment:
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-postgres}
      POSTGRES_DB: ${DB_NAME:-verifin_db}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always

  # Redis bisa di-comment dulu jika belum dipakai sama sekali
  # redis:
  #   image: redis:7-alpine
  #   container_name: verifin-redis
  #   ports:
  #     - "6379:6379"
  #   volumes:
  #     - redis_data:/data
  #   restart: always

volumes:
  postgres_data:
```

### B. Langkah Pengembangan Selanjutnya
1. **Fase Sekarang (Development):** Jalankan PostgreSQL saja. Pastikan inisialisasi [init_db.py](file:///Users/matthewpriantara/Documents/Code/competition_project/gemastik26/verifin-app/backend/scripts/init_db.py) berjalan mulus untuk mengaktifkan ekstensi `vector` pada Postgres.
2. **Implementasi pgvector (Wow Factor):** Buat fungsi utilitas di backend untuk men-generate embedding menggunakan library ringan seperti `sentence-transformers` (bisa jalan lokal di CPU dengan model kecil seperti `all-MiniLM-L6-v2`) atau API embedding gratisan, lalu simpan ke kolom `embedding` setiap kali ada verifikasi baru.
3. **Optimasi Presentasi (Caching):** Dekatkan jadwal final kompetisi, aktifkan kembali Redis untuk mencache hasil request API eksternal (OSM, Kredibel, WHOIS) agar waktu loading saat juri mencoba demo terasa instan.
