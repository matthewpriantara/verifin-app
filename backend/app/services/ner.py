from __future__ import annotations

import re

from app.services.constants import FREE_EMAIL_DOMAINS
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

# Kalimat berisi kontak pemilik akun penyebar/iklan, bukan kontak perekrut. Kata "admin" saja
# tidak cukup: "Lowongan Admin Gudang" atau "WhatsApp admin" justru menunjuk perekrut.
_PROMOTER_LINE = re.compile(
    r"\b(?:pasang\s+(?:loker|iklan|lowongan)|promosi(?:kan)?\s+(?:loker|lowongan|usaha|bisnis)|endorse(?:ment)?|"
    r"iklan\s+loker|(?:mau|ingin)\s+di\s?promosikan|info\s+pasang|admin\s+(?:akun|grup|group|channel|page|ig|info\s+loker))\b",
    re.I,
)

# Frasa yang menyangkal biaya ("tidak dipungut biaya pendaftaran"). Dibuang dulu sebelum mencari
# permintaan biaya, supaya pernyataan gratis tidak dibaca sebagai pungutan.
NEGATED_FEE = re.compile(
    r"\b(?:tidak|tanpa|bebas|tak|bukan)\s+(?:ada\s+|akan\s+|pernah\s+)?(?:di)?(?:pungut|kenakan|kenai|minta|meminta|memungut|ada)?\s*"
    r"(?:biaya|pungutan|bayaran|uang|dana|transfer|deposit)[^.\n!?;]{0,60}"
    r"|\b(?:gratis|free)\s+(?:biaya\s+)?(?:pendaftaran|tes|seleksi|rekrutmen|interview)[^.\n!?;]{0,30}",
    re.I,
)


_RECRUITING_LINE = re.compile(
    r"\b(?:konfirmasi|kehadiran|lamaran|lamar|daftar|pendaftaran|kirim\s+cv|cv|hrd|rekrut\w*|interview|wawancara|"
    r"seleksi|kandidat|pelamar|loker|lowongan|info\s+lebih\s+lanjut|whatsapp|wa)\b",
    re.I,
)


def strip_negated_fee(text: str) -> str:
    return NEGATED_FEE.sub(" ", text or "")


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


_EMPLOYER_NOISE = re.compile(
    r"\b(?:pt|cv|ud|pd|tbk|persero|perseroan|group|grup|indonesia|official|hotel|the)\b|[^\w\s]",
    re.I,
)


def _employer_tokens(name: str) -> frozenset[str]:
    # "(AAM)" dan "(Persero)" dibuang; sisanya token nama inti.
    core = re.sub(r"\([^)]*\)", " ", name or "")
    return frozenset(t for t in _EMPLOYER_NOISE.sub(" ", core.casefold()).split() if len(t) > 1)


def count_distinct_employers(companies: list[str]) -> int:
    """Varian nama yang sama ("PT Pertamina (Persero)", "Pertamina Group") dihitung satu."""
    groups: list[frozenset[str]] = []
    for name in companies or []:
        tokens = _employer_tokens(name) if isinstance(name, str) else frozenset()
        if not tokens:
            continue
        if not any(tokens <= g or g <= tokens or len(tokens & g) * 2 >= min(len(tokens), len(g)) for g in groups):
            groups.append(tokens)
    return len(groups)


def primary_employer_name(companies: list[str]) -> str:
    """Nama yang dipakai untuk pencarian: nama pertama, kecuali ada varian yang lebih spesifik.

    "MORGANS" (OCR logo) → "Morgans Kebab"; pencarian satu kata umum menghasilkan perusahaan lain.
    """
    names = [c for c in (companies or []) if isinstance(c, str) and c.strip()]
    if not names:
        return ""
    first = names[0]
    first_tokens = _employer_tokens(first)
    richer = [n for n in names[1:] if first_tokens and first_tokens < _employer_tokens(n)]
    return max(richer, key=lambda n: len(_employer_tokens(n))) if richer else first


def is_multi_employer(entities: dict) -> bool:
    """Input memuat lowongan dari beberapa pemberi kerja: ≥ 2 nama berbeda DAN ≥ 2 nomor berbeda
    atau ≥ 2 domain email korporat berbeda.

    Satu lowongan wajar mencantumkan satu nomor + satu email, dan sering menyebut nama induk +
    nama dagang (PT Trinity Success Group / Morgans Kebab); itu tidak dihitung multi.
    """
    if count_distinct_employers(entities.get("companies") or []) < 2:
        return False
    phones = {re.sub(r"\D", "", p)[-9:] for p in (entities.get("phones") or []) if isinstance(p, str)}
    domains = {
        e.split("@")[-1].casefold() for e in (entities.get("emails") or [])
        if isinstance(e, str) and "@" in e and e.split("@")[-1].casefold() not in FREE_EMAIL_DOMAINS
    }
    return len(phones) >= 2 or len(domains) >= 2


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
    ctx = strip_negated_fee(text[window_start:window_end]).lower()
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
    # Lookbehind: "Rp30,5 juta" tidak boleh terbaca lagi sebagai "5 juta".
    for m in re.finditer(r"(?<![\d.,])\b\d{1,2}(?:[.,]\d{1,2})?\s*(?:-\s*\d{1,2}(?:[.,]\d{1,2})?\s*)?juta(?:\s*/\s*(?:bulan|bln))?\b", text or "", re.I):
        if not _is_fee_context(text or "", m.start(), m.end()):
            found.append(re.sub(r"\s+", " ", m.group(0)).strip())
    return _uniq(found)

def _extract_fee_requests(text: str) -> list[str]:
    text = strip_negated_fee(text)
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
        if form == "CV" and re.search(r"^(?:ke|anda|terbaru|terbaik|lengkap|kamu|lamaran|dan|atau|terupdate|via|beserta|serta)\b", core, re.I):
            continue
        # "Kirim CV terbaik Anda": nama badan usaha ditulis dengan huruf awal kapital atau angka.
        if form == "CV" and not (core[:1].isupper() or core[:1].isdigit()):
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
_BARE_URL = re.compile(
    r"(?<![@\w./-])(?:www\.)?[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9-]+)*"
    r"\.(?:com|net|org|id|co\.id|or\.id|web\.id|my\.id|ac\.id|go\.id|biz\.id|ly|gle|ee|me|io|link|site|xyz|info|biz|cc|to|app)"
    r"(?:/[^\s<>\"'{}|\\^`]*)?(?![\w@])",
    re.I,
)
# Domain email gratisan yang muncul tanpa '@' karena OCR, bukan tautan lowongan.
_BARE_URL_IGNORE = set(FREE_EMAIL_DOMAINS)


def extract_entities_from_text(text: str) -> dict:
    raw_text = text or ""
    phone_pat = r"(?:\+62|62|0)\s*[1-9](?:[\s\-]?\d){6,12}"
    phones, promoter_phones = [], []
    lines = raw_text.splitlines() or [raw_text]
    for idx, line in enumerate(lines):
        for m in re.finditer(phone_pat, line):
            # Konteks: kalimat nomor itu, kalimat sebelumnya, dan dua baris di atasnya
            # ("Punya loker mau dipromosikan?\nHubungi Admin\nADMIN: 0851…"). Broadcast WA
            # sering satu baris panjang, jadi baris penuh terlalu lebar sebagai konteks.
            start = max(line.rfind(ch, 0, m.start()) for ch in ".!?;")
            if start > 0:
                start = max(line.rfind(ch, 0, start) for ch in ".!?;")
            ends = [i for i in (line.find(ch, m.end()) for ch in ".!?;") if i != -1]
            sentence = line[start + 1:min(ends) if ends else len(line)]
            # Baris di atas hanya dipakai bila baris nomor itu sendiri bukan kalimat rekrutmen
            # ("ADMIN: 0851…" di bawah "mau dipromosikan?"). "Konfirmasi kehadiran via WhatsApp 0822…"
            # tetap nomor perekrut walau baris sebelumnya menyebut "admin grup".
            own_is_recruiting = bool(_RECRUITING_LINE.search(sentence))
            context = sentence if own_is_recruiting else " ".join(lines[max(0, idx - 2):idx] + [sentence])
            (promoter_phones if _PROMOTER_LINE.search(context) else phones).append(clean_indonesian_phone(m.group(0)))
    phones = [p for p in _uniq(phones) if p]
    promoter_phones = [p for p in _uniq(promoter_phones) if p and p not in phones]

    email_pat = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    emails = _uniq([fix_email_ocr_typos(e) for e in re.findall(email_pat, raw_text)])

    url_pat = r"https?://[^\s<>\"'{}|\\^`]+"
    urls = [u.rstrip(".,;:!?)]}") for u in re.findall(url_pat, raw_text)]
    # Tautan tanpa skema ("bit.ly/abc", "forms.gle/xyz", "www.pt.co.id/karir") yang umum di broadcast WA.
    without_scheme = re.sub(url_pat, " ", raw_text)
    for m in _BARE_URL.finditer(without_scheme):
        candidate = m.group(0).rstrip(".,;:!?)]}")
        host = candidate.split("/")[0].lower()
        if host in _BARE_URL_IGNORE or ("/" not in candidate and not host.startswith("www.") and host.count(".") < 1):
            continue
        urls.append("https://" + candidate)
    urls = _uniq(urls)

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
