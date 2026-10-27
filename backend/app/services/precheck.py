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
    if non_job or rule.get("has_mixed_content"):
        kind = non_job or "teks lain"
        notes.append(f"Ada teks di luar lowongan ({kind}). Bagian itu ikut terbaca; abaikan bila tidak relevan.")
    ai_only = (entities.get("_ner_meta") or {}).get("ai_only_contacts") or []
    if ai_only:
        notes.append(
            "Kontak berikut hanya terbaca oleh AI, tidak oleh OCR, sehingga tidak ikut dicek: "
            + ", ".join(ai_only[:4])
            + ". Cocokkan sendiri dengan poster."
        )
    return {"not_job": False, "notes": notes, "issue": None}


def apply_forced(entities: dict, issue_kind: str | None) -> None:
    """Pengguna memilih "Tetap periksa": hasil tetap keluar, tetapi kasus dikecualikan dari graf
    penipuan dan pencarian publik supaya tidak mencemari bukti kasus lain."""
    entities["input_quality"] = "forced"
    entities["is_mixed_input"] = True
    if issue_kind == "not_job":
        entities["not_a_job_posting"] = True
