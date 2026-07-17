"""
Prompt Builder untuk Verifin AI Reasoning Engine.
Mengubah data OSINT & NER yang sudah diekstrak menjadi prompt terstruktur
yang siap dikirim ke LLM (OpenAgentic / Grok) untuk analisis risiko penipuan.
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


def _build_phone_osint_section(phones: list) -> str:
    if not phones:
        return "- Tidak ada nomor HP yang dicek."
    lines = []
    for p in phones:
        phone = p.get("phone") or p.get("phone_local") or "?"
        if p.get("error") and not p.get("found"):
            lines.append(f"- `{phone}`: gagal dicek ({p.get('error')})")
            continue
        parts = [f"- `{phone}` via Kredibel"]
        if p.get("rating") is not None:
            parts.append(f"rating {p.get('rating')}")
        if p.get("review_count") is not None:
            parts.append(f"{p.get('review_count')} review")
        if p.get("reported_fraud"):
            parts.append("⚠️ PERNAH DILAPORKAN PENIPUAN")
        if p.get("url"):
            parts.append(f"sumber: {p.get('url')}")
        lines.append(" | ".join(parts))
        for f in p.get("risk_flags") or []:
            lines.append(f"  → {f}")
        if p.get("summary"):
            lines.append(f"  → ringkas: {p.get('summary')}")
    return "\n".join(lines) if lines else "- Tidak ada data telepon."


def _build_company_osint_section(companies: list) -> str:
    if not companies:
        return "- Tidak ada pengecekan nama PT/perusahaan."
    lines = []
    for c in companies:
        name = c.get("name") or "?"
        lines.append(f"- Nama: `{name}` | method={c.get('method', 'public_web_only')}")
        reg = c.get("registry") or {}
        lines.append(
            f"  → Legalitas AHU/OSS per-entitas: "
            f"{'TERVERIFIKASI' if reg.get('pt_registry_verified') else 'BELUM TERVERIFIKASI (jangan dikarang)'}"
        )
        if reg.get("disclaimer"):
            lines.append(f"  → Disclaimer: {reg.get('disclaimer')}")
        stats = c.get("stats") or {}
        if stats:
            lines.append(
                f"  → Jejak search: {stats.get('public_mentions', 0)} hasil, "
                f"indikasi penipuan di SERP: {stats.get('fraud_related_mentions', 0)}"
            )
        for ev in (c.get("evidence") or [])[:6]:
            et = ev.get("type")
            if et == "website_fetch":
                lines.append(
                    f"  → [FETCH] {ev.get('url')} ok={ev.get('ok')} title={(ev.get('title') or '')[:60]}"
                )
            elif et == "web_search":
                lines.append(f"  → [SEARCH] q=`{ev.get('query')}` ok={ev.get('ok')}")
                for r in (ev.get("results") or [])[:2]:
                    lines.append(
                        f"     · {(r.get('title') or '')[:90]} | {r.get('url')}"
                    )
            elif et == "registry_portal_probe":
                lines.append(
                    f"  → [AHU PORTAL] {ev.get('url')} ok={ev.get('ok')} — {ev.get('note', '')[:120]}"
                )
        for f in c.get("risk_flags") or []:
            lines.append(f"  → ⚠️ {f}")
        for f in c.get("safe_flags") or []:
            lines.append(f"  → ✅ {f}")
        if c.get("error"):
            lines.append(f"  → error: {c.get('error')}")
    return "\n".join(lines)


def _build_web_osint_section(web: dict) -> str:
    if not web:
        return "- Tidak ada data web evidence."
    if web.get("error") and not web.get("websites") and not web.get("searches"):
        return f"- Web evidence error: {web.get('error')}"

    lines = [f"- Engine: {web.get('engine', 'scrapling')}"]
    for w in (web.get("websites") or [])[:3]:
        if w.get("ok"):
            lines.append(
                f"- Website OK: {w.get('url')} | title: {(w.get('title') or '-')[:80]}"
            )
            if w.get("snippet"):
                lines.append(f"  → cuplikan: {w.get('snippet')[:180]}")
        else:
            lines.append(
                f"- Website GAGAL: {w.get('url')} ({w.get('error') or w.get('status')})"
            )
        for f in w.get("risk_flags") or []:
            lines.append(f"  → ⚠️ {f}")
        for f in w.get("safe_flags") or []:
            lines.append(f"  → ✅ {f}")

    for gf in web.get("gform_inspections") or []:
        if gf.get("is_gform"):
            lines.append(f"- Google Form Inspection: `{gf.get('url')}`")
            lines.append(f"  · Judul Formulir: {gf.get('form_title')}")
            qs = gf.get("questions") or []
            if qs:
                qs_str = ", ".join(qs[:5])
                lines.append(f"  · Pertanyaan Formulir: {qs_str}")
            if gf.get("has_phishing_signals"):
                lines.append("  · 🚨 PERINGATAN: Formulir memuat pertanyaan sensitif/keuangan mencurigakan!")

    for s in (web.get("searches") or [])[:2]:
        lines.append(f"- Search: `{s.get('query')}` (ok={s.get('ok')})")
        for r in (s.get("results") or [])[:3]:
            lines.append(
                f"  · {(r.get('title') or '-')[:100]} — {r.get('url')}"
            )
            if r.get("snippet"):
                lines.append(f"    {r.get('snippet')[:140]}")
        for f in s.get("risk_flags") or []:
            lines.append(f"  → ⚠️ {f}")

    for f in web.get("risk_flags") or []:
        lines.append(f"- ⚠️ {f}")
    for f in web.get("safe_flags") or []:
        lines.append(f"- ✅ {f}")

    if len(lines) == 1:
        lines.append("- Tidak ada website/search yang berhasil dikumpulkan.")
    return "\n".join(lines)


def _build_threads_osint_section(threads: dict) -> str:
    """Format hasil OSINT Threads untuk prompt reasoner."""
    if not threads:
        return "- Tidak ada data Threads."
    if not threads.get("enabled"):
        return f"- Threads OSINT nonaktif: {threads.get('error') or threads.get('note') or 'cookie belum diset'}."
    if threads.get("error") and not threads.get("found"):
        return f"- Threads OSINT error: {threads.get('error')}"

    lines = [
        f"- Query: {threads.get('query', '-')}",
        f"- Ditemukan jejak: {'Ya' if threads.get('found') else 'Tidak'}",
    ]
    profiles = threads.get("profiles") or []
    if profiles:
        lines.append("- Profil terkait:")
        for p in profiles[:3]:
            lines.append(f"  · @{p.get('username')} — {p.get('url')}")
    posts = threads.get("posts") or []
    if posts:
        lines.append("- Cuplikan postingan:")
        for p in posts[:4]:
            lines.append(f"  · ({p.get('source')}) {p.get('snippet', '')[:180]}")
    flags = threads.get("risk_flags") or []
    if flags:
        lines.append("- Bendera risiko medsos:")
        for f in flags:
            lines.append(f"  · {f}")
    if not profiles and not posts:
        lines.append("- Tidak ada postingan/profil yang cocok dari pencarian terbatas.")
    return "\n".join(lines)


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

**Reputasi Nomor HP (Kredibel — scrape halaman nyata):**
{_build_phone_osint_section(osint_results.get("phones", []))}

**Cek Nama PT / Perusahaan (jejak publik, BUKAN sertifikat AHU palsu):**
{_build_company_osint_section(osint_results.get("companies", []))}

**Bukti Web (Scrapling — website + pencarian nyata):**
{_build_web_osint_section(osint_results.get("web", {}))}

**Jejak Threads saja (medsos; cookie session):**
{_build_threads_osint_section(osint_results.get("threads", {}))}

**Kebijakan evidence:**
{(osint_results.get("evidence_policy") or {}).get("note", "Hanya fakta dari sumber OSINT.")}

---

## ATURAN KERAS (ANTI-HALUSINASI & VALUASI LOWONGAN VALID)

1. Kamu HANYA boleh memakai FAKTA yang tertulis di bagian OSINT / TEKS ASLI di atas.
2. DILARANG mengarang: laporan medsos fiktif, status AHU/OSS, atau rating Kredibel yang tidak ada di data.
3. Gunakan hasil Scrapling (Instagram/Facebook/TikTok/Marketplace/Threads/SERP) yang ada di `safe_flags` / `safe_signals`.
4. VALUASI LOWONGAN VALID (UMKM/RITEL/STARTUP LOKAL):
   - Jika ALAMAT FISIK TERVERIFIKASI VALID di peta OpenStreetMap Indonesia (misal: Sleman, Yogyakarta),
   - Dan rentang GAJI RASIONAL/WAJAR (contoh: Rp 2 - 4.5 juta/bulan),
   - Dan deskripsi benefit/persyaratan kerja terperinci tanpa indikasi permintaan biaya/uang,
   - Dan terdeteksi PROFIL MEDSOS / TOKO PUBLIK AKTIF (Instagram/Tokopedia/Shopee):
   - ➔ MAKA BERIKAN VERDICT: "AMAN" dengan skor risiko 15 - 35 (skor AMAN)!
   - Catatan: Penggunaan shortlink bit.ly atau Google Forms (forms.gle) adalah praktik standar yang SANGAT UMUM untuk rekrutmen UMKM/Startups di Indonesia dan BUKAN indikator penipuan jika lokasi fisik & medsos terbukti nyata.

## INSTRUKSI ANALISIS

1. Email domain gratisan vs klaim PT formal?
2. Umur domain / SPF / DMARC (hanya dari data WHOIS/DNS di atas)?
3. Gaji tidak wajar / minta biaya (dari teks)?
4. Alamat: valid di OSM atau tidak (hanya dari validasi alamat)?
5. Website: jika web korporat tidak aktif namun akun Instagram/toko publik resmi DITEMUKAN ➔ nilai sebagai AMAN/RITEL VALID!
6. Kredibel: reported_fraud / rating (hanya jika ada di data telepon)?
7. Search/PT traces: indikasi penipuan di SERP (hanya URL yang tertera)?
8. Threads & Medsos: perhatikan hasil pencarian medsos yang tertera di safe_flags!
9. corrected_company_name dari teks asli.
10. Skala bisnis UMKM vs PT formal.
11. risk_score konsisten: AMAN 0-39, WASPADA 40-74, BAHAYA 75-100.

---

## FORMAT OUTPUT (WAJIB JSON)

Berikan output HANYA dalam format JSON berikut, tanpa teks lain di luar JSON:

{{
  "verdict": "AMAN" | "WASPADA" | "BAHAYA",
  "risk_score": <angka 0-100>,
  "corrected_company_name": "<nama lengkap bisnis dari teks asli, atau null jika tidak ada>",
  "summary": "<analisis singkat 1-2 kalimat mengapa verdict ini diberikan secara khusus untuk loker ini>",
  "risk_factors": [
    "<faktor risiko spesifik yang ditemukan pada loker ini, kosongkan [] jika tidak ada>"
  ],
  "safe_factors": [
    "<faktor aman spesifik yang ditemukan pada loker ini>"
  ],
  "recommendations": [
    "<saran tindakan spesifik untuk pelamar loker ini>"
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
