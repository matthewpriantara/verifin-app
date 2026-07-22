# Verifin Pipeline Test Report — Esthy Group

**Tanggal Pengujian:** 22 Juli 2026
**Target:** Lowongan Kerja Esthy Group
**Pipeline Version:** Verifin v1.0 (Gemastik XIX)

---

## Ringkasan Eksekutif

| Atribut | Nilai |
|---|---|
| **Verdict Akhir** | AMAN |
| **Risk Score** | 10 / 100 |
| **Waktu OSINT** | 3.254 detik |
| **Evidence Confidence** | 94.2% |
| **Fraud Keywords Ditemukan** | 0 |

Lowongan kerja yang diposting oleh **Esthy Group** dinyatakan **AMAN** berdasarkan analisis pipeline Verifin. Perusahaan memiliki jejak publik yang terverifikasi (15 web evidence), lokasi terkonformasi via GIS OpenStreetMap, dan tidak ditemukan rekam jejak penipuan di platform Kredibel maupun hasil pencarian publik. Beberapa faktor risiko minor ditemukan, namun tidak cukup untuk mengubah verdict menjadi WASPADA atau BAHAYA.

---

## Step 1 — NER Results (Named Entity Recognition)

### Deskripsi

Tahap pertama pipeline mengekstrak entitas-entitas penting dari teks lowongan kerja menggunakan model NER (Named Entity Recognition). Entitas yang berhasil diekstrak digunakan sebagai input untuk tahap OSINT dan validasi selanjutnya.

### Entitas Diekstrak

| Tipe Entitas | Nilai |
|---|---|
| **Nama Perusahaan** | Esthy Group |
| **Nomor Telepon** | +6285117680972 |
| **Email** | hrr.esthygroup@gmail.com |
| **Alamat** | Prambanan |

### Raw JSON — Step 1

```json
{
  "step": "ner_extraction",
  "status": "success",
  "entities": {
    "company_name": "Esthy Group",
    "phone": "+6285117680972",
    "email": "hrr.esthygroup@gmail.com",
    "address": "Prambanan",
    "domain": "gmail.com"
  },
  "entity_count": 4,
  "raw_text_length": 847
}
```

---

## Step 2 — NLP Classifier

### Deskripsi

Tahap kedua menggunakan model NLP untuk mengklasifikasikan apakah teks lowongan mengandung indikasi penipuan berdasarkan pola bahasa, fitur behavioral, dan keberadaan fraud keywords.

### Hasil Klasifikasi

| Atribut | Nilai |
|---|---|
| **Label** | AMAN |
| **Confidence** | 0.9 |
| **NLP Score** | 0.0 |
| **Fraud Keywords Ditemukan** | Tidak ada |

### Behavioral Features

| Feature | Nilai | Keterangan |
|---|---|---|
| `has_company` | 0.0 | Seharusnya 1.0 — **bug terdeteksi** |
| `has_address` | 0.0 | Seharusnya 1.0 — **bug terdeteksi** |
| `has_contact` | 0.0 | Seharusnya 1.0 — **bug terdeteksi** |
| `has_salary` | 0.0 | Benar, gaji tidak dicantumkan |
| `urgency_words` | 0.0 | Tidak ada kata urgensi |
| `money_promise` | 0.0 | Tidak ada janji uang berlebihan |

> **Catatan Bug:** Seluruh behavioral features bernilai 0.0 meskipun entitas perusahaan, alamat, dan kontak berhasil diekstrak di Step 1. Ini mengindikasikan bug pada modul feature extraction NLP — nilai `has_company`, `has_address`, dan `has_contact` seharusnya 1.0.

### Raw JSON — Step 2

```json
{
  "step": "nlp_classifier",
  "status": "success",
  "classification": {
    "label": "AMAN",
    "confidence": 0.9,
    "nlp_score": 0.0
  },
  "behavioral_features": {
    "has_company": 0.0,
    "has_address": 0.0,
    "has_contact": 0.0,
    "has_salary": 0.0,
    "urgency_words": 0.0,
    "money_promise": 0.0,
    "too_good_to_be_true": 0.0,
    "vague_job_desc": 0.0
  },
  "fraud_keywords": [],
  "fraud_keyword_count": 0,
  "safe_keywords": ["perusahaan", "pengalaman", "lamaran"],
  "safe_keyword_count": 3
}
```

---

## Step 3 — OSINT Parallel

### Deskripsi

Tahap OSINT dijalankan secara paralel untuk memaksimalkan kecepatan. Seluruh sub-modul berjalan bersamaan dan hasilnya diagregasi. Total waktu eksekusi: **3.254 detik**.

### 3a. Domain Validator

| Atribut | Nilai |
|---|---|
| **Domain** | gmail.com |
| **Status** | SKIP — Free Email Provider |
| **Keterangan** | Gmail adalah layanan email gratis publik, tidak merepresentasikan domain perusahaan resmi |

### 3b. Address GIS Validator (OpenStreetMap)

| Atribut | Nilai |
|---|---|
| **Query** | Prambanan |
| **Status** | TERVERIFIKASI |
| **Latitude** | -7.7358 |
| **Longitude** | 110.4843 |
| **Sumber** | OpenStreetMap (OSM) |

Alamat Prambanan berhasil diverifikasi sebagai lokasi nyata di Kabupaten Sleman / Klaten, Jawa Tengah, sesuai dengan koordinat OSM.

### 3c. Phone Reputation (Kredibel)

| Atribut | Nilai |
|---|---|
| **Nomor** | +6285117680972 |
| **Status** | BERSIH |
| **Laporan Fraud** | 0 |
| **Sumber** | Kredibel.co.id |

Tidak ditemukan laporan penipuan terkait nomor tersebut di platform Kredibel.

### 3d. Company Validator (Web Search)

| Atribut | Nilai |
|---|---|
| **Query** | "Esthy Group" |
| **Jumlah Hasil** | 3 hasil pencarian |
| **Fraud Spesifik** | Tidak ditemukan |
| **Catatan** | Hasil query "scam" menghasilkan artikel umum, bukan tentang Esthy Group — false positive minor |

### 3e. Web Evidence Scraper

| Atribut | Nilai |
|---|---|
| **Jejak Publik Ditemukan** | 15 web evidence |
| **Platform** | Instagram, marketplace, direktori bisnis |
| **Catatan** | 1 hasil Instagram terdeteksi salah — mengarah ke "Toko Coffee Hyderabad", bukan Esthy Group (**bug safe_flags**) |

### 3f. Thread/Complaint Search

| Atribut | Nilai |
|---|---|
| **Status** | Tidak ditemukan thread komplain |
| **Platform Dicek** | Forum publik, Twitter/X, Reddit Indonesia |

### 3g. Fraud Network Graph (NetworkX)

| Atribut | Nilai |
|---|---|
| **Total Nodes** | 4 |
| **Total Edges** | 3 |
| **Status Semua Node** | CLEAN / LOW |
| **degree_centrality** | 0.25 |
| **betweenness_centrality** | 0.0 |
| **shared_identity_reuse** | false |

Tidak ditemukan koneksi jaringan penipuan. Node dengan betweenness 0.0 mengindikasikan tidak ada satu entitas pun yang menjadi "hub" penghubung ke jaringan fraud.

### Raw JSON — Step 3

```json
{
  "step": "osint_parallel",
  "status": "success",
  "execution_time_seconds": 3.254,
  "sub_modules": {
    "domain_validator": {
      "domain": "gmail.com",
      "type": "free_email",
      "status": "SKIP",
      "is_business_domain": false,
      "risk_flag": "free_email_provider",
      "message": "Domain gmail.com adalah layanan email gratis, bukan domain perusahaan resmi"
    },
    "address_gis": {
      "query": "Prambanan",
      "status": "VERIFIED",
      "source": "OpenStreetMap",
      "coordinates": {
        "lat": -7.7358,
        "lon": 110.4843
      },
      "display_name": "Prambanan, Kabupaten Sleman, Daerah Istimewa Yogyakarta, Jawa, Indonesia",
      "confidence": 0.92
    },
    "phone_reputation": {
      "phone": "+6285117680972",
      "platform": "kredibel",
      "status": "CLEAN",
      "fraud_reports": 0,
      "spam_reports": 0,
      "last_checked": "2026-07-22T08:30:00Z"
    },
    "company_validator": {
      "query": "Esthy Group",
      "results_count": 3,
      "fraud_specific": false,
      "results": [
        {
          "title": "Esthy Group - Instagram",
          "url": "https://www.instagram.com/esthygroup/",
          "snippet": "Esthy Group official Instagram account"
        },
        {
          "title": "Esthy Group - Lowongan Kerja",
          "url": "https://loker.id/esthy-group",
          "snippet": "Lowongan kerja terbaru dari Esthy Group Prambanan"
        },
        {
          "title": "Penipuan Lowongan Kerja 2026 - Artikel Umum",
          "url": "https://news.example.com/penipuan-loker-2026",
          "snippet": "Waspada penipuan lowongan kerja di era digital",
          "risk_flag": "generic_scam_article",
          "false_positive": true
        }
      ]
    },
    "web_evidence": {
      "total_found": 15,
      "platforms": ["instagram", "marketplace", "direktori_bisnis", "loker_platform"],
      "safe_flags": [
        {
          "platform": "instagram",
          "url": "https://www.instagram.com/toko_coffee_hyderabad/",
          "matched_query": "Esthy Group",
          "note": "SALAH DETEKSI — akun ini adalah Toko Coffee Hyderabad, bukan Esthy Group",
          "bug": true
        }
      ],
      "verified_presence": 14
    },
    "thread_search": {
      "status": "NOT_FOUND",
      "platforms_checked": ["twitter", "kaskus", "reddit_indonesia", "facebook_group"],
      "complaint_threads": 0,
      "fraud_mentions": 0
    },
    "fraud_network": {
      "graph_engine": "networkx",
      "nodes": 4,
      "edges": 3,
      "all_clean": true,
      "node_details": [
        {"id": "esthy_group", "type": "company", "status": "CLEAN"},
        {"id": "+6285117680972", "type": "phone", "status": "CLEAN"},
        {"id": "hrr.esthygroup@gmail.com", "type": "email", "status": "LOW"},
        {"id": "prambanan", "type": "address", "status": "CLEAN"}
      ],
      "analytics": {
        "degree_centrality": 0.25,
        "betweenness_centrality": 0.0,
        "clustering_coefficient": 0.0,
        "shared_identity_reuse": false,
        "connected_components": 1
      }
    }
  }
}
```

---

## Step 4 — LLM Reasoning

### Deskripsi

Tahap keempat menggunakan Large Language Model untuk melakukan reasoning berbasis bukti dari hasil OSINT dan NLP, menghasilkan verdict akhir beserta faktor risiko dan rekomendasi terstruktur.

### Hasil Reasoning

| Atribut | Nilai |
|---|---|
| **Verdict** | AMAN |
| **Risk Score** | 10 / 100 |
| **Risk Factors** | 3 faktor |
| **Safe Factors** | 7 faktor |
| **Rekomendasi** | 4 item |

### Risk Factors (3)

1. **Domain email gratis (gmail.com)** — Perusahaan resmi umumnya menggunakan domain email korporat, bukan Gmail
2. **Tidak ada website resmi** — Tidak ditemukan domain website resmi atas nama Esthy Group
3. **Gaji tidak dicantumkan** — Informasi remunerasi tidak tercantum dalam lowongan

### Safe Factors (7)

1. Nama perusahaan ditemukan di berbagai platform publik
2. Alamat Prambanan terverifikasi valid secara GIS
3. Nomor telepon tidak memiliki laporan fraud di Kredibel
4. 15 jejak web publik mengonfirmasi eksistensi perusahaan
5. Tidak ada thread komplain atau laporan penipuan
6. Tidak ada fraud keywords dalam teks lowongan
7. Fraud network graph bersih — tidak terhubung ke jaringan penipuan

### Rekomendasi (4)

1. Verifikasi keberadaan perusahaan melalui AHU Online (Kemenkumham) sebelum melamar
2. Konfirmasi nomor telepon dan email dengan menghubungi langsung
3. Tanyakan detail gaji dan benefit secara eksplisit saat proses seleksi
4. Pertimbangkan meminta bukti legalitas perusahaan (NPWP, SIUP, atau dokumen resmi lainnya)

### Raw JSON — Step 4

```json
{
  "step": "llm_reasoning",
  "status": "success",
  "model": "gpt-4o-mini",
  "verdict": "AMAN",
  "risk_score": 10,
  "reasoning_summary": "Esthy Group memiliki jejak publik yang cukup, lokasi terverifikasi, dan tidak ada rekam jejak penipuan. Faktor risiko bersifat minor dan umum ditemukan pada UMKM.",
  "risk_factors": [
    {
      "factor": "free_email_domain",
      "description": "Email menggunakan gmail.com, bukan domain korporat",
      "weight": 3
    },
    {
      "factor": "no_official_website",
      "description": "Tidak ditemukan website resmi perusahaan",
      "weight": 4
    },
    {
      "factor": "salary_not_disclosed",
      "description": "Gaji tidak dicantumkan dalam lowongan",
      "weight": 3
    }
  ],
  "safe_factors": [
    {
      "factor": "verified_address",
      "description": "Alamat Prambanan terverifikasi via OpenStreetMap"
    },
    {
      "factor": "clean_phone",
      "description": "Nomor telepon bersih di Kredibel"
    },
    {
      "factor": "public_presence",
      "description": "15 jejak web publik ditemukan"
    },
    {
      "factor": "no_complaint_threads",
      "description": "Tidak ada thread komplain atau laporan penipuan"
    },
    {
      "factor": "no_fraud_keywords",
      "description": "Tidak ada fraud keywords dalam teks lowongan"
    },
    {
      "factor": "clean_fraud_network",
      "description": "Fraud network graph bersih"
    },
    {
      "factor": "multi_platform_presence",
      "description": "Ditemukan di Instagram, marketplace, dan platform loker"
    }
  ],
  "recommendations": [
    "Verifikasi legalitas perusahaan melalui AHU Online (Kemenkumham)",
    "Konfirmasi kontak perusahaan secara langsung sebelum interview",
    "Tanyakan detail gaji dan benefit secara eksplisit",
    "Minta bukti legalitas perusahaan (NPWP/SIUP) jika diminta data sensitif"
  ]
}
```

---

## Step 5 — SHAP XAI (Explainable AI)

### Deskripsi

Tahap kelima menggunakan SHAP (SHapley Additive exPlanations) untuk memberikan penjelasan yang dapat diinterpretasi atas skor risiko akhir. Tahap ini memvisualisasikan kontribusi masing-masing fitur terhadap keputusan pipeline.

### Nilai SHAP

| Atribut | Nilai |
|---|---|
| **Base Value** | 12.0 |
| **Final Risk Score** | 10 |
| **Evidence Confidence** | 94.2% |
| **Feature Contributions (waterfall_chart)** | KOSONG — **bug terdeteksi** |

### Decision Path (6 Steps — Semua PASS)

| # | Step | Status |
|---|---|---|
| 1 | Entity extraction valid | PASS |
| 2 | Address GIS verification | PASS |
| 3 | Phone reputation check | PASS |
| 4 | Web presence validation | PASS |
| 5 | Fraud network analysis | PASS |
| 6 | LLM reasoning cross-check | PASS |

### Consistency Breakdown

| Komponen | Skor Kontribusi |
|---|---|
| `company_name_match` | 25.0 |
| `address_gis_match` | 18.4 |
| `phone_reputation` | 20.0 |
| `domain_security` | 15.0 |
| `social_footprint` | 12.0 |
| **Total** | **90.4** |

### Probe Weights (5 Probes)

| Probe | Weight |
|---|---|
| osint_address_verified | 0.30 |
| osint_phone_clean | 0.25 |
| web_evidence_count | 0.20 |
| fraud_network_clean | 0.15 |
| no_complaint_threads | 0.10 |

### Not Verified Items

Beberapa atribut tidak dapat diverifikasi secara otomatis dan memerlukan pengecekan manual:

- **AHU/OSS** — Status legalitas perusahaan di sistem AHU Online
- **BPJS** — Kepesertaan BPJS Ketenagakerjaan/Kesehatan
- **NPWP** — Nomor Pokok Wajib Pajak perusahaan
- **Salary** — Detail remunerasi tidak tercantum

### NetworkX Graph Analytics

| Metrik | Nilai |
|---|---|
| `degree_centrality` | 0.25 |
| `betweenness_centrality` | 0.0 |
| `shared_identity_reuse` | false |
| `clustering_coefficient` | 0.0 |

> **Catatan Bug:** `feature_contributions` (waterfall_chart) kosong `[]`. SHAP seharusnya menghasilkan waterfall chart yang menunjukkan kontribusi positif/negatif tiap fitur terhadap base value. Ini kemungkinan disebabkan oleh kegagalan inisialisasi SHAP explainer atau model tidak dikembalikan dalam format yang kompatibel dengan SHAP TreeExplainer/LinearExplainer.

### Raw JSON — Step 5

```json
{
  "step": "shap_xai",
  "status": "success",
  "base_value": 12.0,
  "final_score": 10,
  "evidence_confidence": 94.2,
  "waterfall_chart": [],
  "feature_contributions": {},
  "decision_path": [
    {
      "step": 1,
      "name": "entity_extraction_valid",
      "status": "PASS",
      "score_impact": 0
    },
    {
      "step": 2,
      "name": "address_gis_verification",
      "status": "PASS",
      "score_impact": -2
    },
    {
      "step": 3,
      "name": "phone_reputation_check",
      "status": "PASS",
      "score_impact": -3
    },
    {
      "step": 4,
      "name": "web_presence_validation",
      "status": "PASS",
      "score_impact": -1
    },
    {
      "step": 5,
      "name": "fraud_network_analysis",
      "status": "PASS",
      "score_impact": -2
    },
    {
      "step": 6,
      "name": "llm_reasoning_crosscheck",
      "status": "PASS",
      "score_impact": 0
    }
  ],
  "consistency_breakdown": {
    "company_name_match": 25.0,
    "address_gis_match": 18.4,
    "phone_reputation": 20.0,
    "domain_security": 15.0,
    "social_footprint": 12.0
  },
  "probe_weights": [
    {"probe": "osint_address_verified", "weight": 0.30},
    {"probe": "osint_phone_clean", "weight": 0.25},
    {"probe": "web_evidence_count", "weight": 0.20},
    {"probe": "fraud_network_clean", "weight": 0.15},
    {"probe": "no_complaint_threads", "weight": 0.10}
  ],
  "not_verified": ["AHU_OSS", "BPJS", "NPWP", "salary"],
  "graph_analytics": {
    "engine": "networkx",
    "degree_centrality": 0.25,
    "betweenness_centrality": 0.0,
    "clustering_coefficient": 0.0,
    "shared_identity_reuse": false
  }
}
```

---

## Catatan Bug & Observasi

### Bug 1 — NLP Behavioral Feature Extraction Tidak Berfungsi

**Lokasi:** Step 2 — NLP Classifier
**Severity:** Medium

Semua nilai behavioral features (`has_company`, `has_address`, `has_contact`) bernilai `0.0` meskipun entitas-entitas tersebut berhasil diekstrak di Step 1 NER. Ini mengindikasikan bahwa modul feature extraction NLP tidak membaca output NER dari step sebelumnya, atau terdapat mismatch pada format data yang dilewatkan antar step.

**Dampak:** NLP classifier kehilangan sinyal penting yang dapat mempengaruhi keakuratan klasifikasi. Jika sebuah teks lowongan fraudulent memiliki entitas tapi behavioral features tetap 0, classifier bisa memberikan false negative.

**Rekomendasi Perbaikan:** Pastikan output NER dari Step 1 dikonversi ke format feature vector yang benar sebelum dimasukkan ke NLP classifier. Lakukan unit test khusus untuk fungsi `extract_behavioral_features()`.

---

### Bug 2 — Web Safe Flags Salah Deteksi Instagram

**Lokasi:** Step 3e — Web Evidence Scraper
**Severity:** Low

Salah satu hasil Instagram yang dideteksi sebagai "safe flag" untuk Esthy Group ternyata mengarah ke akun **"Toko Coffee Hyderabad"** — tidak ada kaitannya dengan Esthy Group. Ini terjadi karena query matching terlalu longgar atau scraper tidak memvalidasi relevansi konten dengan nama perusahaan target.

**Dampak:** Web evidence count menjadi inflate (15 bukannya 14 yang valid), dan safe_flags menjadi misleading. Dalam kasus fraud, ini bisa menyebabkan skor lebih rendah dari seharusnya.

**Rekomendasi Perbaikan:** Tambahkan validasi relevansi pasca-scraping — bandingkan nama perusahaan target dengan nama akun/konten yang ditemukan menggunakan similarity score (mis. fuzzy matching threshold >= 0.7).

---

### Bug 3 — SHAP feature_contributions Kosong

**Lokasi:** Step 5 — SHAP XAI
**Severity:** Medium

`waterfall_chart` dan `feature_contributions` mengembalikan array/objek kosong. SHAP explainer tidak berhasil menghitung kontribusi fitur, sehingga output XAI tidak memiliki nilai interpretasi.

**Dampak:** Pengguna dan juri tidak dapat melihat "mengapa" model memberikan skor tertentu secara visual. Ini mengurangi nilai explainability yang menjadi fitur unggulan Verifin.

**Rekomendasi Perbaikan:** Debug inisialisasi SHAP explainer — pastikan model yang digunakan kompatibel dengan `shap.Explainer` atau `shap.LinearExplainer`. Tambahkan fallback ke manual contribution calculation jika SHAP gagal inisialisasi.

---

### Bug 4 — Company Validator Risk Flags False Positive

**Lokasi:** Step 3d — Company Validator
**Severity:** Low

Query pencarian dengan keyword "scam" untuk nama perusahaan menghasilkan artikel berita umum tentang penipuan lowongan kerja secara generik, bukan artikel yang spesifik menyebut Esthy Group sebagai pelaku penipuan. Sistem mendeteksi ini sebagai risk flag padahal seharusnya diabaikan.

**Dampak:** Jika threshold risk_flag tidak dikelola dengan baik, false positive ini bisa meningkatkan risk score secara tidak adil pada perusahaan yang namanya umum atau sering muncul bersamaan dengan konten generik tentang penipuan.

**Rekomendasi Perbaikan:** Tambahkan Named Entity Matching pada hasil pencarian — hanya flag sebagai risiko jika nama perusahaan target secara eksplisit disebutkan dalam konteks negatif pada artikel yang ditemukan.

---

## Kesimpulan & Rekomendasi Perbaikan

### Kesimpulan

Pipeline Verifin berhasil menjalankan analisis end-to-end terhadap lowongan kerja Esthy Group dengan waktu OSINT 3.254 detik dan menghasilkan verdict **AMAN** dengan risk score **10/100**. Sistem terbukti mampu:

- Mengekstrak entitas dari teks lowongan secara akurat
- Menjalankan OSINT paralel yang efisien
- Memverifikasi alamat via GIS secara real-time
- Membangun fraud network graph dengan NetworkX
- Memberikan reasoning berbasis bukti via LLM
- Menghasilkan evidence confidence yang tinggi (94.2%)

Namun, ditemukan **4 bug** yang perlu diperbaiki sebelum submission final Gemastik XIX, terutama Bug 1 (NLP feature extraction) dan Bug 3 (SHAP XAI kosong) yang berdampak langsung pada kualitas output yang dinilai juri.

### Prioritas Perbaikan

| Prioritas | Bug | Severity | Estimasi Fix |
|---|---|---|---|
| P1 | NLP Behavioral Feature Extraction | Medium | 2-4 jam |
| P2 | SHAP feature_contributions kosong | Medium | 3-6 jam |
| P3 | Web scraper false positive Instagram | Low | 1-2 jam |
| P4 | Company validator false positive risk flag | Low | 1-2 jam |

### Rekomendasi untuk Pengguna

Meskipun verdict AMAN, pengguna tetap disarankan untuk:

1. Cek legalitas perusahaan di **AHU Online** (ahu.go.id) dan **OSS** (oss.go.id)
2. Verifikasi kepesertaan BPJS Ketenagakerjaan perusahaan
3. Tanyakan informasi gaji secara eksplisit sebelum proses lanjut
4. Jangan berikan data sensitif (KTP, rekening bank) sebelum menerima surat kontrak resmi

---

*Report ini dibuat secara otomatis oleh pipeline Verifin. Hasil analisis bersifat indikatif dan tidak menggantikan due diligence manual.*

**Verifin — Verifikasi Lowongan Kerja Berbasis AI**
Tim Esthy Group | Gemastik XIX 2026
