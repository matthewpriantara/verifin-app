"""
Ekstraksi entitas dari teks lowongan.
Utama: regex (ringan, tanpa torch).
Opsional: IndoBERT NER jika transformers terpasang.
"""

from __future__ import annotations

import re
import warnings

warnings.filterwarnings("ignore")

ner_pipeline = None
ner_lock = None

# Pemisah yang sering nempel setelah alamat
_ADDR_STOP = (
    r"(?:Gaji|GAJI|Salary|Upah|Kontak|Contact|Email|WA|WhatsApp|Hubungi|"
    r"Kirim|CV|Lamaran|Benefit|Syarat|Kualifikasi|Posisi|Lowongan|"
    r"Info|Informasi|NB|Catatan|Note|Transfer|Biaya|Deposit|Deskripsi|Pekerjaan|Ringkasan|Formulir)"
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
    # potong di kata gaji/kontak yang nempel
    a = re.split(rf"\s*[.,;]?\s*{_ADDR_STOP}\b", a, maxsplit=1, flags=re.I)[0]
    a = a.strip(" .,;:-")
    # buang trailing "Gaji 5-7 juta" sisa
    a = re.sub(
        r"\s+(?:Gaji|Salary|Upah)\s*[:.]?\s*.*$",
        "",
        a,
        flags=re.I,
    ).strip(" .,;:-")
    return a


def _extract_salaries(text: str) -> list[str]:
    patterns = [
        # Rp 5.000.000 - Rp 7.000.000 / Rp5jt
        r"(?:Rp\.?\s*)\d{1,3}(?:[.,]\d{3})+(?:\s*[-–]\s*(?:Rp\.?\s*)?\d{1,3}(?:[.,]\d{3})+)?(?:\s*/\s*(?:bulan|bln|month))?",
        r"(?:Rp\.?\s*)\d{1,3}(?:[.,]\d{1,3})?\s*(?:jt|juta|rb|ribu)(?:\s*[-–]\s*\d{1,3}(?:[.,]\d{1,3})?\s*(?:jt|juta|rb|ribu))?",
        # Gaji 5-7 juta / gaji: 5 sampai 7 juta
        r"(?:Gaji|Salary|Upah)\s*[:.]?\s*\d{1,3}(?:[.,]\d{3})*(?:\s*[-–]\s*\d{1,3}(?:[.,]\d{3})*)?\s*(?:jt|juta|rb|ribu)?",
        r"(?:Gaji|Salary|Upah)\s*[:.]?\s*\d{1,2}\s*[-–]\s*\d{1,2}\s*(?:jt|juta)",
        r"\b\d{1,2}\s*[-–]\s*\d{1,2}\s*(?:jt|juta)\b",
    ]
    found: list[str] = []
    for pat in patterns:
        for m in re.finditer(pat, text, flags=re.I):
            s = re.sub(r"\s+", " ", m.group(0)).strip(" .,;:")
            if s and s.lower() not in {x.lower() for x in found}:
                found.append(s)
    return found


def _extract_addresses(text: str) -> list[str]:
    # Label "Alamat: ..." / "Lokasi Kerja: ..."
    labeled = re.findall(
        rf"(?:Alamat|Lokasi Kerja|Lokasi|Bertempat di|Tempat)\s*[:.]?\s*"
        rf"([^\n]{{8,150}}?)"
        rf"(?=\s*(?:{_ADDR_STOP}|\n\n|$))",
        text,
        flags=re.I,
    )
    # Bare street address (Jl. / Jalan)
    bare = re.findall(
        rf"\b(?:Jl\.?|Jalan|Gg\.?|Gang)\s+[A-Za-z0-9\s.,/-]{{10,120}}?"
        rf"(?:\s*,?\s*(?:Yogyakarta|Jogja|Sleman|Bantul|Depok|Jakarta|Bandung|Surabaya|Semarang|Medan|DIY|Kota|[A-Z][a-z]+))"
        rf"(?=\s*(?:{_ADDR_STOP}|\n\n|$))",
        text,
        flags=re.I,
    )

    raw = list(labeled) + list(bare)
    cleaned = []
    for a in raw:
        c = _clean_address(a)
        if len(c) >= 10 and not re.match(r"^(Gaji|WA|Email|THP|Benefit|Deskripsi)\b", c, re.I):
            cleaned.append(c)
    return cleaned


def _get_ner_pipeline():
    global ner_pipeline, ner_lock
    if ner_pipeline is not None:
        return ner_pipeline
    try:
        import threading
        from transformers import pipeline

        if ner_lock is None:
            ner_lock = threading.Lock()
        model_name = "cahya/bert-base-indonesian-NER"
        print(f"[*] Memuat model IndoBERT NER ({model_name})...")
        ner_pipeline = pipeline("ner", model=model_name, aggregation_strategy="simple")
        return ner_pipeline
    except Exception as exc:
        print(f"[!] IndoBERT NER tidak tersedia, pakai regex saja: {exc}")
        ner_pipeline = False
        return None


def extract_entities_from_text(text: str) -> dict:
    normalized_text = re.sub(r"\bJI\b\.?\s+", "Jl. ", text)
    normalized_text = re.sub(r"\bJ\|\b\.?\s+", "Jl. ", normalized_text)
    normalized_text = normalize_phone_typos(normalized_text)

    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    url_pattern = r"(https?://[^\s]+|www\.[^\s]+|[a-zA-Z0-9-]+\.(?:com|id|co\.id|net|org|xyz|info))"
    phone_pattern = r"(?:\+62|62|0)[2-9](?:[\s\-]?\d){7,11}"

    company_pattern = (
        r"(?:PT|CV|UD)\.?\s+"
        r"([A-Z][A-Za-z0-9&'.-]+(?:\s+[A-Z][A-Za-z0-9&'.-]+){0,3})"
        r"(?=\s*(?:membuka|buka|sedang|mencari|butuh|butuhkan|lowongan|rekrut|hiring|untuk|di|yang|,|\.|$))"
    )

    emails = list(set(re.findall(email_pattern, normalized_text)))
    urls = list(set(re.findall(url_pattern, normalized_text)))
    email_domains = {email.split("@")[1] for email in emails if "@" in email}
    urls = [url for url in urls if url not in emails and url not in email_domains]

    phones = list(set(re.findall(phone_pattern, normalized_text)))
    standardized_phones = []
    for ph in phones:
        clean_ph = re.sub(r"\D", "", ph)
        if clean_ph.startswith("0"):
            clean_ph = "62" + clean_ph[1:]
        elif clean_ph.startswith("8"):
            clean_ph = "62" + clean_ph
        standardized_phones.append("+" + clean_ph)
    standardized_phones = list(set(standardized_phones))

    salaries = _extract_salaries(normalized_text)
    extracted_addresses = _extract_addresses(normalized_text)

    companies = []
    for m in re.finditer(company_pattern, normalized_text):
        name = m.group(0).strip().rstrip(".,")
        if m.lastindex:
            core = m.group(1).strip().rstrip(".,")
            prefix = re.match(r"(?:PT|CV|UD)\.?", m.group(0), re.I)
            name = f"{prefix.group(0)} {core}".replace("  ", " ") if prefix else core
        if re.search(r"\b(ke|hrd|membuka|lowongan)\b", name, re.I):
            continue
        if len(name) >= 5:
            companies.append(name)

    nlp = _get_ner_pipeline()
    if nlp:
        try:
            import threading

            words_list = normalized_text.split()
            if len(words_list) > 300:
                chunks = []
                i = 0
                while i < len(words_list):
                    chunks.append(" ".join(words_list[i : i + 300]))
                    i += 250
            else:
                chunks = [normalized_text]

            lock = ner_lock or threading.Lock()
            with lock:
                for chunk in chunks:
                    for entity in nlp(chunk):
                        word = entity["word"].strip().replace("##", "")
                        if len(word) <= 2:
                            continue
                        if any(x in word for x in ("www", ".com", "http", "@")):
                            continue
                        if entity.get("entity_group") == "ORG":
                            companies.append(word.title())
                        if entity.get("entity_group") == "LOC" and len(word) > 3:
                            cleaned = _clean_address(word)
                            if cleaned:
                                extracted_addresses.append(cleaned)
        except Exception as exc:
            print(f"[!] NER BERT gagal, lanjut regex: {exc}")

    def uniq(items: list[str]) -> list[str]:
        seen = set()
        out = []
        for item in items:
            key = item.lower().strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(item.strip())
        return out

    return {
        "companies": uniq(companies),
        "contacts": uniq(standardized_phones),
        "emails": uniq(emails),
        "urls": uniq(urls),
        "addresses": uniq(extracted_addresses),
        "salaries": uniq(salaries),
    }
