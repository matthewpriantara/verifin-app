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

# Pemisah konten non-alamat (label seksi lowongan)
_ADDR_STOP = (
    r"(?:Gaji|GAJI|Salary|Upah|Kontak|Contact|Email|WA|WhatsApp|Hubungi|"
    r"Kirim|CV|Lamaran|Benefit|Syarat|Kualifikasi|Posisi|Lowongan|"
    r"Info|Informasi|NB|Catatan|Note|Transfer|Biaya|Deposit|Deskripsi|"
    r"Pekerjaan|Ringkasan|Formulir|Account|Officer|Lamar)"
)

# Prefix yang boleh MEMULAI alamat (bukan admin murni seperti "Kota X")
_STREET_PREFIX = (
    r"(?:Jl\.?|Jln\.?|Jalan|Gg\.?|Gang|Dusun|Ds\.?|Desa|"
    r"Komp\.?|Komplek|Kompleks|Perum\.?|Perumahan|Blok|Cluster|"
    r"Ruko|Rukan|Gedung|Tower|Lt\.?|Lantai)"
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
    # buang label alamat di depan
    a = re.sub(
        r"^(?:Alamat(?:\s*(?:Kantor|Lengkap|Perusahaan|Toko))?|Lokasi(?:\s*Kerja)?|"
        r"Bertempat\s*di|Tempat(?:\s*Kerja)?|Office|Basecamp|Kode\s*Pos)\s*[:.\-]?\s*",
        "",
        a,
        flags=re.I,
    )
    a = re.sub(r"^(?:di|di\s+area)\s+", "", a, flags=re.I)
    a = re.sub(r"\s+(?:Phone|Telp|Tel\.?|HP|WA|WhatsApp)\s*[:.]?\s*[\d+\-\s]+$", "", a, flags=re.I)
    # buang nomor HP yang nyangkut di depan
    a = re.sub(r"^(?:\+?62|0)\d[\d\s\-]{7,16}[,\s]*", "", a)
    a = re.split(rf"\s*[.,;]?\s*{_ADDR_STOP}\b", a, maxsplit=1, flags=re.I)[0]
    a = a.strip(" .,;:-")
    a = re.sub(
        r"\s+(?:Gaji|Salary|Upah)\s*[:.]?\s*.*$",
        "",
        a,
        flags=re.I,
    ).strip(" .,;:-")
    # buang prefix badan hukum yang nempel di depan alamat
    a = re.sub(
        rf"^(?:{_COMPANY_LEGAL})\.?\s+[A-Z][A-Za-z0-9\s&'.-]{{2,50}}\s+"
        rf"(?={_STREET_PREFIX})",
        "",
        a,
        flags=re.I,
    )
    # buang sisa "PT.XXX," di depan
    a = re.sub(
        rf"^(?:{_COMPANY_LEGAL})\.?\s+[A-Za-z0-9\s&'.-]{{2,40}},\s*",
        "",
        a,
        flags=re.I,
    )
    return a.strip(" .,;:-")


def _extract_salaries(text: str) -> list[str]:
    patterns = [
        r"(?:Rp\.?\s*)\d{1,3}(?:[.,]\d{3})+(?:\s*[-–]\s*(?:Rp\.?\s*)?\d{1,3}(?:[.,]\d{3})+)?(?:\s*/\s*(?:bulan|bln|month))?",
        r"(?:Rp\.?\s*)\d{1,3}(?:[.,]\d{1,3})?\s*(?:jt|juta|rb|ribu)(?:\s*[-–]\s*\d{1,3}(?:[.,]\d{1,3})?\s*(?:jt|juta|rb|ribu))?",
        r"(?:Gaji|Salary|Upah|THP)\s*[:.]?\s*\d{1,3}(?:[.,]\d{3})*(?:\s*[-–]\s*\d{1,3}(?:[.,]\d{3})*)?\s*(?:jt|juta|rb|ribu)?",
        r"(?:Gaji|Salary|Upah|THP)\s*[:.]?\s*\d{1,2}\s*[-–]\s*\d{1,2}\s*(?:jt|juta)",
        r"\b\d{1,2}\s*[-–]\s*\d{1,2}\s*(?:jt|juta)\b",
    ]
    found: list[str] = []
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.I):
            s = re.sub(r"\s+", " ", m.group(0)).strip(" .,;:")
            if s and s.lower() not in {x.lower() for x in found}:
                found.append(s)
    return found


def _normalize_ocr_spacing(text: str) -> str:
    """
    Perbaiki spacing OCR generik (bukan whitelist kota):
    - digit nempel huruf (03Panggung → 03 Panggung)
    - huruf nempel digit (No.190f → No. 190 f)
    - CamelCase nempel (NgropohCondongcatur → Ngropoh Condongcatur)
    - RT/RW tanpa spasi
    """
    t = text or ""
    t = re.sub(r"\b(Jl|Jln|Jalan)\.?\s*", "Jl. ", t, flags=re.I)
    t = re.sub(r"([0-9])([A-Za-z])", r"\1 \2", t)
    t = re.sub(r"([A-Za-z])([0-9])", r"\1 \2", t)
    # CamelCase: huruf kecil diikuti huruf besar (OCR nempel 2 kata)
    t = re.sub(r"([a-z])([A-Z])", r"\1 \2", t)
    # ALLCAPS nempel: ...HARJOSEWON → biarkan; potong di batas RT/RW saja
    t = re.sub(r"\bRT\.?\s*0*(\d+)\s*R[Ww]\.?\s*0*(\d+)\b", r"RT \1 RW \2", t, flags=re.I)
    t = re.sub(r"\bRT\.?\s*0*(\d+)\b", r"RT \1", t, flags=re.I)
    t = re.sub(r"\bR[Ww]\.?\s*0*(\d+)\b", r"RW \1", t, flags=re.I)
    t = re.sub(r",\s*", ", ", t)
    t = re.sub(r"\s+", " ", t)
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
    tokens = [t for t in re.split(r"\s+", s) if t]
    if len(tokens) >= 4:
        score += 0.5
    if len(tokens) >= 7:
        score += 0.5

    # penalti
    if re.search(
        r"\b(?:gaji|syarat|kualifikasi|lamar|email|whatsapp|account\s*officer|"
        r"lowongan|pekerjaan|benefit|transfer|biaya|membutuhkan|dibutuhkan)\b",
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
    if re.match(rf"^(?:{_COMPANY_LEGAL})\.?\s", c, re.I) and not re.search(
        rf"\b(?:{_STREET_PREFIX})\b", c, re.I
    ):
        return False
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

    name = re.sub(rf"^({_COMPANY_LEGAL})\.?\s*", _prefix, name, count=1, flags=re.I)
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
            rf"(?:\s*$|\s*[,.]|\s+(?:{_COMPANY_STOP}))",
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

    return companies


def _extract_addresses(text: str) -> list[str]:
    """
    Multi-strategy, tanpa whitelist kota:
    A) Label alamat (Alamat:/Lokasi:)
    B) Span dari street-prefix + marker admin/RT-RW/kode pos
    C) Baris struktural (confidence score)
    D) Multi-line join (2-3 baris beruntun yang mirip alamat)
    """
    raw_lines = [(ln or "").strip() for ln in (text or "").splitlines() if (ln or "").strip()]
    spaced_lines = [_normalize_ocr_spacing(ln) for ln in raw_lines]
    spaced = "\n".join(spaced_lines)
    flat = re.sub(r"\s*\n\s*", " ", spaced)

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

    # D) Gabung 2 baris beruntun HANYA jika keduanya mirip alamat
    #    (hindari nyedot HP/PT/syarat di sekitar footer poster)
    for i in range(len(spaced_lines) - 1):
        a, b = spaced_lines[i], spaced_lines[i + 1]
        if any(
            re.search(
                r"\b(?:syarat|kualifikasi|gaji|email|lamar|account\s*officer|"
                r"lowongan|pekerjaan|informasi|hubungi|wa\b|phone|telp)\b",
                ln,
                re.I,
            )
            or re.match(rf"^(?:{_COMPANY_LEGAL})\.?\s", ln, re.I)
            or re.search(r"(?:\+?62|0)\d[\d\s\-]{7,}", ln)
            for ln in (a, b)
        ):
            continue
        streetish = sum(
            1
            for ln in (a, b)
            if re.search(rf"\b(?:{_STREET_PREFIX}|RT\.?\s*\d+)\b", ln, re.I)
        )
        if streetish < 1:
            continue
        # minimal satu baris sudah plausible sendiri
        if not (_is_plausible_address(a) or _is_plausible_address(b)):
            continue
        joined = f"{a}, {b}"
        if _is_plausible_address(joined):
            candidates.append(joined)

    cleaned: list[str] = []
    for a in candidates:
        c = _clean_address(_normalize_ocr_spacing(a))
        if not _is_plausible_address(c):
            continue
        cleaned.append(c)
    return cleaned


def _uniq(items: list[str]) -> list[str]:
    """Dedup exact + near-substring; prefer yang lebih bersih."""
    normed = []
    for item in items:
        s = re.sub(r"\s+", " ", (item or "").strip())
        if s:
            normed.append(s)

    def rank(s: str) -> tuple:
        has_street = 1 if re.search(rf"\b(?:{_STREET_PREFIX})\b", s, re.I) else 0
        noise = 0
        if re.search(r"(?:\+?62|0)\d{8,}", s):
            noise += 2
        if len(s) > 120:
            noise += 1
        return (-has_street, noise, abs(len(s) - 50))

    normed.sort(key=rank)
    out: list[str] = []
    for s in normed:
        key = s.lower()
        dominated = False
        for prev in out:
            pk = prev.lower()
            if key == pk:
                dominated = True
                break
            if len(key) >= 15 and len(pk) >= 15:
                if key in pk or pk in key:
                    dominated = True
                    break
                ta, tb = set(key.split()), set(pk.split())
                if ta and tb and len(ta & tb) / max(len(ta), len(tb)) >= 0.7:
                    dominated = True
                    break
        if not dominated:
            out.append(s)
    return out


def extract_entities_from_text(text: str) -> dict:
    """Ekstrak companies, contacts, emails, urls, addresses, salaries (regex only)."""
    normalized_text = re.sub(r"\bJI\b\.?\s+", "Jl. ", text or "")
    normalized_text = re.sub(r"\bJ\|\b\.?\s+", "Jl. ", normalized_text)
    normalized_text = normalize_phone_typos(normalized_text)

    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    url_pattern = (
        r"(https?://[^\s]+|www\.[^\s]+|"
        r"[a-zA-Z0-9-]+\.(?:com|id|co\.id|net|org|xyz|info|io|app|shop|store))"
    )
    phone_pattern = r"(?:\+62|62|0)\s*[2-9](?:[\s\-]?\d){7,12}"

    search_blob = (text or "") + "\n" + _normalize_ocr_spacing(normalized_text)

    emails = list(set(re.findall(email_pattern, search_blob)))
    urls = list(set(re.findall(url_pattern, search_blob)))
    email_domains = {email.split("@")[1] for email in emails if "@" in email}
    urls = [url for url in urls if url not in emails and url not in email_domains]

    phones = list(set(re.findall(phone_pattern, search_blob)))
    standardized_phones = []
    for ph in phones:
        clean_ph = re.sub(r"\D", "", ph)
        if clean_ph.startswith("0"):
            clean_ph = "62" + clean_ph[1:]
        elif clean_ph.startswith("8"):
            clean_ph = "62" + clean_ph
        if len(clean_ph) >= 10:
            standardized_phones.append("+" + clean_ph)

    salaries = _extract_salaries(search_blob)
    extracted_addresses = _extract_addresses(text or "") + _extract_addresses(
        _normalize_ocr_spacing(normalized_text)
    )
    companies = _extract_companies(text or "") + _extract_companies(
        _normalize_ocr_spacing(normalized_text)
    )

    return {
        "companies": _uniq(companies),
        "contacts": _uniq(standardized_phones),
        "emails": _uniq(emails),
        "urls": _uniq(urls),
        "addresses": _uniq(extracted_addresses),
        "salaries": _uniq(salaries),
    }
