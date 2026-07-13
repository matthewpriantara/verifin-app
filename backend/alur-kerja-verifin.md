# Alur Kerja Verifin (Arsitektur Hybrid Detektif)

Dokumen ini menjelaskan mengapa kita menggunakan gabungan OCR, NER, Agen OSINT, dan LLM (Hermes) dalam sistem Verifin, dianalogikan sebagai sebuah **Tim Detektif Forensik**.

---

## Mengapa Tidak Menggunakan LLM Saja untuk Semuanya?
LLM (seperti Hermes/GPT-4) memang pintar, tapi mereka memiliki kekurangan mendasar jika dipaksa melakukan semua hal:
1. **Lambat:** Membaca gambar panjang dan mencari entitas teks memakan waktu lama.
2. **Mahal (Boros Resource):** Semakin panjang teks/gambar yang dimasukkan, semakin banyak "token" yang terbakar.
3. **Rawan Halusinasi:** LLM kadang salah mengekstrak format nomor telepon yang rumit atau URL yang terselip.

Oleh karena itu, Verifin menggunakan **Arsitektur Hybrid**. Setiap komponen melakukan hal yang paling dikuasainya.

---

## Alur Kerja (Analogi Tim Detektif)

### Tahap 1: Pengumpul Barang Bukti (OCR & NER)
*(File: `app/services/ocr.py` & `app/services/ner.py`)*

Saat pengguna (user) mengirimkan *screenshot* atau teks lowongan pekerjaan, komponen pertama yang bekerja adalah OCR dan NER.
*   **PaddleOCR:** Bertugas menterjemahkan gambar menjadi teks kasar.
*   **IndoBERT NER & Regex:** Menyisir teks kasar tersebut untuk mengekstrak entitas penting (barang bukti) secara spesifik dan akurat, seperti:
    *   Nama Perusahaan/PT
    *   Nomor Telepon (diubah ke format standar `+62`)
    *   Tautan URL / Email
    *   Alamat Fisik
    *   Gaji
*   **Tujuan:** Mengelompokkan dan merapikan inputan user agar siap diinvestigasi.

### Tahap 2: Tim Intel & Investigasi (Agen OSINT)
*(File: `app/services/osint/`)*

Setelah "barang bukti" terpisah dengan rapi, sistem melempar masing-masing entitas ke agen intelijen spesifik secara paralel (bersamaan):
*   **WHOIS Checker:** Mengecek URL. *(Contoh hasil: "Domain www.karir-palsu.com baru dibuat 2 hari lalu.")*
*   **GetContact Scraper:** Mengecek Nomor HP. *(Contoh hasil: "Nomor ini memiliki tag 'Penipu Loker'.")*
*   **Company Validator:** Mengecek nama PT ke database lokal (Kemenkumham/OSS). *(Contoh hasil: "PT fiktif, tidak ditemukan di database.")*

### Tahap 3: Sang Hakim & Analis Utama (Hermes LLM)
*(File: `app/services/llm/hermes_reasoner.py`)*

Di sinilah letak kecerdasan puncaknya. Hermes LLM **tidak disuruh** membaca gambar atau mencari nomor telepon. Hermes hanya menerima "Laporan Matang" dari Tahap 2.

Sistem memberikan *prompt* (perintah) kepada Hermes seperti ini:
> *"Berdasarkan data OSINT: Email menggunakan Gmail, Domain web baru berumur 2 hari, Nomor HP memiliki tag Penipu. Buatkan kesimpulan forensik dan hitung persentase bahaya."*

Karena datanya sudah bersih dan jelas, Hermes dapat melakukan **Reasoning (Penalaran)** dengan sangat cepat, akurat, dan merespon dalam format JSON yang rapi:

```json
{
  "risk_score": 98,
  "verdict": "BAHAYA",
  "reasons": [
    "Domain baru berumur 2 hari, ciri khas situs phising.",
    "Nomor telepon memiliki reputasi buruk.",
    "Perusahaan besar tidak menggunakan email gratisan (Gmail)."
  ]
}
```

---

## Kesimpulan
Pendekatan "Hybrid" ini memastikan sistem Verifin bekerja dengan **Cepat (latensi rendah)**, **Murah (hemat komputasi token)**, dan **Sangat Akurat (pengurangan halusinasi AI)**. Hasil JSON dari Hermes inilah yang nantinya akan ditampilkan di Dashboard Frontend (Next.js) atau dibalas ke pengguna via WhatsApp Bot.
