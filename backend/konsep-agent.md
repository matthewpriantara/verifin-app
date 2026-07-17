# Konsep Agent AI di Verifin Backend

Halo! Project Verifin-mu ini keren banget, menggunakan konsep **Arsitektur Hybrid Detektif** untuk memvalidasi lowongan kerja. Ini penjelasan santai tapi mendalam tentang gimana konsep agent, Ollama, dan model Hermes bekerja bareng di backend ini.

---

## 1. Konsep Dasar Agent di Verifin

Secara garis besar, backend Verifin tidak bergantung pada satu AI besar (LLM) untuk melakukan segalanya. Kenapa? Karena LLM itu mahal secara *resource* (token) dan bisa sangat lambat kalau disuruh baca gambar atau nyari data spesifik di internet. 

Jadi, sistem ini menggunakan **Arsitektur Multi-Agent (Pipeline)**. Bayangin aja ini kayak satu tim detektif yang punya peran masing-masing:

### A. Agen Pengekstrak (Tahap 1: Pengumpul Barang Bukti)
Ini bukan LLM, tapi model AI spesifik yang tugasnya cuma satu: **ngambil data mentah (gambar/teks) dan merapikannya.**
- **OCR (PaddleOCR):** "Mata" dari sistem. Dia baca gambar *screenshot* loker dan ngubahnya jadi teks.
- **NER (IndoBERT NER + Regex):** "Pemilah" dari sistem. Dia baca teks dari OCR, lalu misahin mana yang nama PT, mana nomor HP (langsung diformat `+62`), email, alamat, dan gaji.

### B. Agen Investigator/OSINT (Tahap 2: Tim Intel)
Setelah data rapi, diserahkan ke agen-agen spesifik yang jalan **secara paralel** (barengan biar cepet). Mereka ini yang cari data asli di lapangan:
- **WHOIS Checker (Domain):** Ngecek URL atau email. *"Oh, emailnya pake domain company, tapi domainnya baru dibuat 2 hari lalu."*
- **Address Validator (OpenStreetMap):** Ngecek alamat. *"Alamat ini beneran ada nggak sih di peta? Ada bisnis yang namanya mirip nggak di kordinat itu?"*
- *(Nantinya bisa ada GetContact Scraper buat ngecek tag nomor HP, dll).*

### C. Agen Analis Utama / Reasoner (Tahap 3: Sang Hakim - LLM Hermes)
Nah, di tahap terakhir inilah LLM masuk. LLM **sama sekali tidak** disuruh baca gambar atau nyari data di internet. Dia cuma nerima **laporan matang** dari Agen Pengekstrak dan Agen Investigator.

- **Model:** Hermes (via Ollama).
- **Tugas:** Menimbang bukti, melakukan *reasoning* (penalaran logika), memberikan vonis akhir, dan ngeluarin format JSON yang rapi.

---

## 2. Peran Ollama + Hermes

Di dalam folder `app/services/llm/hermes_reasoner.py` dan `app/services/llm/prompt_builder.py`, kamu menggunakan **Ollama** untuk menjalankan model **Hermes** secara lokal. 

### Kenapa Ollama + Hermes?
- **Ollama:** Ini ibarat mesin atau *runner*-nya. Ollama bikin gampang jalanin LLM berat di server/komputer lokal tanpa ribet *setup* PyTorch/CUDA manual yang njelimet. Cukup panggil API-nya di `http://localhost:11434`.
- **Hermes:** Ini adalah model AI-nya (kemungkinan `hermes3` berdasarkan *code*-mu). Model keluarga Hermes (seperti Nous Hermes) terkenal sangat bagus dalam *instruction following* (nurut perintah), *reasoning* logika, dan yang paling penting: **jago nge-output format JSON murni**. Ini penting banget buat backend karena hasil akhirnya harus bisa dibaca oleh *frontend* (Next.js) atau bot.

### Bagaimana Sistematis Prompting-nya?
Sistematis *prompting* (memberi perintah ke AI) di Verifin ini sangat terstruktur dan dinamis (bisa dilihat di `prompt_builder.py`):

1. **Dinamis:** Prompt-nya dibentuk berdasarkan hasil investigasi OSINT. 
   *Contoh:* Kalau emailnya `gmail.com`, prompt akan otomatis ngasih tahu LLM: *"Ini email gratisan, nggak bisa dicek umur/keamanannya, ini risiko besar kalau dia ngaku PT."* Tapi kalau email korporat, prompt bakal ngasih hasil WHOIS dan SPF/DMARC.
2. **Konteks Spesifik:** Prompt ngasih tau LLM secara spesifik untuk membedakan antara UMKM dan PT besar. *"Kalau UMKM, wajar nggak punya website, jangan disalahkan. Kalau PT besar pake gmail, baru curigai."*
3. **Format Ketat:** Prompt memerintahkan LLM (dan diset *temperature* rendah = 0.1 biar nggak ngarang) untuk output murni format JSON berisi: `verdict`, `risk_score`, `summary`, `risk_factors`, `safe_factors`, dan `recommendations`.

---

## 3. Alur Sistematis (Dari Request sampai Response)

Kalau ada user (dari *frontend* atau WA) *upload* gambar loker, ini urutan jalannya:

1. **`main.py` atau Worker:** Menerima *request*.
2. **`ocr.py`:** Membaca teks di gambar loker.
3. **`ner.py`:** Mengekstrak nama PT, email, nomor HP, alamat.
4. **`osint/` (Parallel):**
   - Ngecek domain dari email di atas.
   - Ngecek kordinat alamat di OpenStreetMap.
5. **`prompt_builder.py`:** Merakit semua data (Teks Asli, Data Terekstrak, Hasil OSINT) jadi satu teks instruksi (prompt) yang super lengkap buat AI.
6. **`hermes_reasoner.py`:** Ngirim *prompt* tadi ke Ollama (`POST http://localhost:11434/api/generate`).
7. **Ollama (Hermes):** Berpikir sejenak, lalu membalas dengan JSON yang berisi analisa risiko penipuan.
8. **Backend:** Mengembalikan JSON tersebut ke *frontend* untuk ditampilkan!

Konsep *hybrid* gini brilian banget, bro. Bikin sistem jadi **cepat** (karena tugas berat dibagi-bagi) dan **murah/aman** (karena nggak nge-hit API berbayar kayak GPT-4 terus-terusan, semuanya lokal). Mantap! 🚀