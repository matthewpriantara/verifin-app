from __future__ import annotations

import re

from app.services.constants import FREE_EMAIL_DOMAINS
from app.services.hasher import compute_content_sha256

_ADDR_STOP = (
    r"(?:\bGaji\b|\bSalary\b|\bUpah\b|\bKontak\b|\bContact\b|\bEmail\b|\bWA\b|\bWhatsApp\b|\bHubungi\b|"
    r"\bKirim\b|\bCV\b|\bCover\s*Letter\b|\bSend(?:\s*your)?\b|\bSubjek\b|\bSubject\b|\bApply\b|\bApply\s*Now\b|\bMore\s*Information\b|"
    r"\bLamaran\b|\bBenefit\b|\bSyarat\b|\bKualifikasi\b|\bPosisi\b|\bLowongan\b|"
    r"\bInfo\b|\bInformasi\b|\bNB\b|\bCatatan\b|\bNote\b|\bTransfer\b|\bBiaya\b|\bDeposit\b|\bDeskripsi\b|"
    r"\bPekerjaan\b|\bRingkasan\b|\bFormulir\b|\bAccount\b|\bOfficer\b|\bLamar\b|"
    r"\b(?:Alamat|Lokasi|Kantor|Cabang|Domisili)\b(?:\s+[^,:]{0,25})?\s*[:.\-])"
)

_STREET_PREFIX = (
    r"(?:Jl\.?|Jln\.?|Jalan|Gg\.?|Gang|Dusun|Ds\.?|Desa|"
    r"Komp\.?|Komplek|Kompleks|Perum\.?|Perumahan|Blok|Cluster|"
    r"Ruko|Rukan|Gedung|Tower|Lt\.?|Lantai|Kampus|Kantor)"
)

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
    "Sleman|Bantul|Gunungkidul|Kulon Progo|Klaten|Boyolali|Sragen|"
    "Wonogiri|Karanganyar|Magelang|Purworejo|Kebumen|Temanggung|"
    "Wonosobo|Banjarnegara|Purbalingga|Cilacap|Banyumas|"
    "Pakem|Sewon|Imogiri|Ngaglik|Ngemplak|Turi|Tempel|Seyegan|Minggir|Moyudan|"
    "Godean|Seturan|Mlati|Depok|Kalasan|Prambanan|Berbah|Gamping|Piyungan|Kasihan|Sedayu|"
    "Kotagede|Umbulharjo|Gondokusuman|Wirobrajan|Banguntapan|"
    "Manding|Wukirsari|Dlingo|Pleret|Jetis|Srandakan|Sanden|Kretek|Pundong|Bambanglipuro|"
    "Bantul|Sewon|Banguntapan|Pajangan|Inpres|Krapyak|Gamping|Patangpuluhan"
    "Cikarang|Karawang|Purwakarta|Subang|Indramayu|Majalengka|"
    "Kuningan|Sumedang|Garut|Cianjur|Sukabumi|Tasikmalaya|"
    "Gresik|Sidoarjo|Lamongan|Tuban|Bojonegoro|Jombang|"
    "Kediri|Blitar|Tulungagung|Trenggalek|Ponorogo|Pacitan"
)

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
_BRAND_STOP = (
    r"hiring|lowongan|posisi|syarat|kualifikasi|gaji|email|wa|whatsapp|"
    r"hubungi|loker|info|join|team|crew|outlet|dibutuhkan|segera|"
    r"ringkasan|deskripsi|benefit|fasilitas|pendidikan|pengalaman|umur|gender|"
    r"jam\s+kerja|shift|libur|bonus|reward|gaji|"
    r"jl|jln|jalan|gg|gang|alamat|lokasi|no|rt|rw|profesional|pelamar|karyawan|pegawai|staff|admin|"
    r"penempatan|wilayah|area|kota|provinsi|kecamatan|kelurahan"
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
    a = re.sub(r"\bJI\.", "Jl.", a)
    a = re.sub(r"\bJI(?=[A-Za-z])", "Jl. ", a)
    a = re.sub(r"\bJalan(?=[A-Z])", "Jalan ", a)
    a = re.sub(r"\bJl\.(?=[A-Z])", "Jl. ", a)
    a = re.sub(r"\blstimewa\b", "Istimewa", a, flags=re.I)
    a = re.sub(r"URL\s+Target\s*:\s*\S+", "", a, flags=re.I)
    a = re.sub(r"\[TEKS\s+.*?(?:\]|$)", "", a, flags=re.I)
    a = re.sub(r"\[.*?\]:?", "", a)
    a = re.sub(
        r"^(?:Alamat(?:\s+(?:lain|Kantor|Lengkap|Perusahaan|Toko))?|"
        r"Lokasi(?:\s+(?:kerja|lain))?|Kantor(?:\s+(?:utama|pusat))?|"
        r"Cabang|Domisili|Penempatan(?:\s*(?:Kerja|Kantor))?|"
        r"Bertempat\s*di|Tempat(?:\s*Kerja)?|Office|Basecamp|Kode\s*Pos)\s*[:.\-]?\s*",
        "",
        a,
        flags=re.I,
    )
    a = re.sub(r"^(?:di|di\s+area)\s+", "", a, flags=re.I)
    _STRONG_STREET_PREFIX = r"(?:Jl\.?|Jln\.?|Jalan|Komp\.?|Komplek|Kompleks|Perum\.?|Perumahan|Ruko|Rukan|Gedung|Tower|Kampus|Kantor)"
    m_strong = re.search(rf"\b({_STRONG_STREET_PREFIX})\b", a, re.I)
    if m_strong and m_strong.start() > 0:
        a = a[m_strong.start():]
    else:
        a = re.sub(r"^[A-Z0-9\s&'.!?-]{3,60},\s*(?=(?:Gg|Dusun|Ds|Lt|Lantai|Outlet|Toko)\b)", "", a, flags=re.I)
        weak_marker = re.search(r"\b(?:Gg|Dusun|Ds|Lt|Lantai)\b", a, re.I)
        qualifier = re.search(
            r"\b(?:kuliah|server|steward|kualifikasi|syarat|pria|wanita|"
            r"berpengalaman|shift|weekend|bekerjasama|jujur|disiplin|cekatan|"
            r"komunikatif|posisi|penempatan|pendidikan|sma|smk|d3|s1|usia|"
            r"maks|thn|tahun)\b",
            a,
            re.I,
        )
        if qualifier and weak_marker and qualifier.start() < weak_marker.start():
            a = a[weak_marker.start():]
    a = re.split(
        r"\s+(?=(?:(?:Alamat|Lokasi|Kantor|Cabang|Domisili|Office|Basecamp)\b(?:\s+[^,:]{0,30})?)\s*[:.\-])",
        a,
        maxsplit=1,
        flags=re.I,
    )[0]
    a = re.split(rf"\s*[.,;]?\s*{_ADDR_STOP}", a, maxsplit=1, flags=re.I)[0]
    a = re.sub(r"\s+(?:Phone|Telp|Tel\.?|HP|WA|WhatsApp)\s*[:.]?\s*[\d+\-\s]+$", "", a, flags=re.I)
    a = re.sub(r"^(?:\+?62|0)\d[\d\s\-]{7,16}[,\s]*", "", a)
    a = re.sub(r"\s+(?:Gaji|Salary|Upah|Send|Subjek|Subject|CV|Apply|More)\s*[:.]?\s*.*$", "", a, flags=re.I)
    a = re.sub(
        r",?\s*\b(?:Server|Steward|Waitress?|Kasir|Barista|Cook|Kitchen|Helper|Staff|Admin)\b\s*,?",
        ", ",
        a,
        flags=re.I,
    )
    a = re.sub(
        rf",?\s*\b(?:{_COMPANY_LEGAL})\.?\s*[A-Za-z0-9\s&'.]+$",
        "",
        a,
        flags=re.I,
    )
    a = re.sub(r"\bDaerah\s*,\s*Istimewa\b", "Daerah Istimewa", a, flags=re.I)
    a = re.sub(r"(?:,\s*)+", ", ", a)
    return a.strip(" .,;:-")



def _extract_salaries(text: str) -> list[str]:
    text = re.sub(r"[\u00a0\u202f\u2009]", " ", text or "")
    patterns = [
        r"(?:Rp\.?\s*)\d{1,3}(?:[.,]\d{3})+(?:\s*[-–]\s*(?:Rp\.?\s*)?\d{1,3}(?:[.,]\d{3})+)?(?:\s*/\s*(?:bulan|bln|month))?",
        r"(?:Rp\.?\s*)\d{1,3}(?:[.,]\d{1,3})?\s*(?:jt|juta|rb|ribu)(?:\s*[-–]\s*\d{1,3}(?:[.,]\d{1,3})?\s*(?:jt|juta|rb|ribu))?",
        r"(?:Gaji|Salary|Upah|THP|Besaran\s*Gaji|Rentang\s*[Gg]aji)\s*[:.]?\s*"
        r"\d{1,3}(?:[.,]\d+)?\s*[-–]\s*\d{1,3}(?:[.,]\d+)?\s*(?:jt|juta|rb|ribu)?",
        r"(?:Gaji|Salary|Upah|THP|Besaran\s*Gaji|Rentang\s*[Gg]aji)\s*[:.]?\s*"
        r"\d{1,3}(?:[.,]\d+){0,2}\s*(?:jt|juta|rb|ribu)?",
        r"\b\d{1,3}(?:[.,]\d+)?\s*[-–]\s*\d{1,3}(?:[.,]\d+)?\s*(?:jt|juta|ribu|rb)\b",
    ]
    found: list[str] = []
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.I):
            s = re.sub(r"\s+", " ", m.group(0)).strip(" .,;:")
            if not s:
                continue
            s_low = s.lower()
            if any(s_low in x.lower() and len(x) > len(s) for x in found):
                continue
            found = [x for x in found if not (x.lower() in s_low and len(x) < len(s))]
            if s_low not in {x.lower() for x in found}:
                found.append(s)
    label_pattern = (
        r"(?:Besaran\s+Gaji|Rentang\s+Gaji|Gaji|Salary|Upah|THP)\s*[:.]\s*"
        r"([A-Za-z][A-Za-z /-]{2,32})(?=\s*(?:\n|$|,|\.))"
    )
    for match in re.finditer(label_pattern, text, flags=re.I):
        value = re.sub(r"\s+", " ", match.group(1)).strip(" -")
        if value and value.lower() not in {item.lower() for item in found}:
            found.append(value)
    return found


def fix_email_ocr_typos(email: str) -> str:
    e = (email or "").strip().strip(".,;:)")
    if "@" not in e:
        return e
    user, domain = e.split("@", 1)
    domain_low = domain.lower().strip(".,;:)")
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
    if re.match(r"^62[2379]", clean_ph):
        max_len = 12 if clean_ph.startswith("62274") else 13
        clean_ph = clean_ph[:max_len]
    elif clean_ph.startswith("628") and len(clean_ph) > 13:
        clean_ph = clean_ph[:13]

    if len(clean_ph) >= 9:
        return "+" + clean_ph
    return ""


def _normalize_ocr_spacing(text: str) -> str:
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
    if re.search(r"\b\d{5}\b", s):
        score += 1.5
    if re.search(r"\bNo\.?\s*\d+", s, re.I):
        score += 0.8
    if re.search(r"\bBlok\s*[A-Z0-9]", s, re.I):
        score += 0.8
    if "," in s:
        score += 0.4
    if re.search(rf"\b(?:{_INDONESIAN_CITIES})\s*,\s*(?:{_INDONESIAN_CITIES})\b", s, re.I):
        score += 1.8
    tokens = [t for t in re.split(r"\s+", s) if t]
    if len(tokens) >= 4:
        score += 0.5
    if len(tokens) >= 7:
        score += 0.5
    if re.search(
        r"\b(?:gaji|syarat|kualifikasi|lamar|email|whatsapp|account\s*officer|"
        r"lowongan|pekerjaan|benefit|transfer|biaya|membutuhkan|dibutuhkan|"
        r"crew|hiring|hanya|dibawah|kontak|hubungi|posisi|join|team|outlet)\b",
        low,
    ):
        score -= 3.0
    if "@" in s or re.search(r"https?://|www\.", low):
        score -= 3.0
    if re.search(r"(?:\+?62|0)\d{8,}", s):
        score -= 1.5
    if re.fullmatch(r"[\d\s\-+()]+", s):
        score -= 3.0
    if not has_street and not re.search(r"\bRT\.?\s*\d+", s, re.I) and len(tokens) <= 3:
        if not re.search(rf"\b(?:{_INDONESIAN_CITIES})\s*,\s*(?:{_INDONESIAN_CITIES})\b", s, re.I):
            score -= 2.0

    return score


def _is_plausible_address(s: str) -> bool:
    c = _clean_address(s)
    if len(c) < 12 or len(c) > 180:
        return False
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
    if re.search(
        r"(?:Lihat\s+apa\s+yang\s+sedang|bergabunglah\s+dengan\s+percakapan|Laporkan\s+masalah|Pengunggahan\s+Kontak|nonpengguna\s+meta|daftar\s+instagram|lihat\s+postingan\s+lainnya)",
        s,
        re.I,
    ):
        return False
    if re.match(
        r"^(?:ds\.?\s+|desa\s+|gg\.?\s+|gang\s+|dusun\s+)(?:[a-z]|Full\s*Time|Part\s*Time|Project|Magang|Internship|Freelance|Kerja|Syarat|Kualifikasi|Info|Loker)",
        c,
        re.I,
    ):
        return False
    if not re.search(
        rf"(?:\b(?:{_STREET_PREFIX})\b|\bRT\.?\s*\d+|\bRW\.?\s*\d+|\b\d{{5}}\b|"
        rf"\bBlok\s*[A-Z0-9]|\bNo\.?\s*\d+)",
        c,
        re.I,
    ):
        if re.search(
            rf"\b(?:{_INDONESIAN_CITIES})\s*,\s*(?:{_INDONESIAN_CITIES})\b",
            c,
            re.I,
        ):
            return True
        return False
    return _address_confidence(c) >= 2.5


def _extract_location_candidates(text: str) -> list[str]:
    lines = [line.strip() for line in _normalize_ocr_spacing(text or "").splitlines() if line.strip()]
    label_pattern = re.compile(
        r"^(?:[•·\-\*]\s*)?(?:Lokasi(?:\s+Kerja)?|Penempatan(?:\s+Kerja)?|Wilayah|Area|"
        r"Domisili|Cabang|Outlet|Alamat)\s*[:.\-]?\s*(.*)$", re.I
    )
    values: list[str] = []
    for index, line in enumerate(lines):
        match = label_pattern.match(line)
        if not match:
            continue
        value = match.group(1).strip()
        values.append(value or (lines[index + 1] if index + 1 < len(lines) else ""))

    candidates: list[str] = []
    for value in values:
        value = re.sub(r"^Cabang\s*[:.\-]?\s*", "", value, flags=re.I)
        value = re.sub(r"\([^)]*\)", "", value)
        for item in re.split(r"\s*(?:,|;|/|\||\s+dan\s+|\s*&\s*)\s*", value, flags=re.I):
            item = item.strip(" .:-")
            if not item or _is_plausible_address(item) or len(item) < 2 or len(item) > 80:
                continue
            if re.search(r"@|https?://|(?:\+?62|0)\d[\d\s-]{7,}", item, re.I):
                continue
            if re.search(r"\b(?:pendidikan|pengalaman|gender|umur|gaji|bonus|benefit|reward|libur|syarat|deskripsi|pekerjaan|shift|kirim|lamaran|lamar|email|telepon|juta|tahun|maks|wanita|pria|kompetitif|cv|dan|dengan|serta|atau|ke|di|yang|untuk|dari|pada|dalam|hal|dll|dsb)\b", item, re.I):
                continue
            if re.search(r"[a-z]{2,}[A-Z][a-z]", item):
                continue
            candidates.append(item)
    return _uniq(candidates)


def _split_stuck_company_tokens(core: str) -> str:
    """
    OCR kadang nempel ALLCAPS: RUMAHBAIKCAKRAWALA → coba sisip spasi
    dari email local-part / kata umum (best-effort, non-destructive).
    """
    c = (core or "").strip()
    if not c or " " in c or len(c) < 8:
        return c
    if re.search(r"[a-z]", c) and re.search(r"[A-Z]", c):
        return re.sub(r"([a-z])([A-Z])", r"\1 \2", c)
    known = (
        "RUMAH", "BAIK", "CAKRAWALA", "MAJU", "JAYA", "ABADI", "SEJAHTERA",
        "MANDIRI", "NUSANTARA", "GLOBAL", "PRIMA", "SUKSES", "BERSAMA",
        "INDO", "INDONESIA", "GROUP", "HOLDING", "SENTOSA", "MAKMUR",
    )
    up = c.upper()
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
    companies: list[str] = []
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

    for m in re.finditer(
        r"\b([A-Z][A-Za-z0-9&'.-]{2,}(?:\s+[A-Z][A-Za-z0-9&'.-]{1,}){0,4})\s+"
        r"merupakan\s+(?:sebuah\s+)?(?:perusahaan|pt|cv|ud|yayasan|koperasi)\b",
        text,
        flags=re.I,
    ):
        brand = re.sub(r"\s+", " ", m.group(1)).strip()
        if len(brand) >= 3 and not re.search(r"\b(?:lowongan|pekerjaan|syarat)\b", brand, re.I):
            companies.append(brand)
    for m in re.finditer(
        r"(?:^|[\n\r]|[\.\!\?]\s*)(?:@)?([A-Za-z0-9&'.-]+(?:\s+[A-Za-z0-9&'.-]+){0,3})\s+(?:is\s+hiring|are\s+hiring|membuka\s+lowongan|sedang\s+merekrut|sedang\s+membuka)\b",
        text,
        flags=re.I,
    ):
        cand = m.group(1).strip()
        cand = re.sub(r"^@+", "", cand).strip()
        if len(cand) >= 3 and not re.search(rf"\b(?:{_BRAND_STOP}|kami|kita|we|they|our|the)\b", cand, re.I):
            companies.append(_normalize_company_name(cand))

    for m in re.finditer(
        r"(?:Nama\s*(?:Perusahaan|PT|CV|Instansi)|Perusahaan|Instansi|Perusahaan\s*Kami)\s*[:\-]\s*"
        r"([^\n,]{3,80})",
        text,
        flags=re.I,
    ):
        name = _normalize_company_name(m.group(1))
        if len(name) >= 3:
            companies.append(name)

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

    for line in lines:
        ln = line.strip().rstrip("!*")
        if not re.match(r"^[A-Z][A-Z0-9\s&'.!?-]{3,60}$", ln):
            continue
        words = ln.split()
        if not (2 <= len(words) <= 5):
            continue
        if re.search(rf"\b(?:{_BRAND_STOP})\b", ln, re.I):
            continue
        if re.match(rf"^(?:{_COMPANY_LEGAL})\b", ln, re.I):
            continue
        if re.match(r"^(?:WE|ARE|THE|AND|FOR|WITH|DARI|UNTUK|YANG)\b", ln):
            continue
        candidate = _normalize_company_name(ln)
        if len(candidate) >= 5:
            companies.append(candidate)

    for m in re.finditer(
        r"(?:Let'?s[ \t]+Join[ \t]+to|Bergabung[ \t]+(?:dengan|ke)|Gabung[ \t]+(?:dengan|di)|"
        r"Join[ \t]+(?:to|with)|Tim|Team)[ \t]+([A-Z][A-Za-z0-9&'.!?-]{2,}(?:[ \t]+[A-Z][A-Za-z0-9&'.!?-]{1,}){0,3})",
        text,
        flags=re.I,
    ):
        brand = re.sub(r"!+$", "", m.group(1)).strip()
        if len(brand) >= 3 and not re.search(rf"\b(?:{_BRAND_STOP})\b", brand, re.I):
            companies.append(brand)
    _HEADER_KEYWORDS = re.compile(
        r"^(?:DIBUTUHKAN|LOWONGAN|KERJA|WE'?RE|WE\s+ARE|HIRING|OPEN\s+RECRUITMENT|"
        r"DIBUTUHKAN\s+STAF|LOWONGAN\s+KERJA|LOKER|VACANCY|CAREER)",
        re.I,
    )
    for idx, line in enumerate(lines):
        if not _HEADER_KEYWORDS.search(line):
            continue
        for next_idx in range(idx + 1, min(idx + 4, len(lines))):
            next_line = lines[next_idx].strip().rstrip("!*")
            if not next_line or _HEADER_KEYWORDS.search(next_line):
                continue
            if re.search(rf"\b(?:{_BRAND_STOP})\b", next_line, re.I):
                break
            if len(next_line) < 4 or len(next_line) > 60:
                continue
            words = next_line.split()
            if len(words) < 1 or len(words) > 5:
                continue
            is_title = all(w[0].isupper() or not w[0].isalpha() for w in words) if words else False
            is_allcaps = next_line.isupper()
            if not (is_title or is_allcaps):
                continue
            if re.match(r"^(?:THE|AND|FOR|WITH|DARI|UNTUK|YANG|WE|ARE)\b", next_line, re.I) and len(words) < 3:
                continue
            candidate = _normalize_company_name(next_line)
            if len(candidate) >= 4 and not re.search(rf"\b(?:{_BRAND_STOP})\b", candidate, re.I):
                companies.append(candidate)
            break

    clean_companies = []
    for comp in companies:
        c = re.sub(r"^(?:\[.*?\]\s*|===.*?===\s*)", "", comp).strip()
        if (
            c
            and not re.search(r"^(?:TEKS UTAMA|POSTER/GAMBAR|DESKRIPSI POSTINGAN|URL Target)", c, re.I)
            and c.upper() != "OCR"
            and not re.match(r"^OCR\b", c, re.I)
        ):
            clean_companies.append(c)

    for line in lines:
        if re.search(r"^(?:\[|===|URL Target|TEKS|DESKRIPSI)", line, re.I):
            continue
        if not re.search(r"\b(?:PT|CV|UD|Yayasan|Koperasi)\b|\bmembuka\b|\blowongan\b", line, re.I):
            continue
        for alias in re.findall(r"\(([^()]{3,80})\)", line):
            alias = re.sub(r"\s+", " ", alias).strip(" .,:;-!")
            if (
                len(alias) >= 3
                and len(alias.split()) <= 8
                and not re.search(r"\b(?:lowongan|posisi|syarat|gaji|alamat|email|lokasi|ocr)\b", alias, re.I)
                and alias.upper() != "OCR"
            ):
                clean_companies.append(alias)
    return clean_companies


def _extract_addresses(text: str) -> list[str]:
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

    for m in re.finditer(
        rf"(?:Alamat(?:\s+(?:lain|Kantor|Lengkap|Perusahaan|Toko))?|"
        rf"Lokasi(?:\s+(?:kerja|lain))?|Kantor(?:\s+(?:utama|pusat))?|"
        rf"Cabang|Domisili|Bertempat\s*di|Office|Basecamp)\s*[:.\-]?\s*"
        rf"([^\n]{{8,200}}?)(?=\s*(?:{_ADDR_STOP}|$))",
        spaced,
        flags=re.I | re.M,
    ):
        candidates.append(m.group(1))

    for m in re.finditer(
        rf"\b((?:{_STREET_PREFIX})\s+.{{8,160}}?)"
        rf"(?=\s*(?:{_ADDR_STOP}|(?:{_STREET_PREFIX})\s+[A-Z]|{_COMPANY_LEGAL}\.?|$))",
        flat,
        flags=re.I,
    ):
        span = m.group(1).strip()
        if re.search(rf"(?:{_ADMIN_MARKER})", span, re.I) or span.count(",") >= 1:
            candidates.append(span)

    for ln in spaced_lines:
        if _is_plausible_address(ln):
            candidates.append(ln)

    for ln in spaced_lines:
        m_city = re.search(
            rf"\b((?:{_INDONESIAN_CITIES})\s*,\s*(?:{_INDONESIAN_CITIES}))\b",
            ln,
            flags=re.I,
        )
        if m_city:
            span = m_city.group(1).strip(" .,;:-")
            candidates.append(span)
            continue
        m_kec = re.search(
            rf"\b([A-Z][a-z]{{3,}})\s*,\s*((?:{_INDONESIAN_CITIES}))\b",
            ln,
            flags=re.I,
        )
        if m_kec:
            span = m_kec.group(0).strip(" .,;:-")
            if not re.search(rf"\b(?:{_ADDR_STOP})\b", span, re.I):
                candidates.append(span)
            continue
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
    hard_noise = re.compile(
        r"\b(?:syarat|kualifikasi|gaji|email|lamar|account\s*officer|lowongan|"
        r"pekerjaan|informasi|hubungi|wa\b|phone|telp|cv|subjek|subject|"
        r"(?:alamat|lokasi|kantor|cabang|domisili)(?:\s+[^,]{0,20})?\s*[:.\-]|"
        r"pendaftaran|pelamar|send|kuliah|server|steward|pria|wanita|"
        r"berpengalaman|shift|weekend|bekerjasama|jujur|disiplin|cekatan|"
        r"komunikatif|posisi|penempatan|benefit|bonus|reward|libur|umur|"
        r"pendidikan|pengalaman|gender|deskripsi)\b", re.I
    )
    n_lines = len(spaced_lines)
    for length in range(min(5, n_lines), 1, -1):
        for i in range(n_lines - length + 1):
            block = spaced_lines[i : i + length]
            if any(hard_noise.search(line) for line in block):
                continue
            combined_text = ", ".join(block)
            if (
                re.search(rf"\b(?:{_STREET_PREFIX}|RT\.?\s*\d+)\b", combined_text, re.I)
                or re.search(rf"(?:{_ADMIN_MARKER})", combined_text, re.I)
            ) and _is_plausible_address(combined_text):
                candidates.append(combined_text)

    cleaned: list[str] = []
    for a in candidates:
        c = _clean_address(_normalize_ocr_spacing(a))
        if not _is_plausible_address(c):
            continue
        cleaned.append(c)
    return cleaned


def _is_bare_brand_not_url(url: str) -> bool:
    u = url.strip()
    if re.match(r"^https?://", u, re.I) or re.match(r"^www\.", u, re.I):
        return False
    if "/" in u:
        return False
    parts = u.split(".")
    if len(parts) >= 3:
        return False
    tld = parts[-1].lower() if len(parts) >= 2 else ""
    if len(parts) == 2 and tld == "co":
        return True
    return False


def _uniq(items: list[str]) -> list[str]:
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
            if len(key) >= 12 and len(pk) >= 12:
                if key[:25] == pk[:25] or pk[:25] == key[:25]:
                    dominated = True
                    break
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


def _uniq_addresses(items: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for item in items:
        value = re.sub(r"\s+", " ", (item or "").strip())
        if not value:
            continue
        normalized = re.sub(r"[^a-z0-9 ]", " ", value.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        numbers = tuple(re.findall(r"\b\d+[a-z]?\b", value.lower()))
        key = (normalized, numbers)
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out



def extract_entities_from_text(text: str) -> dict:
    raw_text_input = text or ""
    normalized_text = re.sub(r"\bJI\b\.?\s*", "Jl. ", raw_text_input, flags=re.I)
    normalized_text = re.sub(r"\bJI\.\s*", "Jl. ", normalized_text, flags=re.I)
    normalized_text = re.sub(r"\bJ\|\b\.?\s*", "Jl. ", normalized_text)
    normalized_text = re.sub(r"([0-9]{3,5})\)", r"\1 ", normalized_text)
    normalized_text = re.sub(r"\(([0-9]{3,5})\)", r" \1 ", normalized_text)
    normalized_text = normalize_phone_typos(normalized_text)

    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    url_pattern = (
        r"(?:https?://[^\s\"'\<\>]+|www\.[^\s\"'\<\>]+|"
        r"\b(?:bit\.ly|s\.id|tinyurl\.com|t\.co|goo\.gl|ow\.ly|rebrand\.ly|"
        r"cutt\.ly|shorturl\.at|rb\.gy|linktr\.ee|linktree|forms\.gle|"
        r"docs\.google\.com/forms|wa\.me|t\.me|telegram\.me)"
        r"/[a-zA-Z0-9][^\s\"'\<\>]*|"
        r"\b[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\."
        r"(?:co\.id|or\.id|ac\.id|go\.id|sch\.id|web\.id|my\.id|biz\.id|"
        r"com|id|net|org|xyz|info|io|app|shop|store|co|gle|ly|link|site|page)"
        r"(?:/[^\s\"'\<\>]*)?)"
    )
    phone_pattern = r"(?:\+62|62|0)\s*[1-9](?:[\s\-]?\d){6,12}"

    search_blob = raw_text_input + "\n" + _normalize_ocr_spacing(normalized_text) + "\n" + normalized_text

    emails_raw = list(set(re.findall(email_pattern, search_blob)))
    emails = [fix_email_ocr_typos(e) for e in emails_raw]
    urls = list(set(re.findall(url_pattern, search_blob)))
    urls = [url.rstrip(".,;:!?)]}") for url in urls]
    email_domains = {email.split("@")[1].lower() for email in emails if "@" in email}
    email_domains.update({"gmai.com", "gmail.com", "yahoo.com", "hotmail.com", "gamil.com", "gmial.com"})
    urls = [
        url for url in urls
        if url.lower() not in emails
        and url.lower() not in email_domains
        and not any(
            re.search(rf"(?<![A-Za-z0-9_.+-]){re.escape(email)}(?![A-Za-z0-9_.+-])", url, re.I)
            for email in emails
        )
        and not re.search(r"^(?:gmail|yahoo|hotmail|gmai|gamil)\.(?:com|co|id)$", url, re.I)
        and not re.match(r"^[a-zA-Z]\.(?:com|co|id)$", url, re.I)
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
    location_candidates = _extract_location_candidates(raw_text_input)

    companies = _extract_companies(raw_text_input) + _extract_companies(
        _normalize_ocr_spacing(normalized_text)
    ) + _extract_companies(normalized_text)

    for email in emails:
        if "@" in email:
            dom = email.split("@")[1].lower()
            if dom not in FREE_EMAIL_DOMAINS and "." in dom:
                brand_part = dom.split(".")[0]
                if len(brand_part) >= 4:
                    formatted = re.sub(r"([a-z])(bakery|group|official|store|center|tech|media|studio)\b", r"\1 \2", brand_part, flags=re.I).title()
                    if formatted not in companies:
                        companies.insert(0, formatted)

    uniq_companies = _uniq(companies)
    uniq_contacts = _uniq(standardized_phones)
    uniq_emails = _uniq(emails)
    uniq_addresses_raw = _uniq_addresses(extracted_addresses)
    comp_lows = {c.strip().lower() for c in uniq_companies}
    uniq_addresses = [
        a for a in uniq_addresses_raw
        if a.strip().lower() not in comp_lows
        and not any(a.strip().lower() in c or c in a.strip().lower() for c in comp_lows if len(c) >= 6)
    ]
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
        "phones": uniq_contacts,
        "emails": uniq_emails,
        "urls": _uniq(urls),
        "addresses": uniq_addresses,
        "location_candidates": location_candidates,
        "salaries": _uniq(salaries),
        "extraction_meta": {
            "has_company": bool(uniq_companies),
            "has_phone": bool(uniq_contacts),
            "has_email": bool(uniq_emails),
            "has_address": bool(uniq_addresses),
            "has_location_candidate": bool(location_candidates),
            "has_salary": bool(_uniq(salaries)),
            "text_too_short": len(raw_text_input) < 50,
        },
        "fraud_fingerprint": {
            "template_similarity": None,
            "layout_fingerprint_match": None,
            "signature_hash": compute_content_sha256(raw_text_input)[:16]
        },
        "evidence_conflicts": conflicts
    }
