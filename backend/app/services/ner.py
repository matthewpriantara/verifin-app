"""
Ekstraksi entitas dari teks lowongan — full regex struktural.

Desain:
- Tanpa model ML (IndoBERT dihapus: lambat, sering tidak akurat di poster OCR).
- Alamat berbasis POLA Indonesia (Jl/Dusun/RT-RW/Kel/Kec/Kab + kode pos),
  bukan whitelist kota — layout poster sangat beragam.
- Company berbasis legal form + label + narasi brand.
"""

from __future__ import annotations

import re

from app.services.constants import FREE_EMAIL_DOMAINS
from app.services.hasher import compute_content_sha256

# Pemisah konten non-alamat (label seksi lowongan)
_ADDR_STOP = (
    r"(?:\bGaji\b|\bSalary\b|\bUpah\b|\bKontak\b|\bContact\b|\bEmail\b|\bWA\b|\bWhatsApp\b|\bHubungi\b|"
    r"\bKirim\b|\bCV\b|\bCover\s*Letter\b|\bSend(?:\s*your)?\b|\bSubjek\b|\bSubject\b|\bApply\b|\bApply\s*Now\b|\bMore\s*Information\b|"
    r"\bLamaran\b|\bBenefit\b|\bSyarat\b|\bKualifikasi\b|\bPosisi\b|\bLowongan\b|"
    r"\bInfo\b|\bInformasi\b|\bNB\b|\bCatatan\b|\bNote\b|\bTransfer\b|\bBiaya\b|\bDeposit\b|\bDeskripsi\b|"
    r"\bPekerjaan\b|\bRingkasan\b|\bFormulir\b|\bAccount\b|\bOfficer\b|\bLamar\b)"
)


# Prefix yang boleh MEMULAI alamat (bukan admin murni seperti "Kota X")
_STREET_PREFIX = (
    r"(?:Jl\.?|Jln\.?|Jalan|Gg\.?|Gang|Dusun|Ds\.?|Desa|"
    r"Komp\.?|Komplek|Kompleks|Perum\.?|Perumahan|Blok|Cluster|"
    r"Ruko|Rukan|Gedung|Tower|Lt\.?|Lantai|Kampus|Kantor)"
)


# Daftar kota/kabupaten besar Indonesia sebagai fallback deteksi alamat
# tanpa prefix jalan — bukan whitelist eksklusif, hanya confidence booster.
_INDONESIAN_CITIES = (
    "Ambon|Balikpapan|Banda Aceh|Bandar Lampung|Bandung|Banjar|Banjarbaru|"
    "Banjarmasin|Batam|Batu|Bau-Bau|Bekasi|Bengkulu|Binjai|Bogor|Bontang|"
    "Bukittinggi|Cilegon|Cimahi|Cirebon|Denpasar|Depok|Dumai|Gorontalo|"
    "Jakarta|Jambi|Jayapura|Kediri|Kendari|Kotamobagu|Kupang|Langsa|"
    "Lhokseumawe|Lubuklinggau|Madiun|Magelang|Makassar|Malang|Manado|"
    "Mataram|Medan|Metro|Mojokerto|Padang|Padangsidimpuan|Pagar Alam|"
    "Palangka Raya|Palembang|Palopo|Palu|Pangkalpinang|Parepare|Pariaman|"
    "Pasuruan|Payakumbuh|Pekalongan|Pekanbaru|Pematangsiantar|Pontianak|"
    "Prabumulih|Probolinggo|Purwokerto|Sabang|Salatiga|Samarinda|Semarang|"
    "Serang|Sibolga|Singkawang|Sofifi|Solok|Sorong|Subulussalam|Sukabumi|"
    "Sungai Penuh|Surabaya|Surakarta|Solo|Tangerang|Tanjungbalai|"
    "Tanjungpinang|Tarakan|Tasikmalaya|Tebing Tinggi|Tegal|Ternate|"
    "Tidore Kepulauan|Tomohon|Tual|Yogyakarta|"
    # Kabupaten & wilayah DIY / Jateng / Jabar / Jatim yang sering muncul
    "Sleman|Bantul|Gunungkidul|Kulon Progo|Klaten|Boyolali|Sragen|"
    "Wonogiri|Karanganyar|Magelang|Purworejo|Kebumen|Temanggung|"
    "Wonosobo|Banjarnegara|Purbalingga|Cilacap|Banyumas|"
    "Pakem|Sewon|Imogiri|Ngaglik|Ngemplak|Turi|Tempel|Seyegan|Minggir|Moyudan|"
    "Godean|Seturan|Mlati|Depok|Kalasan|Prambanan|Berbah|Gamping|Piyungan|Kasihan|Sedayu|"
    "Kotagede|Umbulharjo|Gondokusuman|Wirobrajan|Banguntapan|"
    "Cikarang|Karawang|Purwakarta|Subang|Indramayu|Majalengka|"
    "Kuningan|Sumedang|Garut|Cianjur|Sukabumi|Tasikmalaya|"
    "Gresik|Sidoarjo|Lamongan|Tuban|Bojonegoro|Jombang|"
    "Kediri|Blitar|Tulungagung|Trenggalek|Ponorogo|Pacitan"
)


# Marker admin / RT-RW / kode pos — sinyal kuat baris alamat
_ADMIN_MARKER = (
    r"(?:RT\.?\s*\d+|RW\.?\s*\d+|RTRW|"
    r"Kel\.?|Kelurahan|Kec\.?|Kecamatan|Kab\.?|Kabupaten|"
    r"Kota|Prov\.?|Provinsi|Kode\s*Pos|Kodepos|\b\d{5}\b)"
)

_COMPANY_LEGAL = r"(?:PT|CV|UD|PD|Perum|Persero|Tbk|Firma|Fa|Yayasan|Koperasi|Kop\.?|BUMDes|BUMD|BUMN)"
_COMPANY_STOP = (
    r"Jl\.?|Jln\.?|Jalan|Gg\.?|Gang|Dusun|Desa|Kel\.?|Kec\.?|Kab\.?|"
    r"RT\b|RW\b|Alamat|Lokasi|Email|WA|WhatsApp|Hubungi|Gaji|Syarat|"
    r"Kontak|Telp|Phone|HP|No\.?\s*HP|Lamar|Info|Membuka|Lowongan"
)


_SOCIAL_UI_NOISE_PATTERNS = [
    r"lihat\s+apa\s+yang\s+sedang\s+dibicarakan",
    r"bergabunglah\s+dengan\s+percakapan",
    r"laporkan\s+masalah",
    r"full\s+time,?\s+terlibat\s+langsung",
    r"project\s+nyata",
    r"pengunggahan\s+kontak",
    r"nonpengguna\s+meta",
    r"jangan\s+pernah\s+lewatkan\s+postingan",
    r"daftar\s+instagram",
    r"lihat\s+postingan\s+lainnya",
    r"share\s*&\s*save",
    r"cek\s+story",
    r"info\s+lowongan\s+kerja\s+solo",
    r"waspada.*riset\s*&\s*cek",
    r"jangan\s+mau\s+transfer",
]


def normalize_phone_typos(text: str) -> str:
    def repl(match):
        s = match.group(0)
        s = s.replace("O", "0").replace("o", "0")
        s = s.replace("I", "1").replace("l", "1").replace("|", "1")
        s = s.replace("S", "5").replace("s", "5")
        return s

    return re.sub(r"\b\d(?:[\s\-]*[0-9OoIl|Ss]){6,14}\b", repl, text)


def _clean_address(addr: str) -> str:
    a = re.sub(r"\s+", " ", (addr or "").strip())

    # 1. OCR Typos & Normalizations
    a = re.sub(r"\bJI\.", "Jl.", a)
    a = re.sub(r"\bJI(?=[A-Za-z])", "Jl. ", a)
    a = re.sub(r"\bJalan(?=[A-Z])", "Jalan ", a)
    a = re.sub(r"\bJl\.(?=[A-Z])", "Jl. ", a)
    a = re.sub(r"\blstimewa\b", "Istimewa", a, flags=re.I)

    # 2. Buang tag header scraper / OCR / bracket noise
    a = re.sub(r"URL\s+Target\s*:\s*\S+", "", a, flags=re.I)
    a = re.sub(r"\[TEKS\s+.*?(?:\]|$)", "", a, flags=re.I)
    a = re.sub(r"\[.*?\]:?", "", a)

    # 3. Buang label alamat di depan
    a = re.sub(
        r"^(?:Alamat(?:\s*(?:Kantor|Lengkap|Perusahaan|Toko))?|Lokasi(?:\s*Kerja)?|"
        r"Penempatan(?:\s*(?:Kerja|Kantor))?|Bertempat\s*di|Tempat(?:\s*Kerja)?|Office|Basecamp|Kode\s*Pos)\s*[:.\-]?\s*",
        "",
        a,
        flags=re.I,
    )
    a = re.sub(r"^(?:di|di\s+area)\s+", "", a, flags=re.I)

    # 4. Jika ada Strong Street Prefix (Jl/Jalan/Komp/Perum/Ruko/Gedung/Tower), buang teks sampah sebelumnya
    _STRONG_STREET_PREFIX = r"(?:Jl\.?|Jln\.?|Jalan|Komp\.?|Komplek|Kompleks|Perum\.?|Perumahan|Ruko|Rukan|Gedung|Tower|Kampus|Kantor)"
    m_strong = re.search(rf"\b({_STRONG_STREET_PREFIX})\b", a, re.I)
    if m_strong and m_strong.start() > 0:
        a = a[m_strong.start():]
    else:
        # Untuk weak prefix, buang header nama tempat/brand di depan
        a = re.sub(r"^[A-Z0-9\s&'.!?-]{3,60},\s*(?=(?:Gg|Dusun|Ds|Lt|Lantai|Outlet|Toko)\b)", "", a, flags=re.I)
        # Buang frasa kualifikasi di depan
        a = re.sub(
            r"^(?:.*?\b(?:kuliah|server|steward|kualifikasi|syarat|pria|wanita|berpengalaman|shift|weekend|bekerjasama|jujur|disiplin|cekatan|komunikatif|posisi|penempatan|pendidikan|sma|smk|d3|s1|usia|maks|thn|tahun)\b.*?)+?(?=(?:Gg|Dusun|Ds|Lt|Lantai)\b)",
            "",
            a,
            flags=re.I,
        )

    # 5. Buang suffix kontak/email/gaji/company stop words
    a = re.split(rf"\s*[.,;]?\s*{_ADDR_STOP}", a, maxsplit=1, flags=re.I)[0]
    a = re.sub(r"\s+(?:Phone|Telp|Tel\.?|HP|WA|WhatsApp)\s*[:.]?\s*[\d+\-\s]+$", "", a, flags=re.I)
    a = re.sub(r"^(?:\+?62|0)\d[\d\s\-]{7,16}[,\s]*", "", a)
    a = re.sub(r"\s+(?:Gaji|Salary|Upah|Send|Subjek|Subject|CV|Apply|More)\s*[:.]?\s*.*$", "", a, flags=re.I)

    # 6. Buang kata posisi pekerjaan penyela di tengah alamat (misal "Steward", "Server", "Staff", "Admin")
    a = re.sub(
        r",?\s*\b(?:Server|Steward|Waitress?|Kasir|Barista|Cook|Kitchen|Helper|Staff|Admin)\b\s*,?",
        ", ",
        a,
        flags=re.I,
    )

    # 7. Buang trailing company legal name (misal ', PT.ASABA' di akhir)
    a = re.sub(
        rf",?\s*\b(?:{_COMPANY_LEGAL})\.?\s*[A-Za-z0-9\s&'.]+$",
        "",
        a,
        flags=re.I,
    )

    # 8. Clean up whitespace & formatting
    a = re.sub(r"\bDaerah\s*,\s*Istimewa\b", "Daerah Istimewa", a, flags=re.I)
    a = re.sub(r"(?:,\s*)+", ", ", a)
    return a.strip(" .,;:-")



def _extract_salaries(text: str) -> list[str]:
    # Normalisasi non-breaking space / thin space dari OCR
    text = re.sub(r"[\u00a0\u202f\u2009]", " ", text or "")
    # B1 fix: "2,8 - 9 Juta" → tangkap bilangan desimal koma sebelum rentang,
    # dan jangan biarkan label (Gaji:) nyedot angka di sebelah kiri koma.
    patterns = [
        # Rp2.500.000 - Rp5.000.000 / bulan
        r"(?:Rp\.?\s*)\d{1,3}(?:[.,]\d{3})+(?:\s*[-–]\s*(?:Rp\.?\s*)?\d{1,3}(?:[.,]\d{3})+)?(?:\s*/\s*(?:bulan|bln|month))?",
        # Rp 2,5 juta - 9 juta / 2,5jt - 9jt
        r"(?:Rp\.?\s*)\d{1,3}(?:[.,]\d{1,3})?\s*(?:jt|juta|rb|ribu)(?:\s*[-–]\s*\d{1,3}(?:[.,]\d{1,3})?\s*(?:jt|juta|rb|ribu))?",
        # Label + rentang dengan satu satuan di ujung: "Gaji: 2,8 - 9 Juta" / "Gaji 2,8-9 jt"
        r"(?:Gaji|Salary|Upah|THP|Besaran\s*Gaji|Rentang\s*[Gg]aji)\s*[:.]?\s*"
        r"\d{1,3}(?:[.,]\d+)?\s*[-–]\s*\d{1,3}(?:[.,]\d+)?\s*(?:jt|juta|rb|ribu)?",
        # Label + angka tunggal: "Gaji: 4.500.000" / "Gaji: 4,5 juta"
        r"(?:Gaji|Salary|Upah|THP|Besaran\s*Gaji|Rentang\s*[Gg]aji)\s*[:.]?\s*"
        r"\d{1,3}(?:[.,]\d+){0,2}\s*(?:jt|juta|rb|ribu)?",
        # Rentang polos: "2,8 - 9 Juta" / "3-5 jt" (tanpa label)
        r"\b\d{1,3}(?:[.,]\d+)?\s*[-–]\s*\d{1,3}(?:[.,]\d+)?\s*(?:jt|juta|ribu|rb)\b",
    ]
    found: list[str] = []
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.I):
            s = re.sub(r"\s+", " ", m.group(0)).strip(" .,;:")
            if not s:
                continue
            s_low = s.lower()
            # Skip jika sudah ada entri yang lebih lengkap (substring)
            if any(s_low in x.lower() and len(x) > len(s) for x in found):
                continue
            # Hapus entri yang lebih pendek & substring dari yang baru
            found = [x for x in found if not (x.lower() in s_low and len(x) < len(s))]
            if s_low not in {x.lower() for x in found}:
                found.append(s)
    return found


def fix_email_ocr_typos(email: str) -> str:
    e = (email or "").strip()
    if "@" not in e:
        return e
    user, domain = e.split("@", 1)
    domain_low = domain.lower().strip()
    typo_map = {
        "gmai.com": "gmail.com",
        "gamil.com": "gmail.com",
        "gmial.com": "gmail.com",
        "gmal.com": "gmail.com",
        "gmaill.com": "gmail.com",
        "gmai.co": "gmail.com",
        "gmai.id": "gmail.com",
        "yaho.com": "yahoo.com",
        "yaho.co.id": "yahoo.co.id",
        "hotmai.com": "hotmail.com",
    }
    if domain_low in typo_map:
        return f"{user}@{typo_map[domain_low]}"
    return f"{user}@{domain_low}"



def clean_indonesian_phone(ph: str) -> str:
    clean_ph = re.sub(r"\D", "", str(ph))
    if clean_ph.startswith("0"):
        clean_ph = "62" + clean_ph[1:]
    elif clean_ph.startswith("8"):
        clean_ph = "62" + clean_ph

    # Trim landline (+62 2xx, 3xx, 7xx, 9xx) dan HP (+628xx)
    if re.match(r"^62[2379]", clean_ph):
        max_len = 12 if clean_ph.startswith("62274") else 13
        clean_ph = clean_ph[:max_len]
    elif clean_ph.startswith("628") and len(clean_ph) > 13:
        clean_ph = clean_ph[:13]

    if len(clean_ph) >= 9:
        return "+" + clean_ph
    return ""


def _normalize_ocr_spacing(text: str) -> str:
    """
    Perbaiki spacing OCR generik:
    - JRetno / JImogiri → Jl. Retno / Jl. Imogiri
    - digit nempel huruf (03Panggung → 03 Panggung)
    - huruf nempel digit (No.190f → No. 190 f)
    - CamelCase nempel (NgropohCondongcatur → Ngropoh Condongcatur)
    - RT/RW tanpa spasi
    """
    t = text or ""
    t = t.replace("_", " ")
    t = re.sub(r"\b(Jl|Jln|Jalan)\.?\s*", "Jl. ", t, flags=re.I)

    t = re.sub(r"\bJ([A-Z][a-z]{2,})\b", r"Jl. \1", t)
    t = re.sub(r"\bJl([A-Z][a-z]{2,})\b", r"Jl. \1", t)
    t = re.sub(r"([0-9])([A-Za-z])", r"\1 \2", t)
    t = re.sub(r"([A-Za-z])([0-9])", r"\1 \2", t)
    t = re.sub(r"([a-z])([A-Z])", r"\1 \2", t)
    t = re.sub(r"\bRT\.?\s*0*(\d+)\s*R[Ww]\.?\s*0*(\d+)\b", r"RT \1 RW \2", t, flags=re.I)
    t = re.sub(r"\bRT\.?\s*0*(\d+)\b", r"RT \1", t, flags=re.I)
    t = re.sub(r"\bR[Ww]\.?\s*0*(\d+)\b", r"RW \1", t, flags=re.I)
    t = re.sub(r",\s*", ", ", t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()




def _address_confidence(s: str) -> float:
    """
    Skor seberapa mirip string ini dengan alamat Indonesia.
    Tidak bergantung pada nama kota spesifik.
    """
    if not s or len(s) < 8:
        return 0.0
    score = 0.0
    low = s.lower()

    has_street = bool(re.search(rf"\b(?:{_STREET_PREFIX})\b", s, re.I))
    if has_street:
        score += 2.0
    if re.search(r"\bRT\.?\s*\d+", s, re.I):
        score += 1.5
    if re.search(r"\bRW\.?\s*\d+", s, re.I):
        score += 1.0
    if re.search(r"\b(?:Kel\.?|Kelurahan|Kec\.?|Kecamatan|Kab\.?|Kabupaten|Kota|Prov)\b", s, re.I):
        score += 1.2
    if re.search(r"\b\d{5}\b", s):  # kode pos
        score += 1.5
    if re.search(r"\bNo\.?\s*\d+", s, re.I):
        score += 0.8
    if re.search(r"\bBlok\s*[A-Z0-9]", s, re.I):
        score += 0.8
    if "," in s:
        score += 0.4
    # Pasangan "Kec/Kota, Kota/Kab" Indonesia (Godean, Yogyakarta)
    if re.search(rf"\b(?:{_INDONESIAN_CITIES})\s*,\s*(?:{_INDONESIAN_CITIES})\b", s, re.I):
        score += 1.8
    tokens = [t for t in re.split(r"\s+", s) if t]
    if len(tokens) >= 4:
        score += 0.5
    if len(tokens) >= 7:
        score += 0.5

    # penalti
    if re.search(
        r"\b(?:gaji|syarat|kualifikasi|lamar|email|whatsapp|account\s*officer|"
        r"lowongan|pekerjaan|benefit|transfer|biaya|membutuhkan|dibutuhkan|"
        r"crew|hiring|hanya|dibawah|kontak|hubungi|posisi|join|team|outlet)\b",
        low,
    ):
        score -= 3.0
    if "@" in s or re.search(r"https?://|www\.", low):
        score -= 3.0
    if re.search(r"(?:\+?62|0)\d{8,}", s):  # nomor HP di dalam alamat
        score -= 1.5
    if re.fullmatch(r"[\d\s\-+()]+", s):
        score -= 3.0
    # cuma "Kab. X" / "Kota X" tanpa street/RT → terlalu generik
    if not has_street and not re.search(r"\bRT\.?\s*\d+", s, re.I) and len(tokens) <= 3:
        score -= 2.0

    return score


def _is_plausible_address(s: str) -> bool:
    c = _clean_address(s)
    if len(c) < 12 or len(c) > 180:
        return False
    # Tolak jika baris murni kualifikasi/soft skills (misal "Jujur, Disiplin, Cekatan, Komunikatif")
    if re.search(
        r"\b(?:jujur|disiplin|cekatan|komunikatif|ramah|rapi|pria|wanita|berpengalaman|kuliah|shift|weekend|bekerjasama)\b",
        c,
        re.I,
    ) and not re.search(rf"\b(?:{_STREET_PREFIX})\b", c, re.I):
        return False
    if re.match(rf"^(?:{_COMPANY_LEGAL})\.?\s", c, re.I) and not re.search(
        rf"\b(?:{_STREET_PREFIX})\b", c, re.I
    ):
        return False
    # Tolak jika mengandung frasa noise media sosial (Threads/IG UI text)
    if re.search(
        r"(?:Lihat\s+apa\s+yang\s+sedang|bergabunglah\s+dengan\s+percakapan|Laporkan\s+masalah|Pengunggahan\s+Kontak|nonpengguna\s+meta|daftar\s+instagram|lihat\s+postingan\s+lainnya)",
        s,
        re.I,
    ):
        return False

    # Tolak jika weak prefix (ds/gang/gg) diikuti frasa tipe pekerjaan/kualifikasi bukan nama tempat
    # Gg. Mawar / Ds. Sukamaju = OK (diikuti nama proper)
    # ds Lihat / gang Full Time = TOLAK (bukan nama lokasi)
    if re.match(
        r"^(?:ds\.?\s+|desa\s+|gg\.?\s+|gang\s+|dusun\s+)(?:[a-z]|Full\s*Time|Part\s*Time|Project|Magang|Internship|Freelance|Kerja|Syarat|Kualifikasi|Info|Loker)",
        c,
        re.I,
    ):
        return False

    # Pasangan 2-4 kota/kecamatan "X, Y, Z" Indonesia (misal: Pakem, Sleman, Yogyakarta) lolos langsung
    if re.fullmatch(
        rf"(?:{_INDONESIAN_CITIES})(?:\s*,\s*(?:{_INDONESIAN_CITIES})){{1,3}}",
        c,
        flags=re.I,
    ):
        return True
    # Fallback Universal: Pasangan 2-4 nama wilayah Title-Case berpemisah koma (misal: "Panyabungan, Mandailing Natal, Sumatera Utara")
    if re.fullmatch(
        r"[A-Z][a-z0-9.]+(?:\s+[A-Z][a-z0-9.]+)*(?:\s*,\s*[A-Z][a-z0-9.]+(?:\s+[A-Z][a-z0-9.]+)*){1,3}",
        c,
    ):
        return True


    # wajib sinyal lokasi konkret (bukan cuma "Kota X" / "Kab. Y")
    if not re.search(
        rf"(?:{_STREET_PREFIX}|\bRT\.?\s*\d+|\b\d{{5}}\b|\bBlok\s*[A-Z0-9]|"
        rf"\bNo\.?\s*\d+|\bKel\.?|\bKelurahan|\bKec\.?|\bKecamatan)",
        c,
        re.I,
    ):
        return False
    # tolak admin-only pendek: "Kota Surabaya", "Kab. Karawang"
    if re.fullmatch(
        r"(?:Kota|Kab\.?|Kabupaten|Prov\.?|Provinsi)\s+[A-Za-z.]+",
        c,
        flags=re.I,
    ):
        return False
    return _address_confidence(c) >= 2.5


def _split_stuck_company_tokens(core: str) -> str:
    """
    OCR kadang nempel ALLCAPS: RUMAHBAIKCAKRAWALA → coba sisip spasi
    dari email local-part / kata umum (best-effort, non-destructive).
    """
    c = (core or "").strip()
    if not c or " " in c or len(c) < 8:
        return c
    # sudah Title/lower mixed → biarkan CamelCase splitter
    if re.search(r"[a-z]", c) and re.search(r"[A-Z]", c):
        return re.sub(r"([a-z])([A-Z])", r"\1 \2", c)
    # ALLCAPS nempel: sisip spasi di batas suku kata umum Indonesia (whitelist kecil generik)
    known = (
        "RUMAH", "BAIK", "CAKRAWALA", "MAJU", "JAYA", "ABADI", "SEJAHTERA",
        "MANDIRI", "NUSANTARA", "GLOBAL", "PRIMA", "SUKSES", "BERSAMA",
        "INDO", "INDONESIA", "GROUP", "HOLDING", "SENTOSA", "MAKMUR",
    )
    up = c.upper()
    # greedy longest match
    parts = []
    i = 0
    while i < len(up):
        matched = None
        for w in sorted(known, key=len, reverse=True):
            if up.startswith(w, i):
                matched = w
                break
        if matched:
            parts.append(matched.title() if not up.isupper() else matched)
            i += len(matched)
        else:
            # ambil sisa huruf sampai known berikutnya
            j = i + 1
            while j < len(up) and not any(up.startswith(w, j) for w in known):
                j += 1
            parts.append(up[i:j])
            i = j
    return " ".join(p for p in parts if p)


def _normalize_company_name(name: str) -> str:
    name = re.sub(r"\s+", " ", (name or "")).strip().rstrip(".,;:")
    name = re.split(rf"\s+(?:{_COMPANY_STOP})\b", name, maxsplit=1, flags=re.I)[0]
    name = re.split(
        r"\s+(?:membuka|membutuhkan|dibutuhkan|sedang|lowongan|pekerjaan|rekrut)\b",
        name,
        maxsplit=1,
        flags=re.I,
    )[0]
    # PT/CV/UD → "PT. X"; Yayasan/Koperasi tanpa titik paksa
    def _prefix(m):
        form = m.group(1).upper().rstrip(".")
        if form in {"PT", "CV", "UD", "PD", "FA"}:
            return form + ". "
        return form.title() + " "

    m = re.match(rf"^({_COMPANY_LEGAL})\.?\s*(.*)$", name, flags=re.I)
    if m:
        form = m.group(1)
        core = _split_stuck_company_tokens(m.group(2).strip())
        name = f"{form} {core}".strip()
        name = re.sub(rf"^({_COMPANY_LEGAL})\.?\s*", _prefix, name, count=1, flags=re.I)
    else:
        name = _split_stuck_company_tokens(name)
    return re.sub(r"\s+", " ", name).strip().rstrip(".,;:")


def _extract_companies(text: str) -> list[str]:
    """
    Ekstrak badan usaha fleksibel:
    1) Legal form: PT/CV/UD/Yayasan/Koperasi/...
    2) Narasi: "X merupakan Perusahaan..."
    3) Label: "Perusahaan: X" / "Nama PT: X"
    """
    companies: list[str] = []

    # 1) Legal form — match per baris dulu biar tidak nyedot alamat
    for line in (text or "").splitlines():
        ln = line.strip()
        if not ln:
            continue
        m = re.match(
            rf"^((?:{_COMPANY_LEGAL})\.?\s*[A-Z0-9][A-Za-z0-9&'.-]*(?:\s+[A-Z0-9][A-Za-z0-9&'.-]*){{0,5}})"
            rf"(?:\s*\(|\s*$|\s*[,.]|\s+(?:{_COMPANY_STOP}))",
            ln,
            flags=re.I,
        )
        if not m:
            # inline di tengah kalimat: "PT SINAR TERANG membuka..."
            m = re.search(
                rf"\b((?:{_COMPANY_LEGAL})\.?\s*[A-Z0-9][A-Za-z0-9&'.-]*(?:\s+[A-Z0-9][A-Za-z0-9&'.-]*){{0,5}})"
                rf"(?=\s+(?:membuka|buka|sedang|mencari|butuh|lowongan|rekrut|hiring|,|\.|$))",
                ln,
                flags=re.I,
            )
        if not m:
            continue
        name = _normalize_company_name(m.group(1))
        if re.search(r"\b(ke|hrd|membuka|lowongan|pekerjaan|syarat|merupakan|membutuhkan)\b", name, re.I):
            continue
        if re.search(rf"\b(?:{_STREET_PREFIX}|RT|RW)\b", name, re.I):
            continue
        if len(name.split()) < 2 or len(name) < 5:
            continue
        companies.append(name)

    # 2) "X merupakan Perusahaan / PT / CV ..."
    for m in re.finditer(
        r"\b([A-Z][A-Za-z0-9&'.-]{2,}(?:\s+[A-Z][A-Za-z0-9&'.-]{1,}){0,4})\s+"
        r"merupakan\s+(?:sebuah\s+)?(?:perusahaan|pt|cv|ud|yayasan|koperasi)\b",
        text,
        flags=re.I,
    ):
        brand = re.sub(r"\s+", " ", m.group(1)).strip()
        if len(brand) >= 3 and not re.search(r"\b(?:lowongan|pekerjaan|syarat)\b", brand, re.I):
            companies.append(brand)

    # 3) Label eksplisit
    for m in re.finditer(
        r"(?:Nama\s*(?:Perusahaan|PT|CV|Instansi)|Perusahaan|Instansi|Perusahaan\s*Kami)\s*[:\-]\s*"
        r"([^\n,]{3,80})",
        text,
        flags=re.I,
    ):
        name = _normalize_company_name(m.group(1))
        if len(name) >= 3:
            companies.append(name)

    # 4) Header banner brand sebelum "WE'RE HIRING" / "HIRING" / "LOWONGAN KERJA"
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    for idx, line in enumerate(lines):
        if re.search(r"^(?:WE'?RE|WE\s+ARE|HIRING|LOWONGAN|OPEN\s+RECRUITMENT|DIBUTUHKAN)", line, re.I):
            if idx > 0:
                header_lines = [
                    l for l in lines[max(0, idx-3):idx] 
                    if not re.search(r"^(?:\[|===|URL Target|TEKS|DESKRIPSI)", l, re.I)
                    and not re.search(r"\b(?:loker|dibatasi|slide|page|halaman)\b", l, re.I)
                ]
                if header_lines:
                    candidate = " ".join(header_lines).strip()
                    candidate = _normalize_company_name(candidate)
                    if len(candidate) >= 3 and not re.search(r"\b(?:syarat|kualifikasi|gaji|email|loker|info|staff|admin|dapur)\b", candidate, re.I):
                        companies.append(candidate)
            break

    # 5) Brand names ending with common agency/business keywords (MANAGEMENT, CENTER, GROUP, etc.)
    for line in lines:
        if re.search(r"^(?:\[|===|URL Target|TEKS|DESKRIPSI)", line, re.I):
            continue
        if re.search(
            r"\b[A-Za-z0-9&'.-]{2,}\s+(?:[A-Za-z0-9&'.-]{2,}\s+){0,3}(?:MANAGEMENT|CENTER|GROUP|SOLUSINDO|DIGITAL|STUDIO|MEDIA|CORPORATION|SERVICES|STORE|OFFICIAL|ENTERPRISE|LOGISTICS)\b",
            line,
            flags=re.I,
        ):
            candidate = _normalize_company_name(line)
            if (
                candidate
                and 5 <= len(candidate) <= 60
                and len(candidate.split()) <= 6
                and not re.search(r"\b(?:loker|info|syarat|gaji|email|kualifikasi|staff|admin|pengetahuan|dasar|iklan|digital|marketing)\b", candidate, re.I)
            ):
                companies.append(candidate)

    # 6) Brand ALLCAPS berdiri sendiri (OCR poster): "SUSHI YAY!", "INDONESIA COLLEGE"
    #    Minimal 2 kata, max 5 kata, tidak ada stopword lowongan
    _BRAND_STOP = (
        r"hiring|lowongan|posisi|syarat|kualifikasi|gaji|email|wa|whatsapp|"
        r"hubungi|loker|info|join|team|crew|outlet|dibutuhkan|segera|"
        r"ringkasan|deskripsi|benefit|fasilitas|pendidikan|pengalaman|umur|gender|"
        r"jl|jln|jalan|gg|gang|alamat|lokasi|no|rt|rw|profesional|pelamar|karyawan|pegawai|staff|admin"
    )
    for line in lines:
        ln = line.strip().rstrip("!*")
        # baris harus ALLCAPS atau Title Case multiword
        if not re.match(r"^[A-Z][A-Z0-9\s&'.!?-]{3,60}$", ln):
            continue
        words = ln.split()
        if not (2 <= len(words) <= 5):
            continue
        if re.search(rf"\b(?:{_BRAND_STOP})\b", ln, re.I):
            continue
        # Skip jika sudah diawali legal form (sudah ditangkap pattern 1)
        if re.match(rf"^(?:{_COMPANY_LEGAL})\b", ln, re.I):
            continue
        # Skip jika baris ini adalah label umum
        if re.match(r"^(?:WE|ARE|THE|AND|FOR|WITH|DARI|UNTUK|YANG)\b", ln):
            continue
        candidate = _normalize_company_name(ln)
        if len(candidate) >= 5:
            companies.append(candidate)

    # 7) Brand setelah frasa "Let's Join to" / "Bergabung dengan" / "Gabung dengan"
    for m in re.finditer(
        r"(?:Let'?s[ \t]+Join[ \t]+to|Bergabung[ \t]+(?:dengan|ke)|Gabung[ \t]+(?:dengan|di)|"
        r"Join[ \t]+(?:to|with)|Tim|Team)[ \t]+([A-Z][A-Za-z0-9&'.!?-]{2,}(?:[ \t]+[A-Z][A-Za-z0-9&'.!?-]{1,}){0,3})",
        text,
        flags=re.I,
    ):
        brand = re.sub(r"!+$", "", m.group(1)).strip()
        if len(brand) >= 3 and not re.search(rf"\b(?:{_BRAND_STOP})\b", brand, re.I):
            companies.append(brand)

    # Filter akhir: buang tag metadata/header jika ada yang lolos
    clean_companies = []
    for comp in companies:
        c = re.sub(r"^(?:\[.*?\]\s*|===.*?===\s*)", "", comp).strip()
        if c and not re.search(r"^(?:TEKS UTAMA|POSTER/GAMBAR|DESKRIPSI POSTINGAN|URL Target)", c, re.I):
            clean_companies.append(c)

    return clean_companies


def _extract_addresses(text: str) -> list[str]:
    """
    Multi-strategy, tanpa whitelist kota:
    A) Label alamat (Alamat:/Lokasi:)
    B) Span dari street-prefix + marker admin/RT-RW/kode pos
    C) Baris struktural (confidence score)
    D) Multi-line join (2-3 baris beruntun yang mirip alamat)
    """
    norm_text = _normalize_ocr_spacing(text or "")
    raw_lines = [(ln or "").strip() for ln in norm_text.splitlines() if (ln or "").strip()]
    spaced_lines = [
        ln for ln in raw_lines
        if not re.search(
            r"^(?:Send(?:\s+your)?\s+CV(?:\s+to)?|Our\s+Location|Subjek\s+emai?l|Pendaftaran(?:\s+Nama)?\s+Pelamar|Kirim\s+lamaran\s+ke|Apply\s+via)\b",
            ln,
            re.I,
        )
    ]
    spaced = "\n".join(spaced_lines)
    flat = re.sub(r"\s*\n\s*", ", ", spaced)
    flat = re.sub(r"(?:,\s*)+", ", ", flat)



    candidates: list[str] = []

    # A) Label eksplisit — paling andal lintas layout
    for m in re.finditer(
        rf"(?:Alamat(?:\s*(?:Kantor|Lengkap|Perusahaan|Toko))?|Lokasi(?:\s*Kerja)?|"
        rf"Bertempat\s*di|Tempat(?:\s*Kerja)?|Office|Basecamp)\s*[:.\-]?\s*"
        rf"(.{{8,200}}?)(?=\s*(?:{_ADDR_STOP}|\n\n|$))",
        spaced,
        flags=re.I | re.S,
    ):
        candidates.append(m.group(1))

    # B) Span flat: mulai street-prefix, ambil sampai stop/akhir, min ada marker admin ATAU koma+token
    for m in re.finditer(
        rf"\b((?:{_STREET_PREFIX})\s+.{{8,160}}?)"
        rf"(?=\s*(?:{_ADDR_STOP}|(?:{_STREET_PREFIX})\s+[A-Z]|{_COMPANY_LEGAL}\.?|$))",
        flat,
        flags=re.I,
    ):
        span = m.group(1).strip()
        if re.search(rf"(?:{_ADMIN_MARKER})", span, re.I) or span.count(",") >= 1:
            candidates.append(span)

    # C) Baris tunggal dengan confidence struktural
    for ln in spaced_lines:
        if _is_plausible_address(ln):
            candidates.append(ln)

    # C2) Lokasi kota/kecamatan tanpa prefix jalan:
    #     "Godean, Yogyakarta", "Seturan, Yogyakarta"
    #     Match per baris supaya koma batas antar baris tidak ikut.
    for ln in spaced_lines:
        m_city = re.search(
            rf"\b((?:{_INDONESIAN_CITIES})\s*,\s*(?:{_INDONESIAN_CITIES}))\b",
            ln,
            flags=re.I,
        )
        if m_city:
            span = m_city.group(1).strip(" .,;:-")
            candidates.append(span)
            continue  # baris ini sudah selesai

        # Fallback: satu baris hanya nama kota + tidak ada stopword
        # (misal poster hanya tulis "Yogyakarta" atau "Sleman, DIY")
        if re.fullmatch(
            rf"(?:{_INDONESIAN_CITIES})(?:\s*,\s*(?:{_INDONESIAN_CITIES}))?",
            ln.strip(),
            flags=re.I,
        ) and not re.search(
            r"\b(?:gaji|syarat|kualifikasi|email|wa|hubungi|lamar)\b",
            ln,
            re.I,
        ):
            candidates.append(ln.strip())

    # D) Gabung 2 s/d 5 baris beruntun yang semuanya mirip elemen alamat
    # Filter dulu baris non-alamat (seperti label email/pendaftaran/syarat) agar 2-column OCR tidak menyela alamat
    addr_only_lines = [
        ln for ln in spaced_lines
        if not re.search(
            r"\b(?:syarat|kualifikasi|gaji|email|lamar|account\s*officer|"
            r"lowongan|pekerjaan|informasi|hubungi|wa\b|phone|telp|cv|subjek|subject|pendaftaran|pelamar|send|"
            r"kuliah|server|steward|pria|wanita|berpengalaman|shift|weekend|bekerjasama|jujur|disiplin|cekatan|komunikatif|posisi|penempatan)\b",
            ln,
            re.I,
        )
        and not re.match(rf"^(?:{_COMPANY_LEGAL})\.?\s", ln, re.I)
        and not re.search(r"(?:\+?62|0)\d[\d\s\-]{7,}", ln)
    ]


    n_lines = len(addr_only_lines)
    for length in range(min(5, n_lines), 1, -1):
        for i in range(n_lines - length + 1):
            block = addr_only_lines[i : i + length]
            combined_text = ", ".join(block)
            if (
                re.search(rf"\b(?:{_STREET_PREFIX}|RT\.?\s*\d+)\b", combined_text, re.I)
                or re.search(rf"(?:{_ADMIN_MARKER})", combined_text, re.I)
            ):
                if _is_plausible_address(combined_text):
                    candidates.append(combined_text)


    cleaned: list[str] = []
    for a in candidates:
        c = _clean_address(_normalize_ocr_spacing(a))
        if not _is_plausible_address(c):
            continue
        cleaned.append(c)
    return cleaned


def _is_bare_brand_not_url(url: str) -> bool:
    """
    Deteksi apakah string adalah 'nama brand' bukan URL nyata.
    Contoh yang HARUS dibuang: 'eplus.co', 'brand.co', 'nama.id'
    Contoh yang BOLEH lolos: 'eplus.co/careers', 'www.eplus.co', 'https://eplus.co', 'eplus.co.id'

    Rule: Jika string tidak punya http/www DAN tidak punya path (/) DAN
    hanya terdiri dari 2 label domain (misal 'sesuatu.co'), itu kemungkinan nama brand bukan URL.
    """
    u = url.strip()
    # Punya scheme atau www → pasti URL
    if re.match(r"^https?://", u, re.I) or re.match(r"^www\.", u, re.I):
        return False
    # Punya path (slash) → pasti URL atau shortlink
    if "/" in u:
        return False
    # Hitung jumlah label domain
    parts = u.split(".")
    # ≥3 label → seperti 'co.id', 'my.id', 'sch.id' → bisa valid
    if len(parts) >= 3:
        return False
    # Tepat 2 label (misal 'eplus.co') → bare brand, bukan URL
    # HANYA filter .co karena di Indonesia sering dipakai sebagai singkatan brand ("eplus.co" = "eplus company")
    # .id adalah ccTLD resmi Indonesia → JANGAN difilter (lokerjakarta.id, tokopedia.id = website nyata)
    tld = parts[-1].lower() if len(parts) >= 2 else ""
    if len(parts) == 2 and tld == "co":
        return True
    return False


def _uniq(items: list[str]) -> list[str]:

    """Dedup exact + near-substring + truncated addresses/salaries; prefer yang lebih lengkap & bersih."""
    normed = []
    for item in items:
        s = re.sub(r"\s+", " ", (item or "").strip())
        if s:
            normed.append(s)

    def _clean_token_set(text: str) -> set[str]:
        cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
        return {w[:6] for w in cleaned.split() if len(w) >= 3}

    def rank(s: str) -> tuple:
        has_strong_street = 1 if re.search(r"\b(?:Jl\.?|Jln\.?|Jalan|Komp\.?|Perum\.?|Ruko|Gedung|Tower)\b", s, re.I) else 0
        has_street = 1 if re.search(rf"\b(?:{_STREET_PREFIX})\b", s, re.I) else 0
        has_zip = 1 if re.search(r"\b\d{5}\b", s) else 0
        has_admin = 1 if re.search(rf"(?:{_ADMIN_MARKER})", s, re.I) else 0
        is_truncated = 1 if re.search(r"(?:Istime|Kec|Kab|Prov|Jl)\.?$", s, re.I) else 0
        has_junk_prefix = 1 if re.match(r"^(?:ds\.?|desa|gg\.?|gang|dusun)\s+", s, re.I) and not re.search(r"\b(?:No\.?|RT|RW|Kec|Kab|Kota|\d{5})\b", s, re.I) else 0
        noise = 2 if re.search(r"(?:\+?62|0)\d{8,}", s) else 0
        has_formatting = 1 if " " in s and not "+" in s else 0
        completeness = (has_strong_street * 3) + (has_street * 1) + (has_zip * 2) + (has_admin * 2)
        return (-completeness, has_junk_prefix, is_truncated, -has_formatting, noise, -len(s))

    normed.sort(key=rank)

    out: list[str] = []
    for s in normed:
        key = s.lower()
        dominated = False
        tokens_s = _clean_token_set(s)

        for prev in out:
            pk = prev.lower()
            if key == pk:
                dominated = True
                break
            # Cek prefix overlap (misal "Jl. Imogiri Barat No.29...")
            if len(key) >= 12 and len(pk) >= 12:
                if key[:25] == pk[:25] or pk[:25] == key[:25]:
                    dominated = True
                    break
            # Check token overlap
            tokens_p = _clean_token_set(prev)
            if tokens_s and tokens_p:
                inter = len(tokens_s & tokens_p)
                min_len = min(len(tokens_s), len(tokens_p))
                if min_len > 0 and (inter / min_len >= 0.65):
                    dominated = True
                    break
        if not dominated:
            out.append(s)
    return out



def extract_entities_from_text(text: str) -> dict:
    """Ekstrak companies, contacts, emails, urls, addresses, salaries (regex only)."""
    raw_text_input = text or ""
    normalized_text = re.sub(r"\bJI\b\.?\s*", "Jl. ", raw_text_input, flags=re.I)
    normalized_text = re.sub(r"\bJI\.\s*", "Jl. ", normalized_text, flags=re.I)
    normalized_text = re.sub(r"\bJ\|\b\.?\s*", "Jl. ", normalized_text)
    # Hapus tanda kurung telepon OCR seperti (0274) atau 0274)
    normalized_text = re.sub(r"([0-9]{3,5})\)", r"\1 ", normalized_text)
    normalized_text = re.sub(r"\(([0-9]{3,5})\)", r" \1 ", normalized_text)
    normalized_text = normalize_phone_typos(normalized_text)

    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    url_pattern = (
        r"(?:https?://[^\s\"'\<\>]+|www\.[^\s\"'\<\>]+|"
        # B3 fix: shortlink populer tanpa scheme (bit.ly/x, s.id/x, dll)
        # [a-zA-Z0-9] di awal path supaya tidak nyedot karakter OCR liar
        r"\b(?:bit\.ly|s\.id|tinyurl\.com|t\.co|goo\.gl|ow\.ly|rebrand\.ly|"
        r"cutt\.ly|shorturl\.at|rb\.gy|linktr\.ee|linktree|forms\.gle|"
        r"docs\.google\.com/forms|wa\.me|t\.me|telegram\.me)"
        r"/[a-zA-Z0-9][^\s\"'\<\>]*|"
        # B4 fix: domain dengan atau tanpa path (indonesiacollege.co.id, perusahaan.com, forms.gle, bit.ly)
        r"\b[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\."
        r"(?:co\.id|or\.id|ac\.id|go\.id|sch\.id|web\.id|my\.id|biz\.id|"
        r"com|id|net|org|xyz|info|io|app|shop|store|co|gle|ly|link|site|page)"
        r"(?:/[^\s\"'\<\>]*)?)"
    )
    # Dukung juga nomor telepon area/landline Indonesia (misal 0274 373608 atau 021 5551234)
    phone_pattern = r"(?:\+62|62|0)\s*[1-9](?:[\s\-]?\d){6,12}"

    search_blob = raw_text_input + "\n" + _normalize_ocr_spacing(normalized_text) + "\n" + normalized_text

    emails_raw = list(set(re.findall(email_pattern, search_blob)))
    emails = [fix_email_ocr_typos(e) for e in emails_raw]
    urls = list(set(re.findall(url_pattern, search_blob)))
    email_domains = {email.split("@")[1].lower() for email in emails if "@" in email}
    email_domains.update({"gmai.com", "gmail.com", "yahoo.com", "hotmail.com", "gamil.com", "gmial.com"})
    urls = [
        url for url in urls
        if url.lower() not in emails
        and url.lower() not in email_domains
        and not re.search(r"^(?:gmail|yahoo|hotmail|gmai|gamil)\.(?:com|co|id)$", url, re.I)
        and not re.match(r"^[a-zA-Z]\.(?:com|co|id)$", url, re.I)
        # Tolak bare domain 2-label tanpa http/www/path yang kemungkinan nama brand (misal "eplus.co")
        # Domain sah minimal: punya http/www, ATAU punya path (/), ATAU ≥3 label (co.id, my.id)
        and not _is_bare_brand_not_url(url)
    ]



    phones_raw = list(set(re.findall(phone_pattern, search_blob)))
    standardized_phones = []
    for ph in phones_raw:
        c_ph = clean_indonesian_phone(ph)
        if c_ph:
            standardized_phones.append(c_ph)


    salaries = _extract_salaries(search_blob)
    extracted_addresses = _extract_addresses(raw_text_input) + _extract_addresses(
        _normalize_ocr_spacing(normalized_text)
    ) + _extract_addresses(normalized_text)

    companies = _extract_companies(raw_text_input) + _extract_companies(
        _normalize_ocr_spacing(normalized_text)
    ) + _extract_companies(normalized_text)

    # Fallback Perusahaan dari domain email khusus (misal lamaran@deliciabakery.com -> Delicia Bakery)
    for email in emails:
        if "@" in email:
            dom = email.split("@")[1].lower()
            if dom not in FREE_EMAIL_DOMAINS and "." in dom:
                brand_part = dom.split(".")[0]
                if len(brand_part) >= 4:
                    # ubah deliciabakery -> Delicia Bakery / Deliciabakery
                    formatted = re.sub(r"([a-z])(bakery|group|official|store|center|tech|media|studio)\b", r"\1 \2", brand_part, flags=re.I).title()
                    if formatted not in companies:
                        companies.insert(0, formatted)

    uniq_companies = _uniq(companies)
    uniq_contacts = _uniq(standardized_phones)
    uniq_emails = _uniq(emails)
    uniq_addresses_raw = _uniq(extracted_addresses)
    # Buang kandidat alamat yang sama atau bagian dari nama perusahaan
    comp_lows = {c.strip().lower() for c in uniq_companies}
    uniq_addresses = [
        a for a in uniq_addresses_raw
        if a.strip().lower() not in comp_lows
        and not any(a.strip().lower() in c or c in a.strip().lower() for c in comp_lows if len(c) >= 6)
    ]


    # Deteksi inkonsistensi kota antara alamat yang diekstrak vs teks asli poster
    conflicts = []
    addr_cities = {c for a in uniq_addresses for c in re.findall(rf"\b(?:{_INDONESIAN_CITIES})\b", a, re.I)}
    text_cities = set(re.findall(rf"\b(?:{_INDONESIAN_CITIES})\b", raw_text_input, re.I))
    conflict_cities = addr_cities - text_cities
    if conflict_cities and text_cities:
        conflicts.append({
            "type": "LOCATION_MISMATCH",
            "severity": "HIGH",
            "detail": f"Alamat menyebut {', '.join(sorted(conflict_cities))}, tapi teks utama menyebut {', '.join(sorted(text_cities))}."
        })

    return {
        "companies": uniq_companies,
        "contacts": uniq_contacts,
        "emails": uniq_emails,
        "urls": _uniq(urls),
        "addresses": uniq_addresses,
        "salaries": _uniq(salaries),
        # ponytail: confidence statis per-kategori — upgrade ke skor per-entitas saat ada labeled dataset
        "entity_confidences": {
            "companies": round(min(0.98, 0.7 + len(uniq_companies) * 0.05), 2) if uniq_companies else 0.0,
            "contacts": round(min(0.95, 0.75 + len(uniq_contacts) * 0.05), 2) if uniq_contacts else 0.0,
            "emails": round(min(0.99, 0.85 + len(uniq_emails) * 0.05), 2) if uniq_emails else 0.0,
            "addresses": round(min(0.88, 0.6 + len(uniq_addresses) * 0.07), 2) if uniq_addresses else 0.0,
        },
        # ponytail: template_similarity belum diimplementasi — upgrade ke MinHash/SimHash saat ada dataset template fraud
        "fraud_fingerprint": {
            "template_similarity": None,
            "layout_fingerprint_match": None,
            "signature_hash": compute_content_sha256(raw_text_input)[:16]
        },
        "evidence_conflicts": conflicts
    }
