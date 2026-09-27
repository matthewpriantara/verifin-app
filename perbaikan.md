# Laporan Audit Kode & Dokumen Rencana Perbaikan Backend Verifin
**Sistem:** Verifin (*Explainable AI-powered Decision Support System* untuk Verifikasi Lowongan Kerja Berbasis Bukti OSINT)  
**Ruang Lingkup:** Seluruh modul pada direktori `backend/`  
**Dasar Evaluasi:** Keselarasan Arsitektur Proposal, Laporan Akhir Finalis GEMASTIK XIX, serta Standar Rekayasa Perangkat Lunak Produksi.

---

## DAFTAR ISI
1. [Dead Code & Dead Branch (Kode Mati yang Tidak Pernah Dieksekusi)](#1-dead-code--dead-branch-kode-mati-yang-tidak-pernah-dieksekusi)
2. [Redundant Execution & Duplicate Network Calls (Eksekusi Ganda Pemboros Sumber Daya)](#2-redundant-execution--duplicate-network-calls-eksekusi-ganda-pemboros-sumber-daya)
3. [Logic yang Hasilnya Ditimpa, Diabaikan, atau Tidak Berdampak](#3-logic-yang-hasilnya-ditimpa-diabaikan-atau-tidak-berdampak)
4. [Fallback yang Menutupi Root Cause & Error Handling Terlalu Luas](#4-fallback-yang-menutupi-root-cause--error-handling-terlalu-luas)
5. [Duplicate Logic & Fragmented Implementations](#5-duplicate-logic--fragmented-implementations)
6. [Wrapper/Helper yang Tidak Memberikan Nilai Tambahan](#6-wrapperhelper-yang-tidak-memberikan-nilai-tambahan)
7. [Masalah Arsitektur & Operasi Berbahaya saat Import (Side Effects)](#7-masalah-arsitektur--operasi-berbahaya-saat-import-side-effects)
8. [Value & Konfigurasi Hardcoded yang Seharusnya di `.env` atau `config.py`](#8-value--konfigurasi-hardcoded-yang-seharusnya-di-env-atau-configpy)
9. [Case-Specific Logic & Brittle Heuristics (Overfitting Kasus Tertentu)](#9-case-specific-logic--brittle-heuristics-overfitting-kasus-tertentu)
10. [Magic Numbers & Magic Strings yang Seharusnya Menjadi Constant/Parameter](#10-magic-numbers--magic-strings-yang-seharusnya-menjadi-constantparameter)
11. [Logic Berulang yang Seharusnya Menjadi Reusable Function/Helper](#11-logic-berulang-yang-seharusnya-menjadi-reusable-functionhelper)
12. [Function yang Terlalu Spesifik dan Mengunci Nilai (Lacks Parameterization)](#12-function-yang-terlalu-spesifik-dan-mengunci-nilai-lacks-parameterization)
13. [Conditional & Branching yang Perlu Dibuat Generic](#13-conditional--branching-yang-perlu-dibuat-generic)
14. [Konfigurasi Tersebar (Scattered Config) yang Seharusnya Dipusatkan](#14-konfigurasi-tersebar-scattered-config-yang-seharusnya-dipusatkan)
15. [Matriks Rencana Refaktorisasi Terpadu (Design Roadmap)](#15-matriks-rencana-refaktorisasi-terpadu-design-roadmap)
16. [Audit Khusus ner.py: Disparitas Arsitektur Hybrid NER (Proposal vs Realitas Implementasi)](#16-audit-khusus-nerpy-disparitas-arsitektur-hybrid-ner-proposal-vs-realitas-implementasi)

---

## 1. Dead Code & Dead Branch (Kode Mati yang Tidak Pernah Dieksekusi)

### 1.1 `collect_google_maps_evidence`, `collect_instagram_evidence`, `collect_facebook_evidence`, dan `run_platform_evidence`
- **Lokasi:** `backend/app/services/osint/platform_providers.py` (Baris 46–212 dan 307–314) serta helper terkait baris 23–44 (`_matches_platforms`, `_filter_by_platform`, `_search_platform_evidence`).
- **Masalah:** Fungsi-fungsi ini ditulis untuk melakukan direct scraping/search per-platform via Lightpanda. Namun pemanggil di pipeline (`web_evidence.py:671`) hanyalah `collect_all_platform_evidence`. Keempat fungsi ini tidak pernah diimpor maupun dipanggil di mana pun.
- **Kenapa Tidak Fleksibel/Reusable:** Menyisakan ~170 baris kode yang membebani pemeliharaan, memicu impor sirkular potensial, dan mengaburkan rute pengumpulan data bukti platform.
- **Rekomendasi:** Hapus seluruh fungsi mati tersebut.
- **Dampak & Risiko:** Nol risiko fungsional karena tidak memiliki pemanggil (*zero caller*).
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 1.2 `ai_extract_from_page` dan `ai_extract_from_page_sync`
- **Lokasi:** `backend/app/services/osint/ai_extractor.py` (Baris 152–244) & `backend/app/services/osint/platform_providers.py` (Baris 296–304).
- **Masalah:** `ai_extract_from_page` dibuat untuk membedah teks HTML per halaman via LLM. Satu-satunya pemanggil adalah `ai_extract_from_page_sync`, yang hanya dipanggil di dalam 3 fungsi mati pada poin 1.1.
- **Kenapa Tidak Fleksibel/Reusable:** ~100 baris logika prompt dan parsing LLM yang tidak aktif.
- **Rekomendasi:** Hapus kedua fungsi.
- **Dampak & Risiko:** Nol risiko fungsional.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 1.3 `_lightpanda_fetch_via_http` dan `_cdp_fetch_via_websocket`
- **Lokasi:** `backend/app/services/osint/lightpanda_client.py` (Baris 56–144).
- **Masalah:** Implementasi WebSocket client interaktif untuk Chrome DevTools Protocol (CDP) Lightpanda. Fungsi `lightpanda_fetch` di baris 157 langsung memanggil `_lightpanda_fetch_via_docker`, dan jika gagal langsung beralih ke `httpx.Client`. Fungsi CDP WebSocket ini tidak pernah dipanggil.
- **Kenapa Tidak Fleksibel/Reusable:** ~90 baris kode jaringan tingkat rendah yang kompleks, rawan timeout zombie, dan tidak pernah dipakai. Konfigurasi `LIGHTPANDA_CDP_URL` di `config.py` pun menjadi variabel mati.
- **Rekomendasi:** Hapus implementasi WebSocket CDP; gunakan Docker CLI exec atau HTTP standard scraper.
- **Dampak & Risiko:** Nol risiko fungsional.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 1.4 `lightpanda_fetch_instagram` dan `lightpanda_fetch_facebook`
- **Lokasi:** `backend/app/services/osint/lightpanda_client.py` (Baris 325–391).
- **Masalah:** Fungsi parsing DOM Instagram dan Facebook via Lightpanda. Media sosial saat ini ditangani melalui SERP aggregation di `social.py`, sehingga fungsi ini tidak pernah dipanggil.
- **Kenapa Tidak Fleksibel/Reusable:** 65 baris dead code yang terikat struktur DOM medsos yang cepat basi (*fragile scraping*).
- **Rekomendasi:** Hapus kedua fungsi.
- **Dampak & Risiko:** Nol risiko fungsional.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 1.5 `_slug_candidates`
- **Lokasi:** `backend/app/services/osint/social.py` (Baris 122–153).
- **Masalah:** Menghasilkan variasi handle medsos dari nama perusahaan. Tidak dipanggil di mana pun di dalam `social.py` maupun modul lain.
- **Kenapa Tidak Fleksibel/Reusable:** 31 baris dead code.
- **Rekomendasi:** Hapus fungsi.
- **Dampak & Risiko:** Nol risiko fungsional.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 1.6 `_merge_entities`
- **Lokasi:** `backend/app/api/v1/verify/pipeline.py` (Baris 393–428).
- **Masalah:** Fungsi penggabung dua dictionary entitas. Pipeline saat ini menggunakan `_extract_entities_hybrid` (baris 134–217) untuk menggabungkan hasil Regex dan LLM secara in-place. `_merge_entities` tidak pernah dipanggil.
- **Kenapa Tidak Fleksibel/Reusable:** 36 baris kode mati yang menduplikasi logika merge di `_extract_entities_hybrid`.
- **Rekomendasi:** Hapus fungsi.
- **Dampak & Risiko:** Nol risiko fungsional.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 1.7 `validate_company`
- **Lokasi:** `backend/app/services/osint/company_validator.py` (Baris 179–180).
- **Masalah:** Fungsi standalone `async def validate_company(name: str)` tidak pernah diimpor atau dipanggil oleh modul mana pun (modul lain selalu memanggil `validate_companies`).
- **Kenapa Tidak Fleksibel/Reusable:** Dead function.
- **Rekomendasi:** Hapus fungsi.
- **Dampak & Risiko:** Nol risiko fungsional.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 1.8 `is_completed` dan `is_unavailable`
- **Lokasi:** `backend/app/services/status_contract.py` (Baris 13–18).
- **Masalah:** Helper boolean ini tidak pernah digunakan di seluruh codebase. File lain selalu membandingkan status secara langsung terhadap konstanta string (`status == COMPLETED`).
- **Kenapa Tidak Fleksibel/Reusable:** Dead helpers.
- **Rekomendasi:** Hapus helper atau terapkan secara konsisten di seluruh layer.
- **Dampak & Risiko:** Nol risiko fungsional.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 1.9 `get_network_graph_data`
- **Lokasi:** `backend/app/services/graph/fraud_network.py` (Baris 155–195).
- **Masalah:** Fungsi serialisasi graf NetworkX ke format `{nodes: [...], edges: [...]}` untuk visualisasi interaktif (FR-11). Meskipun diekspor di `app/services/graph/__init__.py`, tidak ada endpoint API di FastAPI router yang memanggil fungsi ini.
- **Kenapa Tidak Fleksibel/Reusable:** Fitur FR-11 (Visualisasi Graf) dari backend belum terhubung ke API publik.
- **Rekomendasi:** Tambahkan endpoint API publik `/api/v1/cases/graph` atau simpan sebagai bagian dari respons verifikasi.
- **Dampak & Risiko:** Positif (mengaktifkan fungsionalitas FR-11 yang tertunda).
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 1.10 Dead Branch pada Fitur Perilaku NLP di SHAP Explainer
- **Lokasi:** `backend/app/services/xai/shap_explainer.py` (Baris 51–127).
- **Masalah:** Blok `if nlp_result and nlp_result.get("behavioral_features"):` mengecek fitur `has_fee_request`, `has_foreign_work`, `has_whatsapp_apply`, `fraud_keyword_count`, dll. Namun `nlp_result` dikirim dari `pipeline.py:464` hanya jika `(nlp_result or {}).get("enabled") is True`. Karena `classify_text` di `classifier.py` mengembalikan hardcoded `enabled: False` (sesuai Laporan Akhir Bab III/VI), cabang baris 51–127 adalah *unreachable dead branch*.
- **Kenapa Tidak Fleksibel/Reusable:** Bobot perilaku penipuan Indonesia tidak berkontribusi pada SHAP score melalui jalur ini.
- **Rekomendasi:** Ambil sinyal perilaku dari output prompt LLM Layer 3 atau aktifkan ekstraksi regex rule-based deterministik pada Layer 1.
- **Dampak & Risiko:** Meningkatkan explainability XAI agar konsisten dengan klaim Laporan Akhir.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

---

## 2. Redundant Execution & Duplicate Network Calls (Eksekusi Ganda Pemboros Sumber Daya)

### 2.1 Panggilan Ganda `intelligent_search` pada Perusahaan yang Sama
- **Lokasi:** `backend/app/services/osint/web_evidence.py` (Baris 629–633) dan `backend/app/services/osint/platform_providers.py` (Baris 219–220).
- **Masalah:**
  1. `web_evidence.collect_web_evidence` memanggil `intelligent_search(primary_company, primary_address, max_results=10)`.
  2. Di baris 677, `collect_all_platform_evidence(company_name, loc)` dipanggil.
  3. Di dalam `collect_all_platform_evidence` (Baris 219), ia kembali memanggil `intelligent_search(business_name, location, max_results=10)` dengan query dan argumen identik.
- **Kenapa Tidak Fleksibel/Reusable:** Setiap verifikasi loker dengan nama PT melakukan request pencarian SearXNG/Lightpanda 2x untuk query yang sama.
- **Rekomendasi:** Lewatkan hasil `si_result` dari `web_evidence.py` langsung ke `collect_all_platform_evidence`. Hentikan pemanggilan ulang.
- **Dampak & Risiko:** Memangkas 50% latensi pencarian web OSINT dan mencegah rate-limiting SearXNG.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 2.2 Panggilan Ganda LLM Ekstraksi pada `platform_providers.py`
- **Lokasi:** `backend/app/services/osint/platform_providers.py` (Baris 238) via `_run_ai_extract_sync` $\to$ `ai_extract_and_rank`.
- **Masalah:** Setelah pencarian web, modul ini mengirim prompt ke LLM API untuk mengekstrak entitas dari snippet hasil pencarian. Padahal, pipeline Layer 1 sudah menjalankan ekstraksi NER hibrida, dan Layer 3 menjalankan penalaran LLM komprehensif.
- **Kenapa Tidak Fleksibel/Reusable:** Memunculkan panggilan API LLM sinkron tambahan di tengah tahap OSINT.
- **Rekomendasi:** Ganti pembedahan snippet dengan regex dan token matching deterministik sederhana.
- **Dampak & Risiko:** Menghemat 3–8 detik latensi per verifikasi dan menghemat kuota token LLM.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 2.3 Pemanggilan `classify_text` yang Selalu Menghasilkan Stub
- **Lokasi:** `backend/app/api/v1/verify/router.py` (Baris 172 & 282).
- **Masalah:** `classify_text` dipanggil di endpoint teks dan gambar, dicatat log latensinya, diselipkan ke `analysis["nlp_result"]`, lalu di `pipeline.py:464` dibuang karena `enabled: False`. Berdasarkan Laporan Akhir (Bab III E & Bab VI A.2), model EMSCAD tidak dipakai dalam operasional.
- **Kenapa Tidak Fleksibel/Reusable:** Overhead komputasi dan logging kosong tanpa dampak fungsional.
- **Rekomendasi:** Hapus pemanggilan stub ini dari router.
- **Dampak & Risiko:** Aliran data lebih bersih dan jelas.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

---

## 3. Logic yang Hasilnya Ditimpa, Diabaikan, atau Tidak Berdampak

### 3.1 Panggilan Ganda `_to_response` yang Menimpa Hasil Pertama
- **Lokasi:** `backend/app/api/v1/verify/router.py`:
  - Endpoint Text: Baris 204 & 210
  - Endpoint Image: Baris 305 & 311
  - Endpoint URL: Baris 422 & 428
  - Endpoint Stream: Baris 810 & 816
- **Masalah:**
  ```python
  response = _to_response(analysis, entities, osint_results)  # Panggilan 1
  save_status = await asyncio.to_thread(_save_case_to_db, ...)
  analysis["case_id"] = save_status.get("case_id")
  response = _to_response(analysis, entities, osint_results)  # Panggilan 2 (Menimpa Panggilan 1)
  ```
  Di dalam `_to_response`, fungsi berat `explain_verification_shap(...)` dijalankan. Karena `_to_response` dipanggil dua kali berturut-turut hanya untuk menyisipkan `case_id`, kalkulasi fitur SHAP dan pembuatan grafik *waterfall* dijalankan dua kali. Hasil panggilan pertama dibuang ke garbage collector.
- **Kenapa Tidak Fleksibel/Reusable:** Pemborosan siklus CPU pada setiap request verifikasi.
- **Rekomendasi:** Panggil `_to_response` satu kali setelah `case_id` diperoleh, atau mutasikan atribut `response.case_id = save_status.get("case_id")` secara langsung.
- **Dampak & Risiko:** Mempercepat respons akhir API tanpa mengubah format output.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 3.2 Parameter `risk_factors` dan `safe_factors` yang Diabaikan di SHAP Explainer
- **Lokasi:** `backend/app/services/xai/shap_explainer.py` (Baris 41–42).
- **Masalah:** Signature `explain_verification_shap` menerima parameter `risk_factors: list[str]` dan `safe_factors: list[str]`. Namun di dalam tubuh fungsi, kedua parameter ini tidak pernah dibaca. `risk_contribs` dan `safe_contribs` dihitung murni dari `contributions` internal OSINT.
- **Kenapa Tidak Fleksibel/Reusable:** Antarmuka fungsi membingungkan caller karena parameter yang dikirim tidak memiliki dampak komputasi.
- **Rekomendasi:** Hubungkan evaluasi string `risk_factors`/`safe_factors` ke kontribusi fitur terkait, atau bersihkan dari signature.
- **Dampak & Risiko:** Antarmuka fungsi menjadi konsisten.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 3.3 Parameter yang Dibuang di `check_phones_reputation`
- **Lokasi:** `backend/app/services/osint/phone_validator.py` (Baris 140–147) & `runner.py` (Baris 144–145).
- **Masalah:** `runner.py` mengirim `company=company` dan `web_results=web_results` ke `check_phones_reputation`. Tetapi fungsi tersebut membuangnya dengan memanggil `check_phones_kredibel(contacts, limit=limit)`.
- **Kenapa Tidak Fleksibel/Reusable:** Signature fungsi menjanjikan fitur cross-validation yang ternyata dikerjakan secara terpisah di tempat lain (`_cross_check_phone_official`).
- **Rekomendasi:** Rapikan signature parameter fungsi.
- **Dampak & Risiko:** Kode bersih dan maintainable.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 3.4 Key `"entities"` Ditimpa Dua Kali dalam Dictionary Literal
- **Lokasi:** `backend/app/api/v1/verify/router.py` (Baris 643 dan Baris 651 pada `get_case_by_id`).
- **Masalah:**
  ```python
  return {
      ...
      "entities": db_case.entities,  # Baris 643
      ...
      "entities": entities,          # Baris 651 (MENG-OVERWRITE Baris 643)
      ...
  }
  ```
- **Kenapa Tidak Fleksibel/Reusable:** Nilai baris 643 langsung dibuang karena diduplikasi dan ditimpa oleh baris 651.
- **Rekomendasi:** Hapus deklarasi duplikat pada baris 643.
- **Dampak & Risiko:** Menghindari ambiguitas data dictionary.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

---

## 4. Fallback yang Menutupi Root Cause & Error Handling Terlalu Luas

### 4.1 Masking Kegagalan LLM sebagai "Evidence Reasoning" Sukses
- **Lokasi:** `backend/app/services/llm/verifin_reasoning.py` (Baris 375–436).
- **Masalah:** Jika `chat_completion` melempar Exception (timeout API, API key invalid, jaringan putus), blok `except Exception as exc:` menangkap error tersebut tanpa melakukan logging error (`logger.exception`), lalu mengembalikan dictionary buatan statis dengan label `model_used: f"{LLM_MODEL} (Evidence Reasoning)"`.
- **Kenapa Tidak Fleksibel/Reusable:** Menipu pemanggil API dan sistem observability seolah-olah LLM berhasil berjalan normal, padahal terjadi kegagalan fatal (*silent failure*).
- **Rekomendasi:** Catat log error dengan `logger.exception`, tandai `model_used` sebagai `f"{LLM_MODEL} (Rule-Based Fallback)"`, dan sertakan flag kegagalan eksplisit.
- **Dampak & Risiko:** Root cause koneksi/kuota LLM dapat dideteksi dan diperbaiki secara dini.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 4.2 Duplikasi Logika Fallback Analisis Loker
- **Lokasi:** `backend/app/services/llm/verifin_reasoning.py`:
  - Fallback 1: `_fallback_analysis` (Baris 129–160) ketika 3x retry validasi semantik gagal. Skor di-hardcode (80 untuk bahaya, 28 untuk aman).
  - Fallback 2: Blok `except Exception` (Baris 375–436) ketika koneksi melempar exception. Skor dihitung bertahap ($12 + 65 + 10$).
- **Masalah:** Dua logika fallback terpisah untuk skenario kegagalan LLM yang sama, namun menggunakan formula skoring dan payload yang berbeda.
- **Kenapa Tidak Fleksibel/Reusable:** Inkonsistensi keputusan saat sistem mengalami masalah parsing vs masalah jaringan.
- **Rekomendasi:** Satukan kedua fallback ke dalam satu fungsi terpadu `_generate_rule_based_fallback(entities, osint_results, reason)`.
- **Dampak & Risiko:** Menjamin hasil deterministik dan seragam saat LLM tidak tersedia.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 4.3 Fallback Parser JSON yang Terikat Hanya pada Output Verdict
- **Lokasi:** `backend/app/services/llm/client.py` (Baris 128 dan Baris 135–142).
- **Masalah:**
  1. Pada `_repair_truncated_json`, terdapat guard: `if isinstance(obj, dict) and "verdict" in obj: return obj`. Akibatnya, pemanggilan dari `entity_extraction.py` atau `entity_validator.py` (yang skemanya tidak memiliki key `"verdict"`) selalu gagal diperbaiki jika JSON terpotong.
  2. Jika JSON gagal di-parse total, fallback mengembalikan dictionary khusus verdict (`"verdict": "ERROR"`, `"risk_score": 0`), yang tidak sesuai dengan caller ekstraksi entitas.
- **Kenapa Tidak Fleksibel/Reusable:** Fungsi utilitas `extract_json_from_response` di `client.py` kehilangan sifat generik dan tidak reusable untuk modul selain `verifin_reasoning`.
- **Rekomendasi:** Jadikan `extract_json_from_response(text: str, default: dict | None = None, required_keys: list[str] | None = None)` generik.
- **Dampak & Risiko:** Seluruh caller LLM dapat memanfaatkan JSON repair dan error recovery secara andal.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

---

## 5. Duplicate Logic & Fragmented Implementations

### 5.1 Duplikasi Normalisasi Nomor Telepon Indonesia (4 Implementasi)
- **Lokasi:**
  1. `backend/app/services/ner.py:226` (`clean_indonesian_phone`)
  2. `backend/app/services/graph/fraud_network.py:10` (`_canonical_phone`)
  3. `backend/app/services/osint/phone_validator.py:8` (`normalize_phone_id`)
  4. `backend/app/api/v1/verify/pipeline.py:103` (inline string replace di `_community_report_signal`)
- **Masalah:** Keempat lokasi menuliskan logika yang sama: membuang karakter non-digit dan mengubah prefix `08xx`/`8xx` menjadi standar internasional `628xx`.
- **Kenapa Tidak Fleksibel/Reusable:** Perbedaan kecil pada regex atau handling spasi dapat menyebabkan mismatch pencarian kasus di database lintas modul.
- **Rekomendasi:** Satukan ke dalam satu modul utilitas `backend/app/services/phone_utils.py` dengan fungsi standar `canonicalize_indonesian_phone(phone: str) -> str`.
- **Dampak & Risiko:** Memastikan konsistensi pencocokan entitas nomor HP 100% identik di seluruh sistem.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 5.2 Duplikasi Resolusi Entitas Perusahaan & Stopwords Lokasi
- **Lokasi:**
  - `backend/app/services/osint/query_builder.py` (Baris 5–14 & 21–30)
  - `backend/app/services/osint/search_intelligence.py` (Baris 11–29 & 44–65)
  - `backend/app/services/ner.py` (Baris 424–448)
- **Masalah:** Masing-masing file mendefinisikan regex prefix legalitas PT/CV/Yayasan, ekstraksi alias dalam tanda kurung, dan daftar kata henti lokasi secara terpisah.
- **Kenapa Tidak Fleksibel/Reusable:** Penambahan bentuk badan hukum baru (seperti BUMDes, Koperasi) harus dilakukan di 3 berkas terpisah.
- **Rekomendasi:** Pindahkan daftar legal form dan stopwords ke `app/services/constants.py` dan gunakan satu fungsi helper resolusi entitas.
- **Dampak & Risiko:** Perubahan kosakata hukum Indonesia menjadi terpusat.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 5.3 Duplikasi Pembersihan Alamat Fisik OCR
- **Lokasi:**
  - `backend/app/services/ner.py:103` (`_clean_address`)
  - `backend/app/services/osint/address_validator.py:78–110` (`_OCR_ADDR_FIXES`, `_normalize_ocr_address`, `_clean_address_input`)
- **Masalah:** Keduanya mengoreksi salah baca OCR umum pada alamat Indonesia (`JI.` $\to$ `Jl.`, `lstimewa` $\to$ `Istimewa`, dll.) dan membuang label header ("Penempatan / Alamat / Lokasi:").
- **Kenapa Tidak Fleksibel/Reusable:** Duplikasi logika string cleaning pada layer ekstraksi dan layer validasi geocoding.
- **Rekomendasi:** Satukan fungsi normalisasi alamat OCR ke modul bersama.
- **Dampak & Risiko:** Penanganan typo OCR seragam di semua tahapan.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 5.4 Duplikasi Pipeline Verifikasi URL (~150 Baris)
- **Lokasi:** `backend/app/api/v1/verify/router.py`:
  - `verify_job_url` (Baris 345–435)
  - `_verify_url_stream_generator` (Baris 705–829)
- **Masalah:** Rantai pemrosesan URL $\to$ Scrapling $\to$ OCR gambar $\to$ block formatting $\to$ cache check $\to$ NER hybrid $\to$ Fraud Network $\to$ OSINT $\to$ LLM reasoning $\to$ DB save diimplementasikan dua kali secara hampir verbatim. Perbedaannya hanya pada injeksi `yield _sse_event(...)` pada versi stream.
- **Kenapa Tidak Fleksibel/Reusable:** Setiap pembaruan atau bug fix pada endpoint URL reguler harus di-copy-paste manual ke endpoint streaming, berisiko tinggi terjadi divergensi logika (*logic drift*).
- **Rekomendasi:** Ekstrak logika pipeline inti ke fungsi pipeline bersama yang menerima callback observer `on_stage_progress(stage, status, message)`.
- **Dampak & Risiko:** Memangkas ~120 baris kode duplikat dan menjamin endpoint URL reguler dan stream 100% identik perilakunya.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

---

## 6. Wrapper/Helper yang Tidak Memberikan Nilai Tambahan

### 6.1 `_run_osint_on_entities`
- **Lokasi:** `backend/app/api/v1/verify/pipeline.py` (Baris 260–261).
- **Masalah:**
  ```python
  async def _run_osint_on_entities(entities: dict) -> dict:
      return await run_osint_probes(entities)
  ```
  Hanya membungkus 1 baris fungsi `run_osint_probes` tanpa penambahan logging atau transformasi apa pun.
- **Kenapa Tidak Fleksibel/Reusable:** Indirection tidak berguna yang menambah jejak stack trace.
- **Rekomendasi:** Panggil `run_osint_probes(entities)` secara langsung di caller.
- **Dampak & Risiko:** Nol risiko fungsional.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 6.2 `check_ai_status` di `verifin_reasoning.py`
- **Lokasi:** `backend/app/services/llm/verifin_reasoning.py` (Baris 438–445).
- **Masalah:** Hanya memanggil `check_llm_status()` dari `client.py` dan mengecek apakah `detail` bertipe string.
- **Kenapa Tidak Fleksibel/Reusable:** Wrapper redundan.
- **Rekomendasi:** Router dapat langsung mengimpor dan memanggil `check_llm_status()` dari `client.py`.
- **Dampak & Risiko:** Nol risiko fungsional.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 6.3 `validate_companies` di `company_validator.py`
- **Lokasi:** `backend/app/services/osint/company_validator.py` (Baris 164–177).
- **Masalah:** Dideklarasikan sebagai `async def`, tetapi di dalamnya tidak ada satu pun operasi I/O asinkron atau `await`. Fungsi ini murni menjalankan loop komputasi in-memory sinkron.
- **Kenapa Tidak Fleksibel/Reusable:** "Fake async" yang menambah overhead event loop tanpa manfaat konkurensi nyata.
- **Rekomendasi:** Jadikan fungsi sinkron standar `def validate_companies(...)`.
- **Dampak & Risiko:** Pemanggilan kode lebih jujur dan efisien.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

---

## 7. Masalah Arsitektur & Operasi Berbahaya saat Import (Side Effects)

### 7.1 Eksekusi DDL Database saat Modul Diimpor (Import-Time Side Effects)
- **Lokasi:** `backend/app/api/v1/community/router.py` (Baris 21–38).
- **Masalah:**
  ```python
  Base.metadata.create_all(bind=engine, tables=[CommunityReport.__table__], checkfirst=True)
  with engine.begin() as conn:
      for ddl in ('ALTER TABLE community_reports ADD COLUMN IF NOT EXISTS ...', ...):
          conn.execute(text(ddl))
  ```
  Blok ini berada di level modul terluar (*top-level scope*). Setiap kali modul diimpor (termasuk saat menjalankan test runner atau import FastAPI di `main.py`), Python langsung melakukan koneksi blocking ke database PostgreSQL dan menjalankan DDL `ALTER TABLE`.
- **Kenapa Tidak Fleksibel/Reusable:**
  1. Jika database belum aktif atau terjadi gangguan jaringan saat startup, seluruh aplikasi crash seketika pada tahap import.
  2. Test suite yang menguji unit utilitas terblokir karena mencoba koneksi ke DB saat mengimpor router.
  3. `app/main.py` sudah memiliki fungsi `lifespan` resmi untuk inisialisasi skema.
- **Rekomendasi:** Pindahkan eksekusi pembuatan tabel dan migrasi ke dalam event `lifespan` di `app/main.py`.
- **Dampak & Risiko:** Mengamankan proses booting aplikasi dan meniadakan import side-effects.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 7.2 Hardcoded Status Layanan pada Health Check Endpoint
- **Lokasi:** `backend/app/api/v1/health/router.py` (Baris 39–44).
- **Masalah:**
  ```python
  "osint_services": {
      "openstreetmap": "online",
      "kredibel": "online",
      "scrapling": "online",
      "social_media": "online",
  }
  ```
  Status ini di-hardcode string `"online"`. Layanan Kredibel bahkan sudah tidak dipakai di arsitektur (digantikan Kaspersky), namun health-check tetap melaporkannya "online".
- **Kenapa Tidak Fleksibel/Reusable:** Health check memberikan metrik palsu bagi load balancer atau monitoring server.
- **Rekomendasi:** Lakukan pemeriksaan riil non-blocking (misal mengecek availability cache SearXNG, check connection DNS) atau hapus key statis palsu tersebut.
- **Dampak & Risiko:** Menghasilkan metrik kesehatan server yang akurat dan jujur.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 7.3 Konfigurasi & Dependensi Mati di `config.py`
- **Lokasi:** `backend/app/config.py`:
  - `REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")` (Baris 18)
  - `LLM_VISION_MODEL = os.getenv("LLM_VISION_MODEL") or LLM_MODEL` (Baris 11)
- **Masalah:**
  - Redis tidak pernah diimpor, tidak terdaftar di `requirements.txt`, dan tidak digunakan di modul mana pun.
  - `LLM_VISION_MODEL` tidak pernah dipanggil karena OCR gambar sepenuhnya ditangani oleh PaddleOCR lokal.
- **Kenapa Tidak Fleksibel/Reusable:** Variabel konfigurasi palsu yang membingungkan operator deployment dan dokumentasi env.
- **Rekomendasi:** Hapus kedua variabel dari `config.py` dan `.env.example`.
- **Dampak & Risiko:** Nol risiko fungsional.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

---

## 8. Value & Konfigurasi Hardcoded yang Seharusnya di `.env` atau `config.py`

### 8.1 URL, Timeout, dan Identitas Header OSINT Eksternal
- **Lokasi:**
  - `backend/app/services/osint/address_validator.py` (Baris 6–11)
  - `backend/app/services/osint/phone_validator.py` (Baris 22)
  - `backend/app/services/osint/whois_handler.py` (Baris 13 & 31)
- **Masalah:**
  - `NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"` di-hardcode di kode.
  - `REQUEST_TIMEOUT = 15.0` di-hardcode di kode.
  - `NOMINATIM_HEADERS = {"User-Agent": "Verifin-OSINT-App/1.0 (gemastik-competition; contact@verifin.app)"}` (email dan identitas user-agent di-hardcode).
  - URL endpoint Kaspersky Who Calls (`https://whocalls.id.kaspersky.com/info/...`) di-hardcode.
  - Endpoint RDAP (`https://rdap.org/domain/...`) dan Wayback Machine CDX (`https://web.archive.org/cdx/search/cdx`) di-hardcode dengan timeout 8 detik.
- **Kenapa Tidak Fleksibel/Reusable:** Jika instansi pengguna ingin menjalankan server Nominatim lokal (on-premise / self-hosted) untuk menghindari rate limit OSM publik, URL tidak dapat diganti tanpa memodifikasi kode sumber. Begitu pula email kontak pada User-Agent OSM (wajib menurut Nominatim Usage Policy) tidak dapat disesuaikan per instance.
- **Rekomendasi:** Pindahkan ke `backend/app/config.py` dan baca dari `.env`:
  - `NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")`
  - `OSINT_USER_AGENT = os.getenv("OSINT_USER_AGENT", "Verifin-OSINT-App/1.0")`
  - `OSINT_TIMEOUT_SEC = float(os.getenv("OSINT_TIMEOUT_SEC", "15.0"))`
- **Dampak & Risiko:** Sangat aman; nilai default tetap sama jika variabel `.env` tidak disetel.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 8.2 Parameter Operasional & Caching SearXNG
- **Lokasi:** `backend/app/services/osint/searxng_client.py` (Baris 16–27).
- **Masalah:**
  - `_SEARXNG_BASE = SEARXNG_URL or "http://localhost:8888"`
  - `_SEARXNG_TIMEOUT = 15`
  - `_CACHE_TTL_SECONDS = 600`
  - `_CACHE_MAX_ENTRIES = 512`
  - `_MIN_REQUEST_INTERVAL: float = 0.8`
  - `_AVAILABILITY_TTL: float = 30.0`
- **Kenapa Tidak Fleksibel/Reusable:** Nilai-nilai performa dan rate limiting ini terkunci di file service internal. Jika instance SearXNG berada di cloud berlatensi tinggi atau server shared yang membutuhkan throttle lebih longgar (misal interval 1.5 detik agar tidak diblokir upstream Google/Brave), developer harus mengubah hardcode di file python.
- **Rekomendasi:** Pindahkan parameter operasional ke `config.py` dengan nilai default:
  - `SEARXNG_TIMEOUT = int(os.getenv("SEARXNG_TIMEOUT", "15"))`
  - `SEARXNG_CACHE_TTL = int(os.getenv("SEARXNG_CACHE_TTL", "600"))`
  - `SEARXNG_MIN_INTERVAL = float(os.getenv("SEARXNG_MIN_INTERVAL", "0.8"))`
- **Dampak & Risiko:** Memudahkan tuning performa di production tanpa menyentuh kode logika.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 8.3 Parameter Inferensi Deteksi & Pra-pemrosesan PaddleOCR
- **Lokasi:** `backend/app/services/ocr.py` (Baris 19–27 dan 46–47).
- **Masalah:**
  - Parameter deteksi binarisasi DBNet di-hardcode:
    ```python
    det_db_thresh=0.2,
    det_db_box_thresh=0.4,
    det_db_unclip_ratio=1.8,
    rec_batch_num=6,
    ```
  - Batas resolusi citra maksimal di-hardcode: `if h > 4000 or w > 4000:` (4000px).
  - Ambang batas CLAHE contrast enhancement: `clipLimit=2.5, tileGridSize=(8, 8)`.
- **Kenapa Tidak Fleksibel/Reusable:** Pada server produksi dengan memory terbatas (misal 2GB RAM pada tier hemat), `rec_batch_num=6` atau citra 4000x4000 dapat memicu OOM (Out Of Memory / killed by OS). Sebaliknya, pada server GPU besar, nilai batch dapat ditingkatkan untuk throughput lebih tinggi.
- **Rekomendasi:** Pindahkan `OCR_REC_BATCH_NUM = int(os.getenv("OCR_REC_BATCH_NUM", "6"))` dan `OCR_MAX_IMAGE_DIM = int(os.getenv("OCR_MAX_IMAGE_DIM", "4000"))` ke `config.py`.
- **Dampak & Risiko:** Meningkatkan reliabilitas server memory management saat memproses poster resolusi tinggi.
- **Tingkat Keyakinan:** **Tinggi (95%)**.

### 8.4 Konfigurasi Upload Berkas Bukti Komunitas
- **Lokasi:** `backend/app/api/v1/community/router.py` (Baris 63, 71, 79).
- **Masalah:**
  - `upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "evidence")` di-hardcode dengan path transversal file relatif.
  - `max_size = 5 * 1024 * 1024` (5 MB) di-hardcode.
  - `allowed_types = {"image/jpeg", "image/png", "image/webp", "image/jpg"}` di-hardcode di dalam fungsi router.
- **Kenapa Tidak Fleksibel/Reusable:** Jika aplikasi di-deploy di Docker container, volume persistent storage biasanya berada di path tertentu (misal `/var/data/uploads` atau shared volume). Path hardcode di dalam folder kode backend menyulitkan mounting volume persistent.
- **Rekomendasi:** Pindahkan ke `config.py`:
  - `UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads" / "evidence"))`
  - `MAX_UPLOAD_SIZE_BYTES = int(os.getenv("MAX_UPLOAD_SIZE_BYTES", str(5 * 1024 * 1024)))`
- **Dampak & Risiko:** Standar rekayasa penyimpanan berkas yang aman dan mudah di-mount ke Docker volume.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 8.5 Konfigurasi Database Connection Pool & CORS Allowed Origins
- **Lokasi:**
  - `backend/app/database/postgres_client.py` (Baris 9)
  - `backend/app/main.py` (Baris 66)
- **Masalah:**
  - `engine = create_engine(_db_url, pool_pre_ping=True)` tidak mengonfigurasi pool size (`pool_size`, `max_overflow`, `pool_timeout`).
  - `allow_origins=["*"]` di-hardcode mengizinkan seluruh domain tanpa filter.
- **Kenapa Tidak Fleksibel/Reusable:**
  - Di database cloud seperti Supabase Session Pooler atau Transaction Pooler (PgBouncer), koneksi default tanpa batasan pool size cepat menyebabkan error `FATAL: remaining connection slots are reserved for non-replication superuser connections`.
  - CORS wildcard `["*"]` berisiko keamanan pada lingkungan staging/produksi yang semestinya hanya mengizinkan domain frontend resmi.
- **Rekomendasi:**
  - Di `config.py`, tambahkan `DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))`, `DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))`.
  - Tambahkan `CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]`.
- **Dampak & Risiko:** Mencegah connection leak database dan meningkatkan postur keamanan CORS.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

---

## 9. Case-Specific Logic & Brittle Heuristics (Overfitting Kasus Tertentu)

### 9.1 Hardcode Entitas Uji "Badan Gizi Nasional / SPPG" pada Token Generik Perusahaan
- **Lokasi:**
  - `backend/app/services/osint/company_validator.py` (Baris 8–10)
  - `backend/app/services/llm/prompt_builder.py` (Baris 416–417)
- **Masalah:**
  ```python
  _COMP_GENERIC_TOKENS = frozenset({
      "center", "management", "group", "utama", "persada", "pt", "cv",
      "badan", "nasional", "gizi", "sppg", "indonesia", "instansi", "dinas",
  })
  ```
  Di `prompt_builder.py`:
  `4. PENCATUTAN INSTANSI PEMERINTAH: Jika lowongan mengatasnamakan instansi/badan resmi pemerintah (misal Badan Gizi Nasional/BGN, SPPG, Kementerian, Dinas)...`
- **Kenapa Tidak Fleksibel/Reusable:** Kata `"gizi"` dan `"sppg"` dimasukkan ke dalam daftar token perusahaan generik karena adanya satu kasus uji penipuan loker spesifik yang mencatut program gizi nasional. Akibatnya, jika ada perusahaan legal di industri pangan/nutrisi (misal "PT Gizi Prima Nusantara" atau "Klinik Gizi Sehat"), token identitas `"gizi"` akan dipotong dan dianggap kata sampah, menurunkan akurasi pencarian legalitas entitas yang sah secara tidak adil.
- **Rekomendasi:**
  - Hapus `"gizi"` dan `"sppg"` dari `_COMP_GENERIC_TOKENS`.
  - Ubah aturan prompt dari menyebut nama instansi spesifik menjadi aturan taksonomi generik: *"Jika lowongan mengatasnamakan instansi/badan/lembaga resmi pemerintah namun menggunakan email publik gratisan (Gmail/Yahoo/dll) tanpa domain resmi .go.id..."*.
- **Dampak & Risiko:** Sistem menjadi netral, adil (*fairness in AI*), dan tidak overfitting pada kasus uji lokal tertentu.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 9.2 String Concatenation Bug & Overfitting Geografis Hyper-Lokal DIY pada `_INDONESIAN_CITIES`
- **Lokasi:** `backend/app/services/ner.py` (Baris 40–48).
- **Masalah:**
  1. **Bug Konkatenasi String:** Pada baris 44–45:
     ```python
     "Bantul|Sewon|Banguntapan|Pajangan|Inpres|Krapyak|Gamping|Patangpuluhan"
     "Cikarang|Karawang|Purwakarta|Subang|Indramayu|Majalengka|"
     ```
     Karena string baris 44 tidak memiliki trailing pipe `|`, Python menggabungkan kedua literal menjadi token tunggal: `"PatangpuluhanCikarang"`. Akibatnya, baik "Patangpuluhan" maupun "Cikarang" gagal dicocokkan jika berdiri sendiri!
  2. **Overfitting Hyper-Lokal:** Variabel bernama `_INDONESIAN_CITIES` memuat nama-nama jalan, kelurahan, dan padukuhan di Kabupaten Sleman/Bantul (seperti `"Pakem"`, `"Sewon"`, `"Manding"`, `"Seturan"`, `"Inpres"`, `"Krapyak"`, `"Patangpuluhan"`), sementara kota-kota besar luar Jawa banyak yang belum terwakili secara proporsional.
- **Kenapa Tidak Fleksibel/Reusable:** Bug sintaksis merusak deteksi entitas kota industri besar ("Cikarang"), dan pencampuran level administratif (kota vs jalan/padukuhan) membuat confidence scoring lokasi bias ke wilayah DIY.
- **Rekomendasi:**
  - Perbaiki bug missing separator `|`.
  - Pisahkan daftar kota resmi (kabupaten/kota se-Indonesia) dari daftar POI/kecamatan khusus. Gunakan data terstruktur JSON/set.
- **Dampak & Risiko:** Memperbaiki bug parsing NER yang selama ini gagal mendeteksi lowongan kerja di area industri Cikarang.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 9.3 Heuristik Pemisahan Token Perusahaan Terpaku pada Kasus Uji "RUMAH BAIK CAKRAWALA"
- **Lokasi:** `backend/app/services/ner.py` (Baris 398–421 pada `_split_stuck_company_tokens`).
- **Masalah:**
  ```python
  known = (
      "RUMAH", "BAIK", "CAKRAWALA", "MAJU", "JAYA", "ABADI", "SEJAHTERA",
      "MANDIRI", "NUSANTARA", "GLOBAL", "PRIMA", "SUKSES", "BERSAMA",
      "INDO", "INDONESIA", "GROUP", "HOLDING", "SENTOSA", "MAKMUR",
  )
  ```
  Fungsi ini sengaja menyisipkan tuple hardcode `"RUMAH"`, `"BAIK"`, `"CAKRAWALA"` karena pada poster OCR uji coba terdapat teks menempel `"RUMAHBAIKCAKRAWALA"`.
- **Kenapa Tidak Fleksibel/Reusable:** Jika ada nama perusahaan lain yang hurufnya menempel dari hasil OCR tanpa spasi dan tidak ada dalam daftar 19 kata tersebut, fungsi memotong karakter satu per satu secara tidak teratur di baris 416–419 (`up[i:j]`).
- **Rekomendasi:** Gunakan pendekatan tokenizer berbasis kamus kata umum bahasa Indonesia (misal kamus kata dasar bahasa Indonesia) atau serahkan pemisahan semantik nama brand ke LLM Layer 1 yang memang dirancang untuk itu.
- **Dampak & Risiko:** Mengeliminasi heuristik rapuh berbasis sampel uji coba tunggal.
- **Tingkat Keyakinan:** **Tinggi (90%)**.

### 9.4 Perbandingan Format Nomor Telepon Brittle pada Deteksi Sindikat Kasus Historis
- **Lokasi:** `backend/app/services/hasher.py` (Baris 28–29 pada `detect_identity_syndicate`).
- **Masalah:**
  ```python
  pool = (c.get("phones") or []) if key == "phone" else (c.get("emails") or [])
  if value in pool:
  ```
  `value` dicocokkan menggunakan operator `in` terhadap elemen array `pool` secara *exact string match*.
- **Kenapa Tidak Fleksibel/Reusable:** Jika nomor di `contacts` berformat internasional `+62812345` sementara nomor yang tersimpan di riwayat kasus database `c["phones"]` berformat `62812345` atau `0812345`, perbandingan `value in pool` menghasilkan `False`. Fitur deteksi sindikat penipuan lintas lowongan (Fraud Network) gagal mendeteksi kesamaan nomor hanya karena perbedaan format prefix atau tanda plus.
- **Rekomendasi:** Terapkan normalisasi kanonikal (`clean_indonesian_phone`) pada kedua sisi sebelum perbandingan set:
  `canonical_pool = {canonicalize_phone(p) for p in pool if p}`
- **Dampak & Risiko:** Memastikan deteksi sindikat penipuan bekerja 100% konsisten terlepas dari variasi input pengguna.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 9.5 Asumsi Awalan Header Scraper / Scaffolding Sistem pada NER Pipeline
- **Lokasi:** `backend/app/api/v1/verify/pipeline.py` (Baris 124–131 pada `_clean_text_for_ner`).
- **Masalah:**
  ```python
  cleaned = re.sub(r"^\[TEKS\s+UTAMA[^\]]*\]:\s*", "", text, flags=re.I | re.M)
  cleaned = re.sub(r"^\[TEKS\s+CAPTION[^\]]*\]:\s*", "", cleaned, flags=re.I | re.M)
  cleaned = re.sub(r"^\[UTAS\s+BALASAN[^\]]*\]:\s*", "", cleaned, flags=re.I | re.M)
  cleaned = re.sub(r"^URL\s+Target:\s*\S+\s*", "", cleaned, flags=re.I | re.M)
  ```
- **Kenapa Tidak Fleksibel/Reusable:**
  1. String label scaffold sistem internal di-hardcode dengan bahasa Indonesia spesifik. Jika struktur prompt URL scraper di `router.py` berubah sedikit saja, regex pembersih ini tidak cocok dan label scaffold bocor ke LLM.
  2. Yang lebih kritis: di baris 137, teks yang dioper ke `extract_entities_from_text(text)` adalah teks asli yang **belum dibersihkan** (`text`, bukan `clean_text`), sehingga regex NER sering mengekstrak kata `Target`, `URL`, atau `TEKS` sebagai entitas.
- **Rekomendasi:** Bersihkan teks scaffold sebelum diproses oleh layer apa pun (baik regex NER maupun LLM NER) dan definisikan marker scaffold sebagai konstanta terpusat.
- **Dampak & Risiko:** Menghilangkan kontaminasi teks sistem pada hasil ekstraksi entitas lowongan.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

---

## 10. Magic Numbers & Magic Strings yang Seharusnya Menjadi Constant/Parameter

### 10.1 Bobot Fitur dan Base Value SHAP Explainer yang Di-hardcode
- **Lokasi:** `backend/app/services/xai/shap_explainer.py` (Baris 12–34, 47, 86, 118, dan 591–605).
- **Masalah:**
  - `_FEATURE_WEIGHTS`: Bobot `40.0`, `25.0`, `20.0`, `8.0`, `15.0`, `-8.0`, `-6.0`, `-5.0`, `35.0`, `28.0`, `12.0`, `30.0`, `10.0` di-hardcode sebagai angka mentah.
  - `base_value = 12.0` di-hardcode.
  - Plafon maksimum penalti/reduksi: `min(fraud_kw * 8.0, 32.0)` dan `min(safe_kw * 5.0, 20.0)` memiliki angka batas 32.0 dan 20.0 tanpa konstanta bernama.
  - Bobot probe investigasi:
    ```python
    {"probe": "Address Geocoding (OSM GIS)", "weight": 0.25, ...},
    {"probe": "Phone Reputation (Kaspersky Who Calls)", "weight": 0.20, ...},
    {"probe": "Company Digital Footprint", "weight": 0.20, ...},
    {"probe": "Domain & Email Security", "weight": 0.15, ...},
    {"probe": "Social Media Footprint", "weight": 0.10, ...},
    {"probe": "Cross-Case Fraud Network", "weight": 0.10, ...},
    ```
    Jumlah bobot $(0.25 + 0.20 + 0.20 + 0.15 + 0.10 + 0.10 = 1.00)$ di-hardcode di dalam array kamus pada baris 591–605.
- **Kenapa Tidak Fleksibel/Reusable:** Kalibrasi bobot pembuktian adalah inti dari keandalan model XAI (Laporan Akhir Bab VI.A.4). Menanam angka mentah di dalam baris logika mempersulit eksperimen penyesuaian bobot (*tuning*) dan pengujian sensitivitas (*ablation study*).
- **Rekomendasi:** Satukan seluruh bobot bukti dan konstanta kalibrasi ke dalam modul konfigurasi XAI khusus (`app/services/xai/weights.py` atau `constants.py`).
- **Dampak & Risiko:** Memudahkan kalibrasi saintifik dan mempermudah audit akurasi XAI.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 10.2 Threshold Umur Domain Segar (`is_new: age_days < 90`) pada WHOIS
- **Lokasi:** `backend/app/services/osint/whois_handler.py` (Baris 89).
- **Masalah:** `"is_new": age_days < 90` menggunakan magic number 90 hari.
- **Kenapa Tidak Fleksibel/Reusable:** Kriteria domain penipuan baru di industri keamanan siber bervariasi antara 30, 90, hingga 180 hari. Jika ingin diubah, developer harus mencari baris ternary operator ini di dalam file handler.
- **Rekomendasi:** Definisikan konstanta `DOMAIN_NEW_THRESHOLD_DAYS = 90` di `constants.py` atau `config.py`.
- **Dampak & Risiko:** Sangat aman dan meningkatkan keterbacaan kode.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 10.3 Ambang Batas Skor Risiko dan Tiga Tingkat Verdict (0–39, 40–74, 75–100)
- **Lokasi:**
  - `backend/app/services/llm/verifin_reasoning.py` (Baris 412)
  - `backend/app/api/v1/verify/router.py` (Baris 486–490)
  - `backend/app/services/llm/prompt_builder.py` (Baris 430–445)
- **Masalah:** Angka ambang batas `40` dan `75` (yang membagi verdict AMAN, WASPADA, BAHAYA sesuai Tabel 5.1 Laporan Akhir) ditulis berulang sebagai angka mentah di berbagai ekspresi perbandingan:
  `verdict = "AMAN" if risk_score < 40 else "WASPADA" if risk_score < 75 else "BAHAYA"`
- **Kenapa Tidak Fleksibel/Reusable:** Jika tim melakukan kalibrasi ulang batas rentang skor (misalnya batas WASPADA dinaikkan menjadi 45 atau 50), pengembang harus mengubahnya di banyak tempat, dan inkonsistensi sedikit saja dapat membuat verdict router berbeda dari verdict reasoning engine.
- **Rekomendasi:** Definisikan konstanta terpusat di `app/services/constants.py`:
  - `RISK_THRESHOLD_WASPADA = 40`
  - `RISK_THRESHOLD_BAHAYA = 75`
  dan buat helper fungsi: `def score_to_verdict(score: int) -> str:`
- **Dampak & Risiko:** Menjamin klasifikasi verdict 100% konsisten di seluruh layer.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 10.4 Batas Truncation Karakter Teks & Snippet yang Tersebar
- **Lokasi:**
  - `backend/app/services/llm/entity_validator.py:126` (`[:3000]`)
  - `backend/app/services/llm/entity_extraction.py:71` (`[:4000]`)
  - `backend/app/services/llm/prompt_builder.py:382` (`[:3000]`)
  - `backend/app/services/db_cache.py:71` (`[:2000]`)
  - `backend/app/services/ner.py:316` (`len(c) < 12 or len(c) > 180`)
- **Masalah:** Angka pemotongan panjang string (`3000`, `4000`, `2000`, `180`) di-hardcode di tengah operasi slice tanpa dokumentasi alasan kapasitas token/kolom database.
- **Kenapa Tidak Fleksibel/Reusable:** Mengubah batas token context window LLM membutuhkan penelusuran manual satu per satu.
- **Rekomendasi:** Definisikan konstanta di `config.py` atau `constants.py`:
  - `MAX_LLM_INPUT_CHARS = 4000`
  - `MAX_CACHE_PREVIEW_CHARS = 2000`
- **Dampak & Risiko:** Kode bersih dan mudah dikonfigurasi saat beralih ke model dengan konteks lebih besar.
- **Tingkat Keyakinan:** **Tinggi (90%)**.

---

## 11. Logic Berulang yang Seharusnya Menjadi Reusable Function/Helper

### 11.1 Pemisahan Prefix Administratif Alamat (Kec., Kab., Kel., Desa, Kota)
- **Lokasi:**
  - `backend/app/services/osint/address_validator.py` (Baris 133–138)
  - `backend/app/services/osint/query_builder.py` (Baris 6–14)
  - `backend/app/services/osint/search_intelligence.py` (Baris 26–29)
- **Masalah:** Fungsi internal `_strip_admin_prefix` di `address_validator.py` mendefinisikan regex prefix wilayah Indonesia, sementara `query_builder.py` dan `search_intelligence.py` mendefinisikan set kata henti yang mirip namun sedikit berbeda (`kecamatan`, `kabupaten`, `kelurahan`, `desa`, `kota`).
- **Kenapa Tidak Fleksibel/Reusable:** Logika pembersihan hirarki wilayah Indonesia terpecah dan tidak konsisten.
- **Rekomendasi:** Buat helper fungsi bersama `strip_administrative_prefix(text: str) -> str` di modul utilitas wilayah.
- **Dampak & Risiko:** Parsing geocoding dan query search menjadi seragam.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 11.2 Pembersihan UI Noise Media Sosial
- **Lokasi:**
  - `backend/app/services/web_fetcher.py` (Baris 14–27, `_IG_NOISE_PATTERNS`)
  - `backend/app/services/ner.py` (Baris 73–89, `_SOCIAL_UI_NOISE_PATTERNS`)
- **Masalah:** Kedua file memuat daftar ekspresi reguler yang hampir identik untuk membuang teks UI bawaan Instagram/Facebook (*"lihat apa yang sedang dibicarakan"*, *"daftar instagram"*, *"nonpengguna meta"*, dll.).
- **Kenapa Tidak Fleksibel/Reusable:** Jika Instagram memperbarui teks tombol atau disclaimer web, pengembang harus memperbarui regex di 2 berkas terpisah.
- **Rekomendasi:** Tempatkan `SOCIAL_UI_NOISE_PATTERNS` di `app/services/constants.py` dan gunakan satu fungsi pembersih teks `strip_social_ui_noise(text: str) -> str`.
- **Dampak & Risiko:** Mencegah kebocoran teks antarmuka Instagram ke modul ekstraksi entitas.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 11.3 Helper Deduplikasi Array String Preservasi Urutan (`_uniq` / `uniq`)
- **Lokasi:**
  - `backend/app/services/ner.py:745` (`_uniq`)
  - `backend/app/services/osint/company_validator.py:129` (`uniq`)
  - `backend/app/services/osint/web_evidence.py:769` (`uniq`)
- **Masalah:** Fungsi helper deduplikasi list string tanpa mengubah urutan ditulis berulang 3 kali di dalam fungsi lokal yang berbeda.
- **Kenapa Tidak Fleksibel/Reusable:** Duplikasi logika mikro (*boilerplate redundancy*).
- **Rekomendasi:** Buat helper bersama `deduplicate_preserve_order(items: Iterable[str]) -> list[str]` di modul utilitas umum.
- **Dampak & Risiko:** Nol risiko; penyederhanaan sintaksis.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

---

## 12. Function yang Terlalu Spesifik dan Mengunci Nilai (Lacks Parameterization)

### 12.1 `geocode_address` Mengunci Kueri Berantai dengan Suffix Hardcoded `", Indonesia"`
- **Lokasi:** `backend/app/services/osint/address_validator.py` (Baris 119, 124, 129, 147, 149, 150, 168).
- **Masalah:** Fungsi pembangun kueri menambahkan string literal `", Indonesia"` pada 9 variasi query fallback secara hardcoded, padahal parameter request ke API Nominatim sudah mengunci `"countrycodes": "id"` pada baris 18.
- **Kenapa Tidak Fleksibel/Reusable:** Suffix hardcoded ini redundan dengan filter API OSM dan berisiko membingungkan tokenizer Nominatim pada alamat yang sudah mencantumkan kata "Indonesia" di akhir. Fungsi kueri tidak menerima parameter negara atau wilayah target.
- **Rekomendasi:** Jadikan suffix negara sebagai parameter opsional dengan default `country_suffix: str = "Indonesia"`, dan hindari penambahan ganda jika string input sudah memuat nama negara.
- **Dampak & Risiko:** Meningkatkan hit-rate pencarian alamat OSM pada input yang sudah berformat lengkap.
- **Tingkat Keyakinan:** **Tinggi (90%)**.

### 12.2 `chat_completion` Mengunci Parameter Model & Retry Tanpa Override Global Default
- **Lokasi:** `backend/app/services/llm/client.py` (Baris 145–154) & `entity_extraction.py` (Baris 83–86).
- **Masalah:** `chat_completion` memiliki default `max_retries=4`, `temperature=0.0`, `max_tokens=4096`. Namun tiap modul pemanggil (`entity_extraction`, `entity_validator`, `verifin_reasoning`) mem-passing override angka secara tersebar dan berbeda-beda (`max_retries=2`, `max_tokens=1500`, `max_tokens=8192`) tanpa konfigurasi berbasis profil tugas.
- **Kenapa Tidak Fleksibel/Reusable:** Sulit mengatur kebijakan retry global saat API provider sedang mengalami degradasi layanan.
- **Rekomendasi:** Buat konfigurasi profil model di `config.py` (misal profil `FAST_EXTRACTION` vs `REASONING_SYNTHESIS`) yang memuat batas token dan batas percobaan secara terpusat.
- **Dampak & Risiko:** Mengoptimalkan kuota token dan latensi panggilan LLM.
- **Tingkat Keyakinan:** **Tinggi (90%)**.

### 12.3 `_search_phone_public_serp` Mengunci Template Kueri Fraud Spesifik
- **Lokasi:** `backend/app/services/osint/phone_validator.py` (Baris 69).
- **Masalah:**
  ```python
  query = f'"{phone_meta["display"]}" OR "0{phone_digits}" penipu OR scam OR penipuan'
  ```
  Template kueri pencarian reputasi nomor telepon terkunci hanya pada 3 kata kunci (`penipu`, `scam`, `penipuan`).
- **Kenapa Tidak Fleksibel/Reusable:** Variasi kejahatan loker sering menggunakan istilah lain seperti `lapor`, `korban`, `modus`, `biaya tes`, `blacklist`. Template kueri tidak dapat dikonfigurasi atau diperluas tanpa mengubah kode fungsi.
- **Rekomendasi:** Ambil kata kunci penipuan dari `constants.py` atau jadikan parameter `keywords: list[str] = DEFAULT_SCAM_KEYWORDS`.
- **Dampak & Risiko:** Memperluas cakupan deteksi laporan penipuan publik pada SERP.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

---

## 13. Conditional & Branching yang Perlu Dibuat Generic

### 13.1 Kategorisasi Domain Hasil Pencarian Menggunakan Rantai If-Elif Brittle
- **Lokasi:** `backend/app/services/osint/web_evidence.py` (Baris 45–55).
- **Masalah:**
  ```python
  if any(domain in url.lower() for domain in ("tokopedia.com", "shopee.co.id")):
      return "marketplace"
  if any(domain in url.lower() for domain in ("loker", "jobstreet", "glints", "kalibrr", "linkedin.com/jobs", "karir")):
      return "job_portal"
  if any(domain in url.lower() for domain in ("kompas.com", "detik.com", "tribunnews.com")):
      return "news"
  if any(domain in url.lower() for domain in ("instagram.com", "facebook.com", "tiktok.com", "threads.net", "x.com", "twitter.com")):
      return "social_platform"
  ```
- **Kenapa Tidak Fleksibel/Reusable:** Rantai `if/elif` dengan tuple hardcoded di tengah kode menyulitkan penambahan portal kerja baru (misal `kitalulus.com`, `karirhub.kemnaker.go.id`) atau marketplace baru (misal `tiktok shop`, `blibli.com`).
- **Rekomendasi:** Gunakan struktur data mapping berbasis kamus (`dict[str, tuple[str, ...]]`) terpusat dan lakukan pencocokan melalui satu loop generik.
- **Dampak & Risiko:** Penambahan platform baru tidak perlu mengubah logika percabangan kode.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 13.2 Penanganan Output Skema JSON LLM yang Mengasumsikan Key Tertentu
- **Lokasi:** `backend/app/services/llm/client.py` (Baris 128).
- **Masalah:** Percabangan `if isinstance(obj, dict) and "verdict" in obj:` mengunci bahwa objek yang valid harus memiliki key `"verdict"`.
- **Kenapa Tidak Fleksibel/Reusable:** Menolak JSON hasil pemotongan yang valid dari endpoint ekstraksi entitas atau validasi entitas yang tidak memiliki key `"verdict"`.
- **Rekomendasi:** Ubah kondisi menjadi generik: `if isinstance(obj, dict) and (not required_keys or any(k in obj for k in required_keys)): return obj`.
- **Dampak & Risiko:** Parser JSON menjadi reusable untuk semua tugas ekstraksi LLM.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

---

## 14. Konfigurasi Tersebar (Scattered Config) yang Seharusnya Dipusatkan

### 14.1 Daftar Domain Platform Tersebar di 4 Modul Terpisah
- **Lokasi:**
  1. `backend/app/services/osint/search_intelligence.py:31–40` (`_DOMAIN_CATEGORY`)
  2. `backend/app/services/osint/web_evidence.py:46–52` (inline domain tuple di `_classify_source_type`)
  3. `backend/app/services/osint/social.py:14–26` (`_PLATFORM_DOMAINS`)
  4. `backend/app/services/osint/platform_providers.py:15–20` (`_MAPS_PATTERNS`, `_IG_PATTERNS`, `_FB_PATTERNS`, `_LOKER_PATTERNS`)
- **Masalah:** Pemetaan nama domain ke kategori (apakah URL tersebut adalah media sosial, portal loker, marketplace, atau peta) didefinisikan ulang secara berbeda di 4 file terpisah.
- **Kenapa Tidak Fleksibel/Reusable:** Memperbarui domain (seperti domain X/Twitter atau domain lowongan baru) rawan tertinggal di salah satu file dan menyebabkan inkonsistensi klasifikasi sinyal bukti.
- **Rekomendasi:** Pusatkan seluruh pemetaan domain dan pola platform ke dalam satu dictionary kanonikal di `backend/app/services/constants.py` (misal: `PLATFORM_DOMAIN_REGISTRY`).
- **Dampak & Risiko:** Single source of truth untuk seluruh klasifikasi domain web bukti.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

### 14.2 Daftar Stopwords dan Bentuk Badan Hukum Perusahaan Tersebar di 3 File
- **Lokasi:**
  - `backend/app/services/ner.py:57–62` (`_COMPANY_LEGAL`, `_COMPANY_STOP`)
  - `backend/app/services/osint/query_builder.py:5` (`_LEGAL_PREFIX`)
  - `backend/app/services/osint/search_intelligence.py:11` (`_LEGAL_PREFIX_RE`)
- **Masalah:** Daftar bentuk badan hukum Indonesia (PT, CV, UD, PD, Tbk, Firma, Yayasan, Koperasi) didefinisikan dalam tiga regex pattern terpisah dengan variasi cakupan yang tidak identik.
- **Kenapa Tidak Fleksibel/Reusable:** Jika badan hukum baru ditambahkan, harus disinkronkan manual di 3 lokasi.
- **Rekomendasi:** Definisikan regex pattern kanonikal `LEGAL_ENTITY_FORMS_PATTERN` di `app/services/constants.py` dan impor di ketiga modul.
- **Dampak & Risiko:** Sinkronisasi definisi entitas bisnis 100% konsisten.
- **Tingkat Keyakinan:** **Sangat Tinggi (100%)**.

---

## 15. Matriks Rencana Refaktorisasi Terpadu (Design Roadmap)

Berdasarkan seluruh temuan pada Audit Tahap 1 dan Tahap 2, berikut adalah peta jalan refaktorisasi terpadu dengan prinsip:
$$\text{Root Cause} \longrightarrow \text{Perbaiki} \longrightarrow \text{Sederhanakan Logic} \longrightarrow \text{Hapus Redundancy}$$

| Prioritas | Kategori Desain | Target Berkas | Aksi Rekayasa Utama |
| :--- | :--- | :--- | :--- |
| **P1** | **Import-time DB Side Effects** | `community/router.py`, `app/main.py` | Pindahkan eksekusi DDL `create_all` & `ALTER TABLE` dari level import router ke siklus hidup `lifespan` di `app/main.py`. |
| **P1** | **Silent Error Masking** | `verifin_reasoning.py` | Berikan `logger.exception`, satukan fallback LLM menjadi satu fungsi terpadu `_generate_rule_based_fallback`, dan beri label jujur `(Rule-Based Fallback)`. |
| **P1** | **Redundant Search Calls** | `web_evidence.py`, `platform_providers.py` | Lewatkan hasil `intelligent_search` langsung ke ekstraksi bukti platform; hentikan query duplikat SearXNG/Lightpanda yang identik. |
| **P2** | **Redundant Double Calc** | `verify/router.py` | Hilangkan pemanggilan ganda `_to_response` (panggil sekali setelah `case_id` didapatkan dari database). |
| **P2** | **Dead Code & Scraping Cleanup** | `platform_providers.py`, `ai_extractor.py`, `lightpanda_client.py` | Hapus ~350+ baris fungsi scraping mati (`collect_*_evidence`), helper websocket CDP, dan parser DOM medsos yang tidak terpakai. |
| **P2** | **Duplicate & Brittle Phone Logic** | `ner.py`, `fraud_network.py`, `phone_validator.py`, `pipeline.py`, `hasher.py` | Buat utilitas tunggal `canonicalize_indonesian_phone` dan gunakan normalisasi kanonikal sebelum pencocokan keanggotaan set sindikat kasus historis. |
| **P2** | **Syntax Concatenation Bug** | `ner.py` | Perbaiki missing pipe `|` pada `_INDONESIAN_CITIES` (`PatangpuluhanCikarang`) agar Cikarang dapat terdeteksi sebagai kota industri sah. |
| **P3** | **Hardcoded Config to `.env`** | `config.py`, `address_validator.py`, `searxng_client.py`, `ocr.py`, `community/router.py` | Pindahkan URL Nominatim, timeout OSINT, parameter cache SearXNG, batch OCR, dan direktori upload ke `config.py` yang dapat dibaca dari `.env`. |
| **P3** | **Scattered Config to Constants** | `constants.py`, `web_evidence.py`, `social.py`, `search_intelligence.py` | Pusatkan pemetaan domain platform (`PLATFORM_DOMAIN_REGISTRY`) dan badan hukum (`LEGAL_ENTITY_FORMS`) ke `constants.py`. |
| **P3** | **Magic Values to Constants** | `shap_explainer.py`, `verifin_reasoning.py`, `whois_handler.py` | Definisikan konstanta bernama untuk bobot XAI, threshold umur domain baru (90 hari), dan rentang skor verdict (40 & 75). |
| **P3** | **Overfitting Heuristics Cleanup** | `company_validator.py`, `ner.py` | Hapus hardcode entitas uji coba tunggal (`"gizi"`, `"sppg"`, `"RUMAH BAIK CAKRAWALA"`) dan gunakan pola generik taksonomi penipuan lowongan kerja. |
| **P4** | **Unused Logic & Params Cleanup** | `shap_explainer.py`, `pipeline.py`, `health/router.py` | Hapus parameter mati `risk_factors`/`safe_factors` di SHAP, hapus fungsi mati `_merge_entities`, `validate_company`, dan bersihkan key statis palsu `"kredibel": "online"` pada health check. |


---

## 16. Audit Khusus `ner.py`: Disparitas Arsitektur Hybrid NER (Proposal vs Realitas Implementasi)

### 16.1 Kontrak Arsitektur Resmi (Proposal & Laporan Akhir BAB VI.A.1)
Dalam dokumen resmi Laporan Akhir dan Proposal GEMASTIK XIX (*Bab VI Implementasi - Bagian A.1: Layer 1: Named Entity Recognition Hibrida*), arsitektur Layer 1 dirancang dengan pembagian tanggung jawab komplementer yang sangat tegas:
1. **Mekanisme Deterministik (Regex):** Dikhususkan HANYA untuk entitas **struktural** yang memiliki pola sintaksis stabil:
   - Nomor telepon/WhatsApp (`PHONE`)
   - Alamat email (`EMAIL`)
   - URL/domain (`URL`)
   *Karakteristik:* Cepat, tanpa biaya API, dan presisi tinggi pada tata bahasa formal.
2. **Mekanisme Semantik (LLM API):** Dikhususkan untuk entitas **semantik** yang tidak memiliki tata bahasa tetap dan rentan terhadap variasi layout poster OCR yang berantakan:
   - Nama perusahaan / instansi pemberi kerja (`ORG`)
   - Alamat fisik / lokasi penempatan kerja (`LOC`)
   - Informasi rentang gaji / benefit (`SALARY`)
   *Karakteristik:* Memahami konteks semantik bahasa alami, kebal terhadap variasi kolom atau salah baca OCR.
3. **Strategi Penggabungan (Hybrid Merge Strategy):**
   - Untuk `ORG` (perusahaan): Output LLM bersifat **otoritatif** sehingga false-positive regex (frasa deskriptif yang kebetulan mirip nama PT) otomatis tersaring.
   - Untuk `LOC` dan `SALARY`: Keduanya digabung secara **aditif**.
   - Bila LLM tidak tersedia (offline/error), barulah sistem beralih ke *fallback* regex murni agar pipeline tidak terputus.

### 16.2 Realitas Implementasi di `ner.py`: Mengapa Menjadi 933 Baris Hardcode?
Di dalam kode implementasi saat ini, berkas `backend/app/services/ner.py` membengkak menjadi **933 baris** kode yang sarat dengan heuristik kaku, regex bertingkat yang rapuh, dan daftar token hardcode. Hal ini terjadi karena:

1. **Pelanggaran Batas Tanggung Jawab:**
   `ner.py` tidak hanya mengekstrak entitas struktural (`PHONE`, `EMAIL`, `URL`), melainkan berusaha keras memecahkan persoalan entitas semantik (`ORG`, `LOC`, `SALARY`) menggunakan **ratusan baris aturan regex deterministik ad-hoc**:
   - `_extract_companies` (Baris 450–623, ~174 baris): Memiliki 6 cabang regex heuristik yang menebak nama perusahaan berdasarkan posisi baris sebelum `"WE'RE HIRING"`, baris setelah kata `"DIBUTUHKAN"`, mencari kata `"merupakan perusahaan"`, dan membedah domain email.
   - `_extract_addresses` (Baris 626–728, ~102 baris): Memecah baris teks, menyambung koma, mencari label lokasi, dan memeriksa pola jalan.

2. **Tumpukan Kamus Hardcode Raksasa:**
   - `_INDONESIAN_CITIES` (Baris 23–50): String regex raksasa memuat 150+ nama kota, kabupaten, kecamatan, hingga padukuhan di Kabupaten Sleman/Bantul DIY. Terjadi bug sintaksis konkatenasi pada baris 44–45 (`PatangpuluhanCikarang`) yang merusak pengenalan kota Cikarang.
   - `_split_stuck_company_tokens` (Baris 398–421): Menyisipkan 19 kata hardcode uppercase, termasuk kata `"RUMAH"`, `"BAIK"`, `"CAKRAWALA"`, semata-mata demi meloloskan satu sampel poster OCR pengujian yang kata-katanya menempel.
   - `_BRAND_STOP`, `_COMPANY_STOP`, `_ADDR_STOP` (Baris 58–70): Daftar puluhan kata henti bahasa Indonesia yang ditulis statis.
   - `_SOCIAL_UI_NOISE_PATTERNS` (Baris 73–89): Daftar regex noise antarmuka Instagram yang didefinisikan namun mati (tidak pernah dipanggil di dalam file).

3. **Algoritma Skoring Manual yang Rapuh (Handcrafted Probabilistic Scoring):**
   - `_address_confidence` (Baris 264–311): Heuristik buatan tangan yang menambah skor $+0.25$ jika ada kode pos, $+0.2$ jika cocok nama kota di `_INDONESIAN_CITIES`, $-0.4$ jika ada kata gaji, $+0.15$ jika ada nomor bangunan. Ini adalah upaya meniru classifier probabilistik secara manual yang sangat rapuh terhadap variasi teks nyata.

### 16.3 Efek Domino pada Arsitektur Sistem (The Cascade of Technical Debt)
Karena `ner.py` memaksakan ekstraksi semantik melalui regex kaku, timbul efek domino yang merusak efisiensi pipeline secara keseluruhan:

1. **Ledakan False Positives:**
   Regex perusahaan dan alamat sering mengekstrak frasa deskriptif (*"Bersedia training"*, *"Kirim CV dan lamaran"*, *"Pria/Wanita"*, *"Syarat Kualifikasi"*) sebagai nama PT atau alamat kantor.
2. **Kelahiran Modul `entity_validator.py` (LLM Call Tambahan):**
   Untuk menambal kelemahan false-positive dari `ner.py`, pengembang terpaksa membuat modul baru `backend/app/services/llm/entity_validator.py` (`validate_entities_llm`). Modul ini mengirim prompt ke LLM HANYA untuk menanyakan: *"Apakah entitas hasil regex ini valid atau sampah?"*.
3. **Penggandaan Panggilan API LLM di Layer 1:**
   Di `backend/app/api/v1/verify/pipeline.py` (Baris 139–142):
   ```python
   llm_extracted, llm_validated = await asyncio.gather(
       _run_llm_ner(clean_text),
       _run_llm_validation(clean_text, regex_entities),
   )
   ```
   Sistem mengeksekusi **DUA panggilan LLM API secara paralel** pada setiap verifikasi: satu untuk ekstraksi semantik (`extract_entities_llm`), dan satu lagi untuk validasi hasil regex (`validate_entities_llm`)!
4. **Pembengkakan Biaya dan Latensi:**
   - Ditambah LLM Layer 3 (`verifin_reasoning`) dan LLM web bukti (`platform_providers.py`), satu verifikasi lowongan kerja dapat menghabiskan **3 hingga 4 kali panggilan API LLM**.
   - Hal ini menggandakan biaya komputasi (mengancam estimasi Rp300/transaksi dan target BCR 1.259:1 pada proposal) serta menambah latensi antrean API hingga 5–10 detik.

### 16.4 Solusi Refaktorisasi: Mengembalikan Fitrah Desain Hybrid NER
Untuk mengembalikan arsitektur sesuai prinsip ilmiah Proposal dan Laporan Akhir:

1. **Rampingkan `ner.py` Murni untuk Entitas Struktural (~120–150 Baris):**
   - Pertahankan dan rapikan regex berakurasi tinggi untuk:
     - `phones`: Nomor kontak Indonesia (+62 / 08xx) berstandar kanonikal.
     - `emails`: Alamat email standar + koreksi typo OCR domain umum.
     - `urls`: Hyperlink dan domain valid (tanpa noise).
   - Hapus ratusan baris heuristik tebak layout, scoring alamat manual, dan kamus kota hardcode dari `ner.py`.

2. **Serahkan Entitas Semantik Sepenuhnya ke LLM Layer 1 (`extract_entities_llm`):**
   - `companies`, `addresses`, `location_candidates`, dan `salaries` diekstrak langsung oleh prompt `extract_entities_llm` yang sudah ada di `entity_extraction.py`. LLM terbukti jauh lebih cerdas memahami konteks poster tanpa butuh aturan baris/kolom.

3. **Hapus Modul `entity_validator.py`:**
   - Karena regex tidak lagi memaksakan ekstraksi entitas semantik yang berisik, kebutuhan validasi LLM kedua gugur. Menghapus modul ini langsung menghemat 1 panggilan LLM API pada setiap transaksi verifikasi.

4. **Jadikan Regex Perusahaan & Alamat sebagai Fallback Ringan (Offline Only):**
   - Logika ekstraksi regex untuk perusahaan dan alamat hanya dijalankan jika API LLM mati atau timeout (mode fallback), menggunakan pola minimal yang aman (misal hanya menangkap prefix resmi `PT/CV/UD/Yayasan` dan prefix jalan `Jl./Jalan`).

5. **Sederhanakan Logika Penggabungan di `pipeline.py`:**
   - `entities["phones"] = regex_entities["phones"]`
   - `entities["emails"] = regex_entities["emails"]`
   - `entities["urls"] = regex_entities["urls"]`
   - `entities["companies"] = llm_entities.get("companies") or regex_fallback_companies`
   - `entities["addresses"] = llm_entities.get("addresses") or regex_fallback_addresses`
   - `entities["location_candidates"] = llm_entities.get("location_candidates") or []`
   - `entities["salaries"] = llm_entities.get("salaries") or []`
   Menghilangkan puluhan baris fuzzy string matching dan normalisasi rumit di `pipeline.py`.
---
*Dokumen ini disusun untuk melengkapi pelaporan perbaikan rekayasa perangkat lunak Verifin, memastikan kode bersih, maintainable dalam jangka panjang, dan bebas dari ketergantungan rapuh pada data uji coba tunggal.*
