"""
Prompt Builder untuk Verifin AI Reasoning Engine.
Mengubah data OSINT & NER yang sudah diekstrak menjadi prompt terstruktur
yang siap dikirim ke LLM (Hermes via Ollama) untuk analisis risiko penipuan.
"""

def build_verify_prompt(entities: dict, osint_results: dict) -> str:
    """
    Membangun prompt lengkap untuk analisis penipuan loker kerja.
    
    Args:
        entities: Dict hasil ekstraksi NER (companies, contacts, emails, addresses, salaries).
        osint_results: Dict hasil pengecekan OSINT (domain_age, email_security, whois, dll).
        
    Returns:
        String prompt terstruktur yang siap dikirim ke Hermes LLM.
    """
    
    companies = entities.get("companies", [])
    contacts = entities.get("contacts", [])
    emails = entities.get("emails", [])
    urls = entities.get("urls", [])
    addresses = entities.get("addresses", [])
    salaries = entities.get("salaries", [])
    
    domain_info = osint_results.get("domain", {})
    email_security = osint_results.get("email_security", {})
    
    # Format data entitas ke dalam teks yang mudah dibaca LLM
    company_str = ", ".join(companies) if companies else "Tidak disebutkan"
    contact_str = ", ".join(contacts) if contacts else "Tidak disebutkan"
    email_str = ", ".join(emails) if emails else "Tidak disebutkan"
    url_str = ", ".join(urls) if urls else "Tidak ada"
    address_str = "\n  - ".join(addresses) if addresses else "Tidak disebutkan"
    salary_str = ", ".join(salaries) if salaries else "Tidak disebutkan"
    
    # Format data OSINT domain
    domain_age = domain_info.get("age_years", "Tidak diketahui")
    domain_created = domain_info.get("created_at", "Tidak diketahui")
    domain_is_new = domain_info.get("is_new", False)
    spf_ok = email_security.get("spf_active", False)
    dmarc_ok = email_security.get("dmarc_active", False)
    
    prompt = f"""Kamu adalah sistem AI bernama Verifin yang bertugas menganalisis kecurigaan penipuan lowongan kerja di Indonesia.

Kamu akan diberikan data hasil ekstraksi dari poster/iklan lowongan kerja, beserta hasil pengecekan OSINT (Open Source Intelligence). 
Analisis secara mendalam dan berikan keputusan apakah lowongan ini AMAN, WASPADA, atau BAHAYA.

---

## DATA LOWONGAN KERJA

**Nama Perusahaan:**
{company_str}

**Nomor HP / Kontak:**
{contact_str}

**Alamat Email:**
{email_str}

**Website / URL:**
{url_str}

**Alamat Fisik:**
  - {address_str}

**Gaji yang Ditawarkan:**
{salary_str}

---

## HASIL PENGECEKAN OSINT

**Domain Email:**
- Umur Domain: {domain_age} tahun (dibuat pada: {domain_created})
- Kategori: {"⚠️ DOMAIN BARU (< 1 tahun)" if domain_is_new else "✅ Domain sudah lama"}
- Proteksi SPF: {"✅ Aktif" if spf_ok else "❌ Tidak Aktif (Rentan pemalsuan email)"}
- Proteksi DMARC: {"✅ Aktif" if dmarc_ok else "❌ Tidak Aktif"}

---

## INSTRUKSI ANALISIS

Berdasarkan data di atas, lakukan analisis mendalam dengan mempertimbangkan:
1. Apakah email perusahaan menggunakan domain gratisan (gmail, yahoo, dll.) padahal mengaku sebagai perusahaan besar/PT resmi?
2. Apakah domain email baru dibuat (< 1 tahun) yang menunjukkan perusahaan fiktif?
3. Apakah gaji yang ditawarkan tidak realistis atau tidak disebutkan sama sekali (taktik umum penipu)?
4. Apakah alamat fisik terdengar valid atau mencurigakan?
5. Apakah tidak ada website resmi perusahaan yang dicantumkan?
6. Apakah proteksi SPF/DMARC tidak aktif (tanda bahwa domain sengaja disiapkan untuk phishing)?
7. Tentukan nama lengkap dan benar dari perusahaan perekrut berdasarkan teks asli (raw text). Jika hasil ekstraksi entitas ('Nama Perusahaan') terpotong (misal hanya 'Roti' padahal di teks ada 'SEKOTAK ROTI'), koreksi menjadi nama lengkapnya yang valid.

---

## FORMAT OUTPUT (WAJIB JSON)

Berikan output HANYA dalam format JSON berikut, tanpa teks lain di luar JSON:

{{
  "verdict": "AMAN" | "WASPADA" | "BAHAYA",
  "risk_score": <angka 0-100>,
  "corrected_company_name": "<nama lengkap perusahaan yang benar berdasarkan analisis teks asli loker, atau null jika sudah benar/tidak ada>",
  "summary": "<ringkasan singkat 1-2 kalimat mengapa verdict ini diberikan>",
  "risk_factors": [
    "<faktor risiko spesifik 1>",
    "<faktor risiko spesifik 2>"
  ],
  "safe_factors": [
    "<faktor aman spesifik 1>"
  ],
  "recommendations": [
    "<saran tindakan untuk pencari kerja 1>",
    "<saran tindakan untuk pencari kerja 2>"
  ]
}}

Pastikan risk_score konsisten dengan verdict:
- AMAN: 0-39
- WASPADA: 40-74  
- BAHAYA: 75-100
"""
    return prompt.strip()


def build_text_verify_prompt(raw_text: str, entities: dict, osint_results: dict) -> str:
    """
    Versi prompt yang juga menyertakan teks kasar asli dari OCR
    sebagai konteks tambahan untuk LLM.
    """
    base_prompt = build_verify_prompt(entities, osint_results)
    
    # Sisipkan teks kasar OCR sebagai konteks tambahan
    raw_section = f"""
## TEKS ASLI LOWONGAN (Hasil OCR / Input Manual)

```
{raw_text[:2000]}{"...(terpotong)" if len(raw_text) > 2000 else ""}
```

"""
    # Sisipkan sebelum "## DATA LOWONGAN KERJA"
    return base_prompt.replace("## DATA LOWONGAN KERJA", raw_section + "## DATA LOWONGAN KERJA")
