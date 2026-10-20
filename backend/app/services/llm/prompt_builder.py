import re

from app.services.constants import FREE_EMAIL_DOMAINS


def _build_domain_osint_section(emails: list, domain_info: dict, email_security: dict) -> str:
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
        return "- Nomor HP tidak tercantum pada input; pemeriksaan Kaspersky dilewati. Ini bukan bukti nomor bersih atau bukti penipuan."
    lines = []
    for p in phones:
        phone = p.get("phone") or p.get("phone_local") or "?"
        has_error = p.get("probe_status") == "UNAVAILABLE" or bool(
            p.get("error") and not p.get("checked")
        )
        serp = p.get("serp_fallback") or {}
        serp_risk = serp.get("risk_flags") or []
        if has_error:
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
        parts = [
            f"- `{phone}` via Kaspersky Who Calls",
            f"status pemeriksaan: {p.get('probe_status', 'UNKNOWN')}",
            f"status reputasi: {p.get('reputation_status', 'UNKNOWN')}",
        ]
        if p.get("rating") is not None:
            parts.append(f"rating {p.get('rating')}")
        if p.get("review_count") is not None:
            parts.append(f"{p.get('review_count')} review")
        if p.get("reported_fraud"):
            parts.append("⚠️ PERNAH DILAPORKAN PENIPUAN")
        elif p.get("reputation_status") == "CLEAN":
            parts.append("✅ tidak ada laporan fraud/spam yang ditemukan")
        if p.get("url"):
            parts.append(f"sumber: {p.get('url')}")
        lines.append(" | ".join(parts))
        for f in p.get("risk_flags") or []:
            lines.append(f"  → {f}")
        for n in p.get("neutral_notes") or []:
            lines.append(f"  → [info] {n}")
        if p.get("summary"):
            lines.append(f"  → ringkas: {p.get('summary')}")
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
        if stats.get("search_count") is not None:
            lines.append(
                f"  → Detail search tersedia di bagian Web Evidence; "
                f"{stats.get('search_count', 0)} query dipakai tanpa menyalin payload."
            )
        for f in c.get("risk_flags") or []:
            lines.append(f"  → ⚠️ {f}")
        for f in c.get("safe_flags") or []:
            lines.append(f"  → ✅ {f}")
        for note in c.get("neutral_notes") or []:
            lines.append(f"  → ℹ️ {note}")
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
        if w.get("website_status") == "AVAILABLE":
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
            elif gf.get("content_verification_status") == "UNVERIFIED":
                lines.append(
                    "  · ⚠️ Isi pertanyaan belum berhasil dibaca; jangan menyimpulkan form bebas phishing."
                )
            elif gf.get("has_phishing_signals") is False:
                lines.append("  · Tidak ditemukan kata kunci phishing pada isi form yang berhasil dibaca; ini bukan bukti perusahaan/lowongan resmi.")

    for s in (web.get("searches") or [])[:2]:
        lines.append(f"- Search: `{s.get('query')}` (status={s.get('status', 'UNKNOWN')}, engine={s.get('engine', 'unknown')})")
        for r in (s.get("results") or [])[:3]:
            url = r.get("url") or ""
            if any(domain in url.lower() for domain in ("tokopedia.com", "shopee.co.id")):
                source_note = "public marketplace listing; bukan bukti akun resmi perusahaan"
            elif any(domain in url.lower() for domain in ("lokerjogja", "jobstreet", "glints", "kalibrr", "linkedin.com/jobs")):
                source_note = "public job portal listing; bukan kanal resmi perusahaan"
            elif any(domain in url.lower() for domain in ("instagram.com", "facebook.com", "tiktok.com", "threads.net")):
                source_note = "public social result; status resmi tidak terverifikasi"
            else:
                source_note = "public web result; status resmi tidak terverifikasi"
            lines.append(
                f"  · {(r.get('title') or '-')[:100]} — {url} ({source_note})"
            )
            if r.get("snippet"):
                lines.append(f"    {r.get('snippet')[:140]}")
        for f in s.get("risk_flags") or []:
            lines.append(f"  → ⚠️ {f}")

    for f in web.get("risk_flags") or []:
        lines.append(f"- ⚠️ {f}")
    for f in web.get("safe_flags") or []:
        lines.append(f"- ✅ {f}")

    counts = web.get("evidence_counts") or {}
    if counts:
        lines.append(
            "- COUNTS DETERMINISTIK: "
            f"{counts.get('relevant_results', 0)} hasil relevan; "
            f"sumber={counts.get('by_source_type', {})}; "
            f"REQUESTS_OK={counts.get('successful_requests', 0)}; "
            f"NO_RESULTS={counts.get('empty_searches', 0)}; "
            f"NO_RELEVANT_RESULTS={counts.get('no_relevant_searches', 0)}; "
            f"UNAVAILABLE={counts.get('unavailable_searches', 0)}."
        )
        footprint = counts.get("digital_footprint", "unknown")
        if footprint != "unknown":
            footprint_label = {
                "strong": "KUAT (banyak jejak terverifikasi)",
                "moderate": "SEDANG (ada beberapa jejak)",
                "weak": "MINIM (jejak sangat tipis)",
                "none": "TIDAK ADA (tidak ditemukan jejak apapun)",
            }.get(footprint, footprint)
            lines.append(f"- DIGITAL FOOTPRINT (Search Intelligence): {footprint_label}")
            presences = []
            if counts.get("official_presence"):
                presences.append("website/halaman resmi")
            if counts.get("marketplace_presence"):
                presences.append("marketplace")
            if counts.get("social_presence"):
                presences.append("media sosial")
            if counts.get("maps_presence"):
                presences.append("Google Maps")
            if presences:
                lines.append(f"  → Kehadiran terdeteksi di: {', '.join(presences)}")
        lines.append(
            "- `NO_RESULTS`/`NO_RELEVANT_RESULTS` bukan bukti tidak ada penipuan; hasil harus relevan dan spesifik untuk menjadi evidence."
        )

    if len(lines) == 1:
        lines.append("- Tidak ada website/search yang berhasil dikumpulkan.")
    return "\n".join(lines)


def _build_scam_check_section(web: dict) -> str:
    check = (web or {}).get("scam_check") or {}
    status = check.get("status")
    if status in (None, "SKIPPED"):
        return "- Tidak dijalankan (tidak ada nama perusahaan)."
    if status == "UNAVAILABLE":
        return f"- Pencarian tidak tersedia pada run ini ({check.get('error') or 'gagal'}). Jangan dianggap aman maupun berbahaya."
    results = check.get("results") or []
    if not results:
        return f"- Query `{check.get('query')}`: tidak ada artikel peringatan/bantahan yang menyebut nama ini."
    lines = [
        f"- Query `{check.get('query')}`: {len(results)} artikel peringatan/bantahan lowongan palsu atas nama ini:",
    ]
    for r in results[:4]:
        lines.append(f"  • {r.get('title', '')} — {r.get('snippet', '')[:160]}")
    lines.append(
        "  → Artinya nama ini PERNAH dicatut. Bukan bukti lowongan ini palsu, kecuali isi/nomor/modusnya cocok "
        "dengan artikel; tetapi bila lowongan ini juga memakai kanal tidak resmi, ini memperkuat WASPADA/BAHAYA."
    )
    return "\n".join(lines)


def _build_social_osint_section(social: dict) -> str:
    if not social:
        return "- Tidak ada data media sosial."
    if not social.get("enabled"):
        return f"- Social Media OSINT nonaktif: {social.get('note') or 'tidak ada data'}."
    if social.get("error") and not social.get("found"):
        return f"- Social Media OSINT error: {social.get('error')}"

    found = social.get("social_found", social.get("found", False))
    public_footprint_found = social.get("public_footprint_found", found)
    platform_hits = social.get("official_platform_hits") or social.get("platform_hits") or {}
    active_platforms = [p for p, v in platform_hits.items() if v]
    risk_flags = social.get("risk_flags") or []
    profiles = social.get("profiles") or []
    posts = social.get("posts") or []

    lines = [
        f"- Jejak ditemukan: {'Ya' if found else 'Tidak'}",
        f"- Footprint publik media sosial: {'Ya' if public_footprint_found else 'Tidak'}",
        f"- Platform aktif: {', '.join(active_platforms) if active_platforms else 'tidak ada'}",
        f"- Jumlah postingan ditemukan: {len(posts)}",
        f"- Jumlah profil ditemukan: {len(profiles)}",
    ]
    if risk_flags:
        for f in risk_flags:
            lines.append(f"- Risiko: {f}")
    counts = social.get("evidence_counts") or {}
    if counts:
        lines.append(
            "- COUNTS DETERMINISTIK SOCIAL: "
            f"{counts.get('public_posts', 0)} posting publik, "
            f"{counts.get('public_profiles', 0)} profil publik, "
            f"{counts.get('official_posts', 0)} posting berstatus official."
        )
    if profiles:
        for p in profiles[:2]:
            lines.append(f"- Profil: @{p.get('username', '?')} ({p.get('url', '')})")
    if social.get("found_by_name_only"):
        lines.append(
            "- CATATAN: profil di atas ditemukan lewat pencarian nama, TIDAK ditautkan oleh lowongan. "
            "Ini akun pemilik nama tersebut, bukan bukti bahwa lowongan ini berasal darinya; "
            "jangan dijadikan safe_factor."
        )
    return "\n".join(lines)


def _build_address_osint_section(address_validations: list) -> str:
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

        details = av.get("address_details", {}) or {}
        match_level = details.get("match_level", "area")

        if not found:
            lines.append(f"- `{addr}`: ❌ TIDAK DITEMUKAN di peta Indonesia.")
        else:
            display = details.get("display_name", "")[:120]
            if match_level == "exact":
                lines.append(f"- `{addr}`: ✅ match_level=exact — jalan DAN nomor cocok ({display}).")
            elif match_level == "business":
                lines.append(
                    f"- `{addr}`: ℹ️ match_level=business — peta menemukan tempat bernama "
                    f"'{details.get('matched_name')}' di wilayah ini ({display}). Ini hanya bukti tempat itu ada; "
                    "nama perusahaan besar sering dicatut beserta alamat kantor aslinya."
                )
            elif match_level == "street":
                lines.append(
                    f"- `{addr}`: ℹ️ match_level=street — nama jalan cocok, nomor bangunan BELUM cocok ({display})."
                )
            else:
                lines.append(
                    f"- `{addr}`: ⚠️ match_level=area, street_match=false — hanya wilayah/kode pos yang cocok "
                    f"({display}). Nama jalan BELUM terkonfirmasi; DILARANG menulis jalan/alamat terkonfirmasi."
                )

        neutral_notes = av.get("neutral_notes", [])
        for note in neutral_notes:
            lines.append(f"  → ℹ️ {note}")

        if biz_found is True and biz_details.get("source") == "google_maps_serp":
            matched = biz_details.get("matched_name", "?")
            business_level = biz_details.get("match_level", "business_location")
            lines.append(
                f"  → ✅ Titik bisnis ditemukan dari hasil Google Maps publik: '{matched}' "
                f"(status lokasi: {business_level}; bukan konfirmasi alamat exact OSM)."
            )
        elif biz_found is True and match_level == "exact":
            matched = biz_details.get("matched_name", "?")
            sim = biz_details.get("similarity", 0) * 100
            lines.append(f"  → ✅ Nama perusahaan ditemukan di OSM dekat lokasi: '{matched}' (kemiripan {sim:.0f}%).")
        elif biz_found is False and not neutral_notes:
            lines.append("  → ⚠️ Nama bisnis tidak ditemukan di peta sekitar koordinat.")
        elif biz_found is None:
            lines.append("  → ℹ️ Tidak ada nama perusahaan untuk dicocokkan di peta.")

    return "\n".join(lines) if lines else "- Validasi alamat tidak tersedia."


def _build_text_signal_section(signals: dict | None) -> str:
    """Sinyal teks deterministik dari classifier, supaya LLM tidak menebak ulang hal yang bisa dihitung."""
    if not signals:
        return ""

    def yn(key: str) -> str:
        return "YA" if signals.get(key) else "tidak"

    return f"""
## SINYAL TEKS (deterministik, dihitung sistem dari teks lowongan)
- Meminta biaya/transfer: {yn("has_fee_request")}
- Menyebut kerja di luar negeri / negara rawan TPPO: {yn("has_foreign_work")}
- Satu-satunya jalur melamar adalah WhatsApp pribadi atau tautan di bio (tanpa email/portal resmi): {yn("has_whatsapp_apply")}
- Menyebut nama badan usaha yang bisa diperiksa: {yn("has_company")}
- Mengaku pabrik/perusahaan/kantor tetapi tidak menyebut namanya: {yn("anonymous_employer_claim")}
- Menawarkan gaji tanpa nama badan usaha: {yn("salary_no_company")}
- Mengatasnamakan BUMN/Persero/Tbk tetapi pendaftaran hanya lewat WhatsApp/tautan di bio: {yn("brand_unofficial_channel")}
"""


def build_verify_prompt(entities: dict, osint_results: dict, text_signals: dict | None = None) -> str:
    companies = entities.get("companies", [])
    contacts = entities.get("contacts") or entities.get("phones") or []
    emails = entities.get("emails", [])
    urls = entities.get("urls", [])
    addresses = entities.get("addresses", [])
    salaries = entities.get("salaries", [])

    domain_info = osint_results.get("domain", {})
    email_security = osint_results.get("email_security", {})

    company_str = ", ".join(companies) if companies else "Tidak disebutkan"
    contact_str = ", ".join(contacts) if contacts else "Tidak disebutkan"
    email_str = ", ".join(emails) if emails else "Tidak ada email yang terdeteksi"
    url_str = ", ".join(urls) if urls else "Tidak ada"
    address_str = "\n  - ".join(addresses) if addresses else "Tidak disebutkan"
    salary_str = ", ".join(salaries) if salaries else "Tidak disebutkan"
    fee_requests = entities.get("fee_requests") or []
    fee_str = ", ".join(fee_requests) if fee_requests else "Tidak ada indikasi permintaan biaya pada format nominal"
    address_input_note = (
        "Alamat fisik tidak tercantum pada input; jangan menyebut alamat gagal, fiktif, atau belum tervalidasi."
        if not addresses
        else "Alamat fisik tercantum pada input; bedakan alamat exact, street, dan area dari hasil OSM."
    )

    prompt = f"""Kamu adalah Verifin, sistem yang menilai risiko penipuan lowongan kerja di Indonesia.
Kamu menerima data hasil ekstraksi lowongan dan hasil pemeriksaan sumber publik (OSINT).
Putuskan AMAN, WASPADA, atau BAHAYA hanya dari bukti di bawah.

## DATA LOWONGAN KERJA

**Nama Perusahaan:** {company_str}
**Nomor HP / Kontak:** {contact_str}
**Alamat Email:** {email_str}
**Website / URL:** {url_str}
**Alamat Fisik:**
  - {address_str}
  - STATUS INPUT: {address_input_note}
**Gaji yang Ditawarkan:** {salary_str}
**Indikasi Permintaan Biaya / Transfer:** {fee_str}
{_build_text_signal_section(text_signals)}
## BUKTI OSINT

**Domain email:**
{_build_domain_osint_section(emails, domain_info, email_security)}

**Alamat di peta (OpenStreetMap):**
{_build_address_osint_section(osint_results.get("address_validations", []))}

**Reputasi nomor HP (Kaspersky Who Calls):**
{_build_phone_osint_section(osint_results.get("phones", []))}

**Jejak publik nama perusahaan (bukan cek legalitas AHU):**
{_build_company_osint_section(osint_results.get("companies", []))}

**Bukti web (situs + pencarian):**
{_build_web_osint_section(osint_results.get("web", {}))}

**Peringatan/bantahan lowongan palsu atas nama ini:**
{_build_scam_check_section(osint_results.get("web", {}))}

**Media sosial:**
{_build_social_osint_section(osint_results.get("social", {}))}

## ATURAN BUKTI

1. Pakai hanya fakta dari bagian DATA, BUKTI OSINT, dan teks asli. Dilarang mengarang status AHU/OSS, akun medsos, atau hasil Kaspersky.
2. Pemeriksaan yang berstatus `UNAVAILABLE`, `TIMEOUT`, atau gagal diakses berarti "tidak ada data", bukan sinyal aman dan bukan sinyal bahaya. Jangan masukkan ke safe_factors maupun risk_factors.
3. Email Gmail/Yahoo netral untuk UMKM, ritel, dan perusahaan kecil. Hanya jadi faktor risiko bila digabung sinyal lain (tanpa alamat, tanpa jejak publik, atau mengaku instansi besar).
4. Pencatutan instansi pemerintah (BGN, SPPG, kementerian, dinas) dengan email Gmail/Yahoo tanpa domain .go.id: WASPADA 45–60. Naik ke BAHAYA hanya bila ada permintaan biaya, transfer, KTP, atau rekening.
5. Gaji tidak disebut, tidak ada website, atau tautan bit.ly/Google Forms bukan bukti penipuan sendirian.
6. Google Forms: bila `has_phishing_signals` = null atau `content_verification_status` = "UNVERIFIED", isinya belum terbaca; jangan jadikan risk_factor. Hanya jadi risk_factor bila `has_phishing_signals` = true dengan bukti eksplisit.
7. Portal lowongan publik (JobStreet, LinkedIn, Glints, KitaLulus): tidak adanya nomor/email di teks itu wajar.
8. Berita penipuan umum (razia, Satgas PASTI, "deretan hoaks loker") bukan bukti lowongan ini palsu. Klaim penipuan spesifik hanya bila judul/snippet menyebut nama lengkap entitas atau nomor ini.
9. Status nomor: `probe_status=COMPLETED` berarti pemeriksaan berhasil; `reputation_status=CLEAN` dan `reported_fraud=false` berarti tidak ada laporan. `found=false` hanya berarti tidak ada bukti scam, bukan pemeriksaan gagal.
10. Alamat: hanya `match_level=exact` yang boleh disebut alamat terverifikasi. `business` = tempat bernama sama ada di peta. `street` = jalan cocok, nomor belum. `area` = hanya wilayah/kode pos; dilarang menyebut jalan terkonfirmasi.
11. Kecocokan alamat atau jejak web perusahaan besar tidak membuktikan lowongan atas namanya asli, karena penipu memakai nama dan alamat kantor asli.
12. Marketplace, portal lowongan, hasil pencarian, dan akun medsos yang ditemukan lewat pencarian nama bukan kanal resmi lowongan. Sebut "resmi" hanya bila bukti menunjukkan hubungan resmi (mis. domain email sama dengan situs).
13. Jika semua pencarian web berstatus `NO_RESULTS`/`UNAVAILABLE`, tulis "bukti publik tidak tersedia pada run ini", bukan "zero footprint". Jika `relevant_results > 0`, dilarang menulis keduanya.
14. Jangan mengganti nama perusahaan hasil ekstraksi; `corrected_company_name` = null kecuali teks asli mengoreksinya.

## BAND SKOR

**AMAN (0–39)**
- 0–10: alamat `exact` atau `business`, HP bersih, tanpa permintaan biaya, ada situs/medsos/jejak publik, tanpa laporan scam spesifik.
- 11–22: mayoritas sinyal aman, sisa keraguan ringan (gaji kosong, jejak web tipis, nomor bangunan belum pasti).
- 23–39: aman dengan 1–2 kelemahan non-kritis. UMKM tanpa PT/alamat/website tetapi deskripsi kerja wajar dan rinci, HP bersih, tanpa biaya: 20–35.

**WASPADA (40–74)**
- Kombinasi sinyal nyata tanpa bukti keras: alamat tidak ditemukan + jejak publik benar-benar nihil, instansi pemerintah + Gmail (45–60), atau sinyal scam lemah.
- SINYAL TEKS "Mengaku perusahaan tetapi tidak menyebut namanya" = YA DAN "jalur melamar hanya WhatsApp/tautan bio" = YA: 45–60.
- SINYAL TEKS "Mengatasnamakan BUMN/Persero/Tbk tetapi pendaftaran hanya lewat WhatsApp/tautan bio" = YA: minimal 60–74. Ada artikel peringatan/bantahan atas nama itu: mendekati 74.
- Ada artikel peringatan/bantahan lowongan palsu atas nama perusahaan ini DAN jalur melamar hanya WhatsApp/tautan bio (SINYAL TEKS): minimal 60–74, walau nama tidak memakai akhiran Persero/Tbk.

**BAHAYA (75–100)**
- Wajib ada bukti keras: permintaan biaya/transfer/KTP/rekening (termasuk tiket atau akomodasi dengan janji reimburse), HP `reported_fraud`, form phishing, atau laporan penipuan spesifik yang menyebut nomor/perusahaan/modus lowongan ini.

## URUTAN PENALARAN

1. Cek bukti keras dulu (biaya, nomor dilaporkan, phishing, laporan spesifik).
2. Cek sinyal pencatutan (BUMN/instansi + kanal tidak resmi, artikel peringatan).
3. Nilai alamat sesuai `match_level`, lalu jejak web dan medsos.
4. Pilih band, lalu skor yang selaras dengan band.

## FORMAT JAWABAN

`summary` menjelaskan bukti, bukan status hukum. Dilarang menyebut lowongan/perusahaan "resmi", "terverifikasi", "valid", "legal", "sah", "terpercaya", "kredibel", atau "pasti aman". Contoh: "Domain email perusahaan sudah lama terdaftar dan jejak digitalnya konsisten; tidak ditemukan tanda bahaya."

Batas: `summary` 1 kalimat (maks 25 kata); `risk_factors`, `safe_factors`, `recommendations` masing-masing maks 3 butir, maks 8 kata per butir, rekomendasi berupa kalimat perintah pendek.

{{
  "verdict": "AMAN" | "WASPADA" | "BAHAYA",
  "risk_score": <angka 0-100>,
  "corrected_company_name": null,
  "summary": "<1 kalimat>",
  "risk_factors": ["<maks 8 kata>"],
  "safe_factors": ["<maks 8 kata>"],
  "recommendations": ["<maks 8 kata>"]
}}
"""
    return prompt.strip()


def build_text_verify_prompt(
    raw_text: str, entities: dict, osint_results: dict, text_signals: dict | None = None
) -> str:
    base_prompt = build_verify_prompt(entities, osint_results, text_signals)

    MAX_RAW = 2500
    raw_section = f"""
## TEKS LENGKAP LOWONGAN KERJA (Input Langsung / OCR):
```text
{raw_text[:MAX_RAW]}{"...(terpotong)" if len(raw_text) > MAX_RAW else ""}
```
---
"""
    if "## DATA LOWONGAN KERJA" in base_prompt:
        return base_prompt.replace("## DATA LOWONGAN KERJA", raw_section + "\n## DATA LOWONGAN KERJA")
    if "**Nama Perusahaan:**" in base_prompt:
        return base_prompt.replace("**Nama Perusahaan:**", raw_section + "\n**Nama Perusahaan:**")
    return raw_section + "\n" + base_prompt
