"""
Prompt Builder untuk Verifin AI Reasoning Engine.
Mengubah data OSINT & NER yang sudah diekstrak menjadi prompt terstruktur
yang siap dikirim ke LLM (Hermes via Ollama) untuk analisis risiko penipuan.
"""

# Domain gratisan yang umum digunakan — tidak perlu dicek WHOIS/SPF/DMARC
FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "yahoo.co.id", "hotmail.com",
    "outlook.com", "live.com", "ymail.com", "icloud.com",
    "protonmail.com", "mail.com"
}


def _build_domain_osint_section(emails: list, domain_info: dict, email_security: dict) -> str:
    """
    Membangun teks section OSINT domain secara kondisional:
    - Jika tidak ada email: tampilkan pesan 'tidak ada email'.
    - Jika email adalah domain gratisan (gmail, yahoo, dll): hanya tampilkan info domain gratisan.
    - Jika email adalah domain korporat: tampilkan info WHOIS + SPF/DMARC lengkap.
    """
    if not emails:
        return "- Tidak ada email yang terdeteksi pada lowongan ini. Abaikan faktor keamanan domain dalam analisis."

    first_email = emails[0]
    domain = first_email.split("@")[-1].lower() if "@" in first_email else ""

    if domain in FREE_EMAIL_DOMAINS:
        return (
            f"- Email menggunakan domain GRATISAN: `{domain}` (misal: gmail, yahoo).\n"
            "- ⚠️ Domain gratisan TIDAK dapat dicek umur/SPF/DMARC karena bukan domain perusahaan.\n"
            "- Ini adalah faktor risiko utama jika perusahaan mengaku sebagai instansi resmi atau PT."
        )

    # Domain korporat — tampilkan data OSINT lengkap
    domain_age = domain_info.get("age_years", "Tidak diketahui")
    domain_created = domain_info.get("created_at", "Tidak diketahui")
    domain_is_new = domain_info.get("is_new", False)
    spf_ok = email_security.get("spf_active", False)
    dmarc_ok = email_security.get("dmarc_active", False)

    return (
        f"- Domain: `{domain}`\n"
        f"- Umur Domain: {domain_age} tahun (dibuat pada: {domain_created})\n"
        f"- Kategori: {'⚠️ DOMAIN BARU (< 1 tahun)' if domain_is_new else '✅ Domain sudah lama'}\n"
        f"- Proteksi SPF: {'✅ Aktif' if spf_ok else '❌ Tidak Aktif (Rentan pemalsuan email)'}\n"
        f"- Proteksi DMARC: {'✅ Aktif' if dmarc_ok else '❌ Tidak Aktif'}"
    )


def _build_address_osint_section(address_validations: list) -> str:
    """
    Membangun teks section hasil validasi alamat dari OpenStreetMap
    untuk disisipkan ke dalam prompt LLM.
    """
    if not address_validations:
        return "- Tidak ada alamat yang berhasil divalidasi."

    lines = []
    for av in address_validations:
        addr = av.get("address_input", "?")
        found = av.get("address_found", False)
        biz_found = av.get("business_found")
        biz_details = av.get("business_details", {})
        error = av.get("error")

        if error:
            lines.append(f"- `{addr}`: Gagal divalidasi ({error})")
            continue

        if not found:
            lines.append(f"- `{addr}`: ❌ TIDAK DITEMUKAN di peta Indonesia (kemungkinan alamat fiktif).")
            continue

        # Alamat ditemukan di peta
        display = av.get("address_details", {}).get("display_name", "")[:80]
        lines.append(f"- `{addr}`: ✅ Alamat valid di peta ({display}...).")

        # Catatan netral dari pencarian bisnis
        neutral_notes = av.get("neutral_notes", [])
        for note in neutral_notes:
            lines.append(f"  → ℹ️ {note}")

        if biz_found is True:
            matched = biz_details.get("matched_name", "?")
            sim = biz_details.get("similarity", 0) * 100
            lines.append(f"  → ✅ Nama perusahaan ditemukan di OSM dekat lokasi: '{matched}' (kemiripan {sim:.0f}%).")
        elif biz_found is False and not neutral_notes:
            lines.append("  → ⚠️ Nama bisnis tidak ditemukan di peta sekitar koordinat.")
        elif biz_found is None:
            lines.append("  → ℹ️ Tidak ada nama perusahaan untuk dicocokkan di peta.")

    return "\n".join(lines) if lines else "- Validasi alamat tidak tersedia."


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
    email_str = ", ".join(emails) if emails else "Tidak ada email yang terdeteksi"
    url_str = ", ".join(urls) if urls else "Tidak ada"
    address_str = "\n  - ".join(addresses) if addresses else "Tidak disebutkan"
    salary_str = ", ".join(salaries) if salaries else "Tidak disebutkan"
    
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
{_build_domain_osint_section(emails, domain_info, email_security)}

**Validasi Alamat Fisik (OpenStreetMap):**
{_build_address_osint_section(osint_results.get("address_validations", []))}

---

## INSTRUKSI ANALISIS

Berdasarkan data di atas, lakukan analisis mendalam dengan mempertimbangkan:
1. Apakah email perusahaan menggunakan domain gratisan (gmail, yahoo, dll.) padahal mengaku sebagai perusahaan besar/PT resmi?
2. Apakah domain email baru dibuat (< 1 tahun) yang menunjukkan perusahaan fiktif?
3. Apakah gaji yang ditawarkan tidak realistis atau tidak disebutkan sama sekali (taktik umum penipu)?
4. Apakah alamat fisik terdengar valid atau mencurigakan?
5. Apakah tidak ada website resmi perusahaan yang dicantumkan?
6. Apakah proteksi SPF/DMARC tidak aktif? (Hanya pertimbangkan ini jika email ditemukan dan BUKAN domain gratisan seperti gmail/yahoo).
7. WAJIB tentukan nama bisnis lengkap dari TEKS ASLI LOWONGAN (misalnya: jika teks asli menulis 'SEKOTAK ROTI' tetapi di data tertulis 'Roti', maka corrected_company_name harus diisi 'Sekotak Roti').
8. PENTING - KLASIFIKASI SKALA BISNIS:
   - Jika ini adalah bisnis UMKM/Informal (toko, bakery, cafe, warung, dll. tanpa PT/CV): Ketiadaan website resmi atau email korporat adalah HAL YANG SANGAT WAJAR. Jika alamat fisiknya valid di peta dan ada nomor kontak (WA), lowongan ini harus dikategorikan **AMAN (Verdict: AMAN, skor 15-35)**. Jangan mengarang risiko palsu hanya karena tidak ada email.
   - Jika ini adalah perusahaan besar/Formal (menggunakan nama PT/CV resmi): Penggunaan email gratisan (gmail/yahoo) harus dinilai sebagai **WASPADA (skor 40-55)** untuk kehati-hatian, bukan langsung BAHAYA.
9. DILARANG KERAS BERHALUSINASI GEOGRAFIS: Jangan pernah mengarang bahwa suatu alamat di daerah perkotaan/pemukiman Jawa (seperti Yogyakarta, Sleman, Bantul, Jakarta, dll.) sebagai "terpencil" atau "mencurigakan" jika alamat tersebut valid ditemukan di peta.

---

## FORMAT OUTPUT (WAJIB JSON)

Berikan output HANYA dalam format JSON berikut, tanpa teks lain di luar JSON:

{{
  "verdict": "AMAN",
  "risk_score": 25,
  "corrected_company_name": "Sekotak Roti",
  "summary": "Lowongan ini aman karena alamat valid di peta dan profil UMKM lokal yang wajar menggunakan WhatsApp.",
  "risk_factors": [],
  "safe_factors": [
    "Alamat fisik valid di peta",
    "Kualifikasi pekerjaan realistis"
  ],
  "recommendations": [
    "Hubungi nomor WhatsApp tertera untuk konfirmasi lowongan"
  ]
}}

Pastikan format JSON di atas diikuti persis dengan struktur field yang sama untuk output analisismu.
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
