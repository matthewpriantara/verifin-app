"""Tahap "Memeriksa isi": berhenti sebelum OSINT bila input tidak bisa dinilai sebagai satu lowongan.

Intervensi: I-01 bukan lowongan, I-03 teks terlalu sedikit, I-04 lebih dari satu lowongan (dipotong
per pemberi kerja); catatan tanpa berhenti untuk teks lain di luar lowongan dan kontak yang hanya
terbaca AI. Pemicunya uji tepi 27 Okt 2026: tiga loker asli yang digabung setelah loker palsu
dengan nomor yang sama dinilai BAHAYA 75 karena graf penipuan ikut tercemar. Keputusan
memakai dua sumber: aturan kata kunci (`check_content_safety_and_type`) dan klasifikasi dari
panggilan ekstraksi entitas LLM (`entities["_content"]`), jadi tidak ada panggilan AI tambahan.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.ner import count_distinct_employers, extract_entities_from_text, is_multi_employer
from app.services.nlp.classifier import check_content_safety_and_type

VISION_MARKER = "[PEMBACAAN AI DARI GAMBAR]"

# Intervensi I-12: data pribadi yang tidak perlu dikirim ke AI.
_NIK_PATTERN = re.compile(r"(?<!\d)\d{16}(?!\d)")
_ACCOUNT_PATTERNS = (
    re.compile(r"\b(?:rekening|norek|no\.?\s*rek|transfer|setor)\b[^\n]{0,20}(?<!\d)\d{8,16}(?!\d)", re.I),
    re.compile(r"(?<!\d)\d{8,16}(?!\d)(?=[^.\n]{0,30}\b(?:rekening|norek|rek\b|transfer|setor))", re.I),
)
_KTP_WORDS = re.compile(r"\b(?:ktp|e-?ktp|nik|foto\s*ktp|scan\s*ktp)\b", re.I)

# Intervensi I-13: deteksi kasar bahasa Inggris dari kata fungsi, tanpa model tambahan.
_ID_STOPWORDS = {
    "dan", "yang", "untuk", "dengan", "dari", "kami", "anda", "tidak", "akan", "atau",
    "juga", "pada", "dalam", "adalah", "bisa", "harus", "bagi", "serta", "kepada",
}
_EN_STOPWORDS = {
    "the", "and", "for", "with", "from", "you", "are", "will", "not", "our", "this",
    "that", "have", "has", "must", "should", "able", "please", "applicants", "requirements",
}


def split_non_job(text: str, spans: list[dict]) -> tuple[str, list[str]]:
    """Buang potongan teks di luar lowongan (intervensi I-05) memakai kutipan persis dari LLM.

    Pengembalian: (teks lowongan saja, potongan yang dibuang). Bila hasil potongan terlalu pendek,
    pemotongan dibatalkan supaya lowongan tidak ikut hilang."""
    kept = text or ""
    removed: list[str] = []
    for span in spans or []:
        chunk = re.sub(r"\s+", " ", str((span or {}).get("text") or "")).strip()
        if len(chunk) < 20:
            continue
        idx = kept.lower().find(chunk.lower())
        if idx < 0:
            continue
        removed.append(kept[idx:idx + len(chunk)])
        kept = (kept[:idx] + "\n" + kept[idx + len(chunk):]).strip()
    if not removed or len(kept) < max(40, int(len(text) * 0.25)):
        return text, []
    return kept, removed


def apply_non_job_filter(entities: dict, kept_text: str, removed: list[str]) -> int:
    """Hapus entitas yang hanya muncul di potongan non-lowongan, supaya nomor/nama dari berita
    atau promo lain tidak ikut diperiksa ke sumber publik. Kembalikan jumlah entitas yang dibuang."""
    if not removed:
        return 0
    kept_low = (kept_text or "").lower()
    removed_low = " ".join(removed).lower()
    dropped = 0
    for key in ("companies", "phones", "emails", "urls", "addresses", "location_candidates", "salaries"):
        values = entities.get(key)
        if not isinstance(values, list):
            continue
        kept_values = []
        for value in values:
            text = str(value).lower()
            if text and text not in kept_low and text in removed_low:
                dropped += 1
                continue
            kept_values.append(value)
        entities[key] = kept_values
    return dropped


def detect_personal_data(text: str) -> list[str]:
    """Intervensi I-12: sebut jenis data pribadi yang ditemukan, tanpa menyalin nilainya."""
    found: list[str] = []
    if _KTP_WORDS.search(text or "") and (_NIK_PATTERN.search(text or "") or _KTP_WORDS.search(text or "")):
        found.append("NIK/KTP")
    if _NIK_PATTERN.search(text or "") and "NIK/KTP" not in found:
        found.append("NIK")
    if any(pattern.search(text or "") for pattern in _ACCOUNT_PATTERNS):
        found.append("nomor rekening")
    return found


def detect_language_note(text: str) -> str | None:
    """Intervensi I-13: catatan bila teks lowongan berbahasa Inggris."""
    words = re.findall(r"[a-zA-Z]+", (text or "").lower())
    if len(words) < 30:
        return None
    id_hits = sum(1 for w in words if w in _ID_STOPWORDS)
    en_hits = sum(1 for w in words if w in _EN_STOPWORDS)
    if en_hits >= 5 and en_hits > id_hits * 1.5:
        return (
            "Lowongan berbahasa Inggris. Pemeriksaan tetap berjalan, tetapi pencarian lokal "
            "(berita, forum, akun Indonesia) mungkin kurang lengkap."
        )
    return None



def _mask_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("62"):
        digits = "0" + digits[2:]
    if len(digits) < 8:
        return phone
    return f"{digits[:4]}-xxxx-{digits[-4:]}"


def _find_anchor(text: str, phrase: str, start: int = 0) -> int:
    words = re.findall(r"\w+", phrase or "")
    if len(words) < 2:
        return -1
    pattern = r"\W+".join(re.escape(w) for w in words[:8])
    match = re.compile(pattern, re.I).search(text, start)
    return match.start() if match else -1


def split_postings(text: str, postings: list[dict]) -> list[dict]:
    """Potong teks per lowongan memakai kata pembuka tiap lowongan (dari LLM), atau nama pemberi
    kerja bila kata pembuka tidak ditemukan. Lowongan yang posisinya tidak ketemu tetap tampil
    sebagai kartu, tetapi tanpa teks sehingga tidak bisa dipilih."""
    located = []
    for p in postings:
        pos = _find_anchor(text, p.get("first_words", ""))
        if pos < 0:
            m = re.search(re.escape(p.get("employer", "")), text, re.I) if p.get("employer") else None
            pos = m.start() if m else -1
        located.append((pos, p))

    starts = sorted({pos for pos, _ in located if pos >= 0})
    segments = []
    for i, (pos, p) in enumerate(located):
        seg_text = None
        if pos >= 0:
            nxt = next((s for s in starts if s > pos), len(text))
            chunk = text[pos:nxt].strip()
            if len(chunk) >= 40:
                seg_text = chunk
        contacts: list[str] = []
        if seg_text:
            found = extract_entities_from_text(seg_text)
            contacts = [_mask_phone(x) for x in (found.get("phones") or [])[:2]] + (found.get("emails") or [])[:2]
        segments.append({
            "id": i,
            "employer": p.get("employer", ""),
            "position": p.get("position", ""),
            "contacts": contacts,
            "text": seg_text,
        })
    return segments


def assess_input(text: str, entities: dict) -> dict[str, Any]:
    """Kembalikan {"issue": dict|None, "notes": [str], "not_job": bool}.

    `issue` terisi bila proses harus berhenti dan bertanya ke pengguna."""
    analysed = (text or "").split(VISION_MARKER)[0]
    rule = check_content_safety_and_type(analysed, entities.get("companies"))
    llm = entities.get("_content") or {}
    llm_job = llm.get("is_job_posting")
    notes: list[str] = []

    strong_rule_job = rule.get("is_job_posting") and rule.get("job_signal_count", 0) >= 3
    if llm_job is False:
        not_job = not strong_rule_job
    elif llm_job is True:
        not_job = False
    else:
        not_job = not rule.get("is_job_posting") and rule.get("confidence") == "tinggi"

    if not_job:
        return {
            "not_job": True,
            "notes": notes,
            "issue": {
                "id": "I-01",
                "kind": "not_job",
                "title": "Ini sepertinya bukan lowongan kerja.",
                "message": "Tidak ditemukan posisi, cara melamar, atau pemberi kerja. Verifin hanya bisa menilai lowongan kerja.",
                "can_force": True,
            },
        }

    if rule.get("text_too_short"):
        return {
            "not_job": False,
            "notes": notes,
            "issue": {
                "id": "I-03",
                "kind": "too_short",
                "title": "Informasinya terlalu sedikit untuk diperiksa.",
                "message": "Tambahkan nama perusahaan, posisi, atau cara melamar bila ada. Tanpa itu, hampir tidak ada yang bisa dicek ke sumber publik.",
                "can_force": True,
            },
        }

    postings = llm.get("postings") or []
    employers = [p["employer"] for p in postings if p.get("employer")]
    if count_distinct_employers(employers) >= 2:
        segments = split_postings(analysed, postings)
        contact_sets = {tuple(s["contacts"]) for s in segments if s["contacts"]}
        if is_multi_employer(entities) or len(contact_sets) >= 2:
            return {
                "not_job": False,
                "notes": notes,
                "issue": {
                    "id": "I-04",
                    "kind": "multi_job",
                    "title": f"Kami menemukan {len(segments)} lowongan berbeda.",
                    "message": "Satu pemeriksaan untuk satu lowongan, supaya bukti dari lowongan lain tidak ikut menilai.",
                    "can_force": True,
                    "segments": segments,
                },
            }

    non_job = llm.get("non_job_content") or ""
    if "PEMBACAAN AI" in non_job.upper():
        non_job = ""
    job_text = None
    removed: list[str] = []
    spans = llm.get("non_job_spans") or []
    if isinstance(spans, list) and spans:
        job_text, removed = split_non_job(text, [s for s in spans if isinstance(s, dict)])
    if removed:
        notes.append(
            f"Ada teks di luar lowongan ({non_job or 'teks lain'}); {len(removed)} potongan itu tidak ikut "
            "diperiksa supaya nama/nomor di dalamnya tidak mencemari hasil."
        )
    elif non_job or rule.get("has_mixed_content"):
        kind = non_job or "teks lain"
        notes.append(f"Ada teks di luar lowongan ({kind}). Bagian itu ikut terbaca; abaikan bila tidak relevan.")
    personal = detect_personal_data(text)
    if personal:
        notes.append(
            f"Input memuat data pribadi ({', '.join(personal)}). Data itu disamarkan sebelum dikirim ke AI "
            "dan tidak disimpan di cuplikan teks."
        )
    language_note = detect_language_note(analysed)
    if language_note:
        notes.append(language_note)
    ai_only = (entities.get("_ner_meta") or {}).get("ai_only_contacts") or []
    if ai_only:
        notes.append(
            "Kontak berikut hanya terbaca oleh AI, tidak oleh OCR, sehingga tidak ikut dicek: "
            + ", ".join(ai_only[:4])
            + ". Cocokkan sendiri dengan poster."
        )
    return {"not_job": False, "notes": notes, "issue": None, "job_text": job_text, "removed": removed}


def apply_forced(entities: dict, issue_kind: str | None) -> None:
    """Pengguna memilih "Tetap periksa": hasil tetap keluar, tetapi kasus dikecualikan dari graf
    penipuan dan pencarian publik supaya tidak mencemari bukti kasus lain."""
    entities["input_quality"] = "forced"
    entities["is_mixed_input"] = True
    if issue_kind == "not_job":
        entities["not_a_job_posting"] = True
