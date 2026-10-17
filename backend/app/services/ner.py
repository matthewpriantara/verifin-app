from __future__ import annotations

import re

from app.services.hasher import compute_content_sha256

def clean_indonesian_phone(ph: str) -> str:
    clean_ph = re.sub(r"\D", "", str(ph))
    if clean_ph.startswith("0"):
        clean_ph = "62" + clean_ph[1:]
    elif clean_ph.startswith("8"):
        clean_ph = "62" + clean_ph
    if len(clean_ph) >= 9 and clean_ph.startswith("628"):
        return "+" + clean_ph
    return ""

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
    return f"{user}@{typo_map.get(domain_low, domain_low)}"

# Baris berisi kontak admin akun penyebar/iklan, bukan kontak perekrut.
_PROMOTER_LINE = re.compile(
    r"\b(?:admin|pasang\s+(?:loker|iklan|lowongan)|promosi(?:kan)?|endorse|iklan\s+loker|"
    r"mau\s+dipromosikan|hubungi\s+admin)\b",
    re.I,
)

# Kata yang sering tertangkap sebagai entitas padahal bukan nama/lokasi/gaji.
_JUNK_ENTITY = {
    "kerja", "perusahaan", "kompetitif", "nego", "negotiable", "menarik", "lokasi", "cabang",
    "kantor", "tempat", "area", "wilayah", "domisili", "penempatan", "sesuai", "terlampir", "-",
}


# Frasa deskriptif yang bukan nama tempat, mis. "seluruh jaringan cabang perusahaan".
_JUNK_PHRASE = re.compile(r"\b(?:seluruh|semua|jaringan|perusahaan|ditempatkan|bersedia|sesuai\s+kebutuhan)\b", re.I)


def is_junk_entity(value: str) -> bool:
    v = re.sub(r"[^a-z0-9 ]", " ", (value or "").lower()).strip()
    return not v or v in _JUNK_ENTITY or all(w in _JUNK_ENTITY for w in v.split())


def is_junk_location(value: str) -> bool:
    return is_junk_entity(value) or bool(_JUNK_PHRASE.search(value or ""))


def uniq_casefold(items: list[str]) -> list[str]:
    seen, out = set(), []
    for item in _uniq(items):
        key = re.sub(r"\s+", " ", item.casefold())
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _uniq(items: list[str]) -> list[str]:
    return list(dict.fromkeys(re.sub(r"\s+", " ", (i or "")).strip() for i in items if (i or "").strip()))
_DATE_TIME_JUNK = re.compile(
    r"\b(?:tanggal|tgl|jadwal|waktu|pukul|jam|periode|deadline|batas\s+waktu|"
    r"senin|selasa|rabu|kamis|jumat|sabtu|minggu|"
    r"januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember|"
    r"jan|feb|mar|apr|jun|jul|agu|ags|sep|sept|okt|oct|nov|des|dec|"
    r"wib|wita|wit)\b",
    re.I
)

_DATE_PATTERNS = re.compile(
    r"(?:\d{1,2}\s*[-/.]\s*\d{1,2}\s*[-/.]\s*\d{2,4}|\d{1,2}[:.]\d{2}|\b202[0-9]\b)",
    re.I
)

def _is_plausible_address(s: str) -> bool:
    c = re.sub(r"\s+", " ", (s or "")).strip(" .,;:-·•*")
    if len(c) < 8 or len(c) > 180:
        return False
    if re.search(r"\b(gaji|salary|kualifikasi|syarat|benefit|posisi|lowongan|dibutuhkan)\b", c, re.I):
        return False
    if _DATE_TIME_JUNK.search(c) or _DATE_PATTERNS.search(c):
        return False
    physical_indicators = (
        r"\b(?:jl\.?|jln\.?|jalan|gg\.?|gang|ruko|komplek|perumahan|gedung|tower|"
        r"blok|rt|rw|kelurahan|kecamatan|desa|dusun|no\.?\s*\d+|km\.?\s*\d+|kode\s*pos)\b"
    )
    if not re.search(physical_indicators, c, re.I):
        return False
    return True
def _is_fee_context(text: str, start: int, end: int) -> bool:
    window_start = max(0, start - 100)
    window_end = min(len(text), end + 60)
    ctx = text[window_start:window_end].lower()
    fee_keywords = [
        "biaya", "transfer", "bayar", "setor", "deposit", "uang jaminan",
        "uang pendaftaran", "tiket", "akomodasi", "reimburse", "rekening",
        "tarif", "seragam", "pelatihan", "training", "booking", "pemesanan"
    ]
    return any(kw in ctx for kw in fee_keywords)

_SALARY_SHORT = re.compile(
    r"Rp\.?\s*\d{1,3}(?:[.,]\d{1,3})?\s*(?:rb|ribu|k|jt|juta)\b(?:\s*/\s*(?:hari|minggu|bulan|bln|jam))?",
    re.I,
)
_SALARY_MINIMUM = re.compile(r"\b(?:gaji\s+)?UM[RPK](?:\s*\+\s*\w+)?\b", re.I)


def _extract_salaries(text: str) -> list[str]:
    found = []
    for pat in (_SALARY_SHORT, _SALARY_MINIMUM):
        for m in pat.finditer(text or ""):
            if not _is_fee_context(text or "", m.start(), m.end()):
                found.append(re.sub(r"\s+", " ", m.group(0)).strip())
    pat = r"(?:Rp\.?\s*)\d{1,3}(?:[.,]\d{3})+(?:\s*[-–]\s*(?:Rp\.?\s*)?\d{1,3}(?:[.,]\d{3})+)?(?:\s*/\s*(?:bulan|bln|month|hari|minggu|jam))?"
    for m in re.finditer(pat, text or "", re.I):
        if not _is_fee_context(text or "", m.start(), m.end()):
            found.append(re.sub(r"\s+", " ", m.group(0)).strip())
    for m in re.finditer(r"\b\d{1,2}(?:[.,]\d{1,2})?\s*(?:-\s*\d{1,2}(?:[.,]\d{1,2})?\s*)?juta(?:\s*/\s*(?:bulan|bln))?\b", text or "", re.I):
        if not _is_fee_context(text or "", m.start(), m.end()):
            found.append(re.sub(r"\s+", " ", m.group(0)).strip())
    return _uniq(found)

def _extract_fee_requests(text: str) -> list[str]:
    found = []
    pat = r"(?:Rp\.?\s*)\d{1,3}(?:[.,]\d{3})+(?:\s*[-–]\s*(?:Rp\.?\s*)?\d{1,3}(?:[.,]\d{3})+)?(?:\s*/\s*(?:bulan|bln|month))?"
    for m in re.finditer(pat, text or "", re.I):
        if _is_fee_context(text or "", m.start(), m.end()):
            found.append(re.sub(r"\s+", " ", m.group(0)).strip())
    if not found and re.search(r"\b(?:transfer|biaya|bayar|deposit|setor)\b.*?\b(?:rekening|tiket|akomodasi|travel|jaminan|seragam)\b", text or "", re.I):
        found.append("Permintaan transfer biaya/tiket terindikasi")
    return _uniq(found)

def _extract_location_candidates(text: str) -> list[str]:
    candidates = []
    pat = r"\b(?:Lokasi(?:\s+Kerja)?|Penempatan(?:\s+Kerja)?|Wilayah|Area|Domisili|Cabang)[^\S\r\n]*[:\-][^\S\r\n]*([^\n,]{3,60})"
    for m in re.finditer(pat, text or "", re.I):
        loc = re.sub(r"\s+", " ", m.group(1)).strip(" .,;:-·•*")
        if len(loc) >= 3 and not is_junk_location(loc) and not re.search(r"\b(gaji|syarat|kualifikasi|email|wa|hubungi)\b", loc, re.I):
            if not _DATE_TIME_JUNK.search(loc) and not _DATE_PATTERNS.search(loc):
                candidates.append(loc)
    return _uniq(candidates)
def _extract_companies(text: str) -> list[str]:
    results = []
    pat = r"\b(PT|CV|UD|PD|Perum|Persero|Yayasan|Koperasi|Firma|Fa|BUMDes|BUMN)\.?\s+([A-Za-z0-9&'.-]+(?:\s+[A-Za-z0-9&'.-]+){0,5})"
    for m in re.finditer(pat, text or "", re.I):
        form = m.group(1).upper()
        raw = m.group(2).strip()
        core = re.split(r"\s+(?:membuka|buka|sedang|mencari|butuh|membutuhkan|lowongan|rekrut|hiring|open|dibutuhkan|,|\.|$)\b", raw, flags=re.I)[0].strip()
        if form == "CV" and re.search(r"^(?:ke|anda|terbaru|lamaran|dan|atau|terupdate)\b", core, re.I):
            continue
        if len(core) >= 3 and not re.search(r"^(?:ke|dari|untuk|di|dengan|pada)\b", core, re.I):
            prefix = f"{form}. " if form in {"PT", "CV", "UD"} else f"{form.title()} "
            results.append(f"{prefix}{core}")
    label = r"(?:Nama\s+(?:Perusahaan|Usaha|Toko|Instansi)(?:\s*/\s*(?:Perusahaan|Usaha|Toko|Instansi))?|Perusahaan|Instansi|Company)"
    for m in re.finditer(label + r"[^\S\r\n]*[:\-][^\S\r\n]*([^\n,]{3,60})", text or "", re.I):
        name = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(".,;:")
        if len(name) >= 3 and not re.search(r"\b(membuka|lowongan|syarat|gaji)\b", name, re.I):
            results.append(name)
    return _uniq(results)

def _extract_addresses(text: str) -> list[str]:
    candidates = []
    street_pat = r"\b((?:Jl\.?|Jln\.?|Jalan|Gg\.?|Gang|Ruko|Komplek|Perumahan|Gedung|Tower)\s+[A-Za-z0-9\s.,/-]{5,100}?)(?=[^\S\r\n]*(?:\n|Email|WA|WhatsApp|Hubungi|Gaji|Syarat|Kualifikasi|$))"
    for m in re.finditer(street_pat, text or "", re.I):
        addr = re.sub(r"\s+", " ", m.group(1)).strip(" .,;:-·•*")
        if len(addr) >= 10:
            candidates.append(addr)
    label_pat = r"(?:Alamat(?:\s+Kantor)?)[^\S\r\n]*[:.\-][^\S\r\n]*([^\n]{8,120})"
    for m in re.finditer(label_pat, text or "", re.I):
        addr = re.sub(r"\s+", " ", m.group(1)).strip(" .,;:-·•*")
        if len(addr) >= 10 and not re.search(r"\b(gaji|syarat|kualifikasi|email|wa)\b", addr, re.I):
            candidates.append(addr)
    return [a for a in _uniq(candidates) if _is_plausible_address(a)]
def extract_entities_from_text(text: str) -> dict:
    raw_text = text or ""
    phone_pat = r"(?:\+62|62|0)\s*[1-9](?:[\s\-]?\d){6,12}"
    phones, promoter_phones = [], []
    for line in raw_text.splitlines() or [raw_text]:
        found = [clean_indonesian_phone(p) for p in re.findall(phone_pat, line)]
        (promoter_phones if _PROMOTER_LINE.search(line) else phones).extend(found)
    phones = [p for p in _uniq(phones) if p]
    promoter_phones = [p for p in _uniq(promoter_phones) if p and p not in phones]

    email_pat = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    emails = _uniq([fix_email_ocr_typos(e) for e in re.findall(email_pat, raw_text)])

    url_pat = r"https?://[^\s<>\"'{}|\\^`]+"
    urls = _uniq([u.rstrip(".,;:!?)]}") for u in re.findall(url_pat, raw_text)])

    companies = _extract_companies(raw_text)
    addresses = _extract_addresses(raw_text)
    salaries = _extract_salaries(raw_text)
    fee_requests = _extract_fee_requests(raw_text)
    locations = _extract_location_candidates(raw_text)

    return {
        "companies": companies,
        "phones": phones,
        "emails": emails,
        "urls": urls,
        "addresses": addresses,
        "location_candidates": locations,
        "salaries": salaries,
        "fee_requests": fee_requests,
        "promoter_phones": promoter_phones,
        "extraction_meta": {
            "has_company": bool(companies),
            "has_phone": bool(phones),
            "has_email": bool(emails),
            "has_address": bool(addresses),
            "has_location_candidate": bool(locations),
            "has_salary": bool(salaries),
            "has_fee_request": bool(fee_requests),
            "text_too_short": len(raw_text) < 50,
        },
        "fraud_fingerprint": {
            "template_similarity": None,
            "layout_fingerprint_match": None,
            "signature_hash": compute_content_sha256(raw_text)[:16]
        },
        "evidence_conflicts": []
    }
