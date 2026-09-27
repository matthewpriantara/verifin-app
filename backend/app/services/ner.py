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

def _uniq(items: list[str]) -> list[str]:
    return list(dict.fromkeys(re.sub(r"\s+", " ", (i or "")).strip() for i in items if (i or "").strip()))

def _is_plausible_address(s: str) -> bool:
    c = re.sub(r"\s+", " ", (s or "")).strip(" .,;:-")
    if len(c) < 10 or len(c) > 180:
        return False
    if re.search(r"\b(gaji|salary|kualifikasi|syarat|benefit|posisi|lowongan|dibutuhkan)\b", c, re.I):
        return False
    return True

def _extract_salaries(text: str) -> list[str]:
    found = []
    pat = r"(?:Rp\.?\s*)\d{1,3}(?:[.,]\d{3})+(?:\s*[-–]\s*(?:Rp\.?\s*)?\d{1,3}(?:[.,]\d{3})+)?(?:\s*/\s*(?:bulan|bln|month))?"
    for m in re.finditer(pat, text or "", re.I):
        found.append(re.sub(r"\s+", " ", m.group(0)).strip())
    for m in re.finditer(r"\b\d{1,2}(?:[.,]\d{1,2})?\s*(?:-\s*\d{1,2}(?:[.,]\d{1,2})?\s*)?juta(?:\s*/\s*(?:bulan|bln))?\b", text or "", re.I):
        found.append(re.sub(r"\s+", " ", m.group(0)).strip())
    return _uniq(found)

def _extract_location_candidates(text: str) -> list[str]:
    candidates = []
    pat = r"(?:Lokasi(?:\s+Kerja)?|Penempatan(?:\s+Kerja)?|Wilayah|Area|Domisili|Cabang)\s*[:.\-]?\s*([^\n,]{3,60})"
    for m in re.finditer(pat, text or "", re.I):
        loc = re.sub(r"\s+", " ", m.group(1)).strip(" .,;:-")
        if len(loc) >= 3 and not re.search(r"\b(gaji|syarat|kualifikasi|email|wa|hubungi)\b", loc, re.I):
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
    for m in re.finditer(r"(?:Nama\s+Perusahaan|Perusahaan|Instansi)\s*[:\-]\s*([^\n,]{3,60})", text or "", re.I):
        name = re.sub(r"\s+", " ", m.group(1)).strip().rstrip(".,;:")
        if len(name) >= 3 and not re.search(r"\b(membuka|lowongan|syarat|gaji)\b", name, re.I):
            results.append(name)
    return _uniq(results)

def _extract_addresses(text: str) -> list[str]:
    candidates = []
    street_pat = r"\b((?:Jl\.?|Jln\.?|Jalan|Gg\.?|Gang|Ruko|Komplek|Perumahan|Gedung|Tower)\s+[A-Za-z0-9\s.,/-]{5,100}?)(?=\s*(?:\n|Email|WA|WhatsApp|Hubungi|Gaji|Syarat|Kualifikasi|$))"
    for m in re.finditer(street_pat, text or "", re.I):
        addr = re.sub(r"\s+", " ", m.group(1)).strip(" .,;:-")
        if len(addr) >= 10:
            candidates.append(addr)
    label_pat = r"(?:Alamat(?:\s+Kantor)?|Lokasi(?:\s+Kerja)?)\s*[:.\-]\s*([^\n]{8,120})"
    for m in re.finditer(label_pat, text or "", re.I):
        addr = re.sub(r"\s+", " ", m.group(1)).strip(" .,;:-")
        if len(addr) >= 10 and not re.search(r"\b(gaji|syarat|kualifikasi|email|wa)\b", addr, re.I):
            candidates.append(addr)
    return [a for a in _uniq(candidates) if _is_plausible_address(a)]

def extract_entities_from_text(text: str) -> dict:
    raw_text = text or ""
    phone_pat = r"(?:\+62|62|0)\s*[1-9](?:[\s\-]?\d){6,12}"
    phones = [clean_indonesian_phone(p) for p in re.findall(phone_pat, raw_text)]
    phones = [p for p in _uniq(phones) if p]

    email_pat = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    emails = _uniq([fix_email_ocr_typos(e) for e in re.findall(email_pat, raw_text)])

    url_pat = r"https?://[^\s<>\"'{}|\\^`]+"
    urls = _uniq([u.rstrip(".,;:!?)]}") for u in re.findall(url_pat, raw_text)])

    companies = _extract_companies(raw_text)
    addresses = _extract_addresses(raw_text)
    salaries = _extract_salaries(raw_text)
    locations = _extract_location_candidates(raw_text)

    return {
        "companies": companies,
        "phones": phones,
        "emails": emails,
        "urls": urls,
        "addresses": addresses,
        "location_candidates": locations,
        "salaries": salaries,
        "extraction_meta": {
            "has_company": bool(companies),
            "has_phone": bool(phones),
            "has_email": bool(emails),
            "has_address": bool(addresses),
            "has_location_candidate": bool(locations),
            "has_salary": bool(salaries),
            "text_too_short": len(raw_text) < 50,
        },
        "fraud_fingerprint": {
            "template_similarity": None,
            "layout_fingerprint_match": None,
            "signature_hash": compute_content_sha256(raw_text)[:16]
        },
        "evidence_conflicts": []
    }
