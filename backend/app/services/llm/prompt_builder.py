"""
Prompt Builder untuk Verifin AI Reasoning Engine.
Mengubah data OSINT & NER yang sudah diekstrak menjadi prompt terstruktur
yang siap dikirim ke LLM (OpenAgentic / Grok) untuk analisis risiko penipuan.
"""

# Domain gratisan yang umum digunakan — tidak perlu dicek WHOIS/SPF/DMARC
from app.services.constants import FREE_EMAIL_DOMAINS


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
            "- Domain gratisan TIDAK dapat dicek umur/SPF/DMARC (bukan domain perusahaan).\n"
            "- ℹ️ NETRAL untuk UMKM/ritel/startup lokal di Indonesia — sangat umum pakai Gmail/Yahoo.\n"
            "- Hanya naikkan risiko RINGAN jika digabung red flag lain (minta biaya, HP fraud, alamat fiktif).\n"
            "- JANGAN jadikan Gmail satu-satunya alasan skor tinggi atau WASPADA."
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
        has_error = bool(p.get("error") and not p.get("found"))
        serp = p.get("serp_fallback") or {}
        serp_risk = serp.get("risk_flags") or []
        if has_error:
            # Kredibel gagal — tampilkan status SERP fallback agar LLM tidak mengarang
            if serp_risk:
                lines.append(
                    f"- `{phone}`: Kaspersky Who Calls gagal dicek ({p.get('error')}), "
                    f"NAMUN SERP publik menemukan INDIKASI PENIPUAN:"
                )
                for rf in serp_risk:
                    lines.append(f"  → {rf}")
            else:
                lines.append(
                    f"- `{phone}`: Kaspersky Who Calls tidak dapat diakses ({p.get('error')}). "
                    f"Pencarian SERP publik tidak menemukan laporan penipuan spesifik terkait nomor ini."
                )
            continue
        parts = [f"- `{phone}` via Kaspersky Who Calls"]
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
        # Sertakan juga SERP fallback jika ada flag tambahan
        for rf in serp_risk:
            lines.append(f"  → [SERP] {rf}")
    return "\n".join(lines) if lines else "- Tidak ada data telepon."



def _build_company_osint_section(companies: list) -> str:
    if not companies:
        return "- Tidak ada pengecekan nama PT/perusahaan."
    lines = []
    for c in companies:
        name = c.get("name") or "?"
        lines.append(f"- Nama: `{name}` | method={c.get('method', 'public_web_only')}")
        reg = c.get("registry") or {}
        # registry field hanya ada kalau company_validator melakukan probe AHU — umumnya kosong
        if reg.get("pt_registry_verified") is not None:
            lines.append(
                f"  → Legalitas AHU/OSS: "
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


def _build_social_osint_section(threads: dict) -> str:
    """Format hasil OSINT Social Media untuk prompt reasoner — ringkas."""
    if not threads:
        return "- Tidak ada data media sosial."
    if not threads.get("enabled"):
        return f"- Social Media OSINT nonaktif: {threads.get('note') or 'tidak ada data'}."
    if threads.get("error") and not threads.get("found"):
        return f"- Social Media OSINT error: {threads.get('error')}"

    found = threads.get("found", False)
    platform_hits = threads.get("platform_hits") or {}
    active_platforms = [p for p, v in platform_hits.items() if v]
    risk_flags = threads.get("risk_flags") or []
    profiles = threads.get("profiles") or []
    posts = threads.get("posts") or []

    lines = [
        f"- Jejak ditemukan: {'Ya' if found else 'Tidak'}",
        f"- Platform aktif: {', '.join(active_platforms) if active_platforms else 'tidak ada'}",
        f"- Jumlah postingan ditemukan: {len(posts)}",
        f"- Jumlah profil ditemukan: {len(profiles)}",
    ]
    if risk_flags:
        for f in risk_flags:
            lines.append(f"- Risiko: {f}")
    if profiles:
        for p in profiles[:2]:
            lines.append(f"- Profil: @{p.get('username', '?')} ({p.get('url', '')})")
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
        String prompt terstruktur yang siap dikirim ke LLM.
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
Analisis secara mendalam, formal, dan berbasis evidence. Berikan keputusan apakah lowongan ini AMAN, WASPADA, atau BAHAYA.

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

**Reputasi Nomor HP (Kaspersky Who Calls — scrape halaman nyata):**
{_build_phone_osint_section(osint_results.get("phones", []))}

**Cek Nama PT / Perusahaan (jejak publik, BUKAN sertifikat AHU palsu):**
{_build_company_osint_section(osint_results.get("companies", []))}

**Bukti Web (Scrapling — website + pencarian nyata):**
{_build_web_osint_section(osint_results.get("web", {}))}

**Jejak Media Sosial (Instagram, Threads, TikTok, Facebook, X):**
{_build_social_osint_section(osint_results.get("threads", {}))}

**Kebijakan evidence:**
{(osint_results.get("evidence_policy") or {}).get("note", "Hanya fakta dari sumber OSINT.")}

---

## ATURAN KERAS (ANTI-HALUSINASI & KALIBRASI SKOR)

1. HANYA pakai FAKTA di OSINT / TEKS ASLI. Dilarang mengarang AHU/OSS, medsos, atau rating Kaspersky.
2. EMAIL GMAIL/YAHOO: Email gratisan umum di UMKM dan perusahaan kecil Indonesia — BUKAN indikator penipuan tunggal. Hanya masukkan sebagai risk_factor jika dikombinasikan dengan sinyal lain (tidak ada alamat, tidak ada website, tidak ada jejak AHU).
2. Gunakan safe_flags / risk_flags / safe_signals yang ada di data.
3. Email Gmail/Yahoo = NETRAL untuk UMKM/ritel/startup lokal di Indonesia (bukan red flag utama).
4. PENCATUTAN INSTANSI PEMERINTAH: Jika lowongan mengatasnamakan instansi/badan resmi pemerintah (misal Badan Gizi Nasional/BGN, SPPG, Kementerian, Dinas) namun menggunakan email Gmail/Yahoo tanpa domain .go.id, ini adalah indikasi tidak resmi/pencatutan.
   ➔ PANDUAN SKOR: Kategori WASPADA (skor 45–60). DILARANG meloncat ke BAHAYA (75+) HANYA karena email Gmail, KECUALI ada bukti pemerasan biaya/transfer uang/KTP/rekening.
5. Gaji tidak disebut = NETRAL (banyak loker legitimate tanpa gaji di poster).
6. Tidak ada website resmi = NETRAL jika ada medsos/toko publik ATAU alamat OSM valid.
7. shortlink bit.ly / Google Forms = praktik umum rekrutmen UMKM, BUKAN penipuan sendirian.
8. PORTAL LOKER RESMI (JobStreet, LinkedIn, Glints, KitaLulus): Ketiadaan nomor HP atau email kontak langsung di dalam teks ADALAH HAL WARJAR karena lamaran dikirim langsung via tombol portal. DILARANG menjadikan "tidak ada email/telepon" sebagai faktor risiko untuk portal loker resmi.
9. DILARANG MENGHALUSINASI BERITA UMUM KEPOLISIAN/OJK: Berita portal umum mengenai penipuan umum (misal berita 'Aparat Memburu Penipu Pendirian SPPG', 'Satgas PASTI', atau 'Deretan Hoaks Lowongan Kerja') BUKAN bukti bahwa lowongan ini adalah penipuan tersebut. HANYA klaim berita penipuan jika judul/snippet secara spesifik menyebutkan nama lengkap entitas atau nomor telepon ini.
10. KREDIBEL GAGAL DIAKSES: Jika nomor HP tercatat "Kaspersky Who Calls tidak dapat diakses" DAN "Pencarian SERP publik tidak menemukan laporan penipuan", artinya TIDAK ADA BUKTI PENIPUAN terkait nomor tersebut. DILARANG memasukkan ini sebagai risk_factor. Ini harus masuk sebagai safe_factor atau diabaikan sama sekali.

## PANDUAN SKOR (WAJIB DIIKUTI — JANGAN PARKIR DI 25-35 TANPA ALASAN)

**AMAN (0–39)** — pecah band:
- **0–10 (sangat aman):** alamat OSM valid + HP bersih Kaspersky Who Calls + tidak minta biaya +
  (medsos/toko aktif ATAU website hidup) + tidak ada indikasi scam di SERP.
  Gmail diperbolehkan di band ini untuk UMKM.
- **11–22 (aman):** mayoritas sinyal aman; sisa keraguan ringan (gaji kosong, jejak web tipis).
- **23–39 (aman dengan catatan):** masih AMAN tapi ada 1–2 kelemahan non-kritis.

**WASPADA (40–74):**
- kombinasi red flag nyata: alamat gagal OSM + zero footprint, atau klaim instansi pemerintah (BGN/SPPG/Kementerian) + Gmail (skor 45-60),
  atau sinyal scam lemah di SERP tanpa konfirmasi kuat.

**BAHAYA (75–100):**
- WAJIB ada bukti keras: permintaan biaya/transfer/KTP/rekening, ATAU HP reported_fraud Kaspersky Who Calls,
  ATAU phishing form, ATAU laporan penipuan spesifik yang terbukti menargetkan nomor/perusahaan ini.

## VALUASI UMKM VALID (PRIORITAS)
Jika SEMUA ini terpenuhi:
- alamat fisik terverifikasi OSM, DAN
- HP tidak reported_fraud di Kaspersky Who Calls, DAN
- tidak ada permintaan biaya/uang di teks, DAN
- (medsos/toko publik aktif ATAU deskripsi syarat kerja wajar terperinci):
➔ verdict **AMAN**, risk_score **5–15** (boleh under 10).
Jangan naikkan ke 25+ hanya karena Gmail / tanpa website / gaji kosong.

Jika TIDAK ADA alamat OSM tapi SEMUA ini terpenuhi:
- tidak ada nama PT/CV formal (hanya UMKM/perorangan/hiring pribadi), DAN
- HP tidak reported_fraud di Kaspersky Who Calls, DAN
- tidak ada permintaan biaya/uang di teks, DAN
- deskripsi pekerjaan wajar dan terperinci (jobdesk, syarat, sistem kerja jelas):
➔ verdict **AMAN**, risk_score **20–35** (aman dengan catatan — zero footprint UMKM normal).
Jangan naikkan ke WASPADA hanya karena tidak ada alamat/PT/website — itu normal untuk UMKM kecil.

## INSTRUKSI ANALISIS
1. Red flag keras dulu: biaya, fraud HP, phishing form, scam SERP.
2. Alamat OSM valid?
3. Medsos/toko/web evidence?
4. Gmail hanya faktor ringan jika digabung red flag lain.
5. corrected_company_name dari teks asli.
6. risk_score HARUS selaras verdict dan band di atas.

---

## FORMAT OUTPUT (WAJIB JSON saja)

{{
  "verdict": "AMAN" | "WASPADA" | "BAHAYA",
  "risk_score": <angka 0-100>,
  "corrected_company_name": "<nama lengkap bisnis dari teks asli, atau null jika tidak ada>",
  "summary": "<1-2 kalimat alasan verdict>",
  "risk_factors": ["<faktor risiko nyata; [] jika tidak ada>"],
  "safe_factors": ["<faktor aman>"],
  "recommendations": ["<saran untuk pelamar>"]
}}

Skor vs verdict:
- AMAN: 0-39 (UMKM valid target 5-15)
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

    # Kurangi batas raw_text agar prompt tidak terlalu panjang
    # Prompt besar = response terpotong = JSON error
    MAX_RAW = 600
    raw_section = f"""
## TEKS ASLI LOWONGAN (Hasil OCR / Input Manual)

```
{raw_text[:MAX_RAW]}{"...(terpotong)" if len(raw_text) > MAX_RAW else ""}
```

"""
    return base_prompt.replace("## DATA LOWONGAN KERJA", raw_section + "## DATA LOWONGAN KERJA")
