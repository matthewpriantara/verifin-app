"""Domain resmi pemberi kerja dari hasil pencarian, tanpa daftar merek (audit-007 10.7 B).

Poster palsu tidak pernah mencantumkan situs resmi merek yang dicatutnya, jadi domain resmi dicari
dari hasil pencarian nama perusahaan. Kandidat dinilai dengan fitur umum:
- token nama di label host atau judul hasil,
- peringkat (3 teratas),
- lebih dari satu hasil dari host yang sama,
- kecocokan negara bila nama perusahaan memuat "Indonesia",
- umur domain minimal satu tahun (hanya untuk kandidat teratas, satu panggilan WHOIS/RDAP).

Situs pihak ketiga (media sosial, marketplace, portal loker, direktori, berita) disaring lewat
`site_kinds`, bukan daftar di modul ini.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Callable

from app.services import site_kinds

# Kata yang tidak membedakan satu merek dari yang lain. Ini kosakata bahasa, bukan daftar merek.
_GENERIC_WORDS = {
    "pt", "cv", "ud", "tbk", "persero", "indonesia", "group", "grup", "hotel", "resto", "toko",
    "official", "store", "ritel", "retail", "electronics", "electronic", "distribusi", "global",
    "jaya", "abadi", "mandiri", "sejahtera", "nusantara", "the", "and", "dan", "yogyakarta", "jogja",
    "media", "digital", "sinar", "mitra", "karya", "utama", "makmur", "sentosa", "indo", "company",
}
MIN_SCORE = 3
MIN_AGE_DAYS = 365


def brand_tokens(companies: list) -> set[str]:
    tokens: set[str] = set()
    for name in companies or []:
        for word in re.findall(r"[a-z0-9]+", str(name).lower()):
            if len(word) >= 4 and word not in _GENERIC_WORDS:
                tokens.add(word)
    return tokens


def _wants_indonesia(companies: list) -> bool:
    return any("indonesia" in str(c).lower() for c in companies or [])


def score_candidates(companies: list, searches: list) -> list[dict[str, Any]]:
    """Skor setiap host non-pihak-ketiga di hasil pencarian. Tanpa panggilan jaringan."""
    tokens = brand_tokens(companies)
    if not tokens:
        return []
    want_id = _wants_indonesia(companies)
    stats: dict[str, dict[str, Any]] = defaultdict(lambda: {"hits": 0, "best_rank": 99, "titles": []})
    for search in searches or []:
        for rank, item in enumerate((search or {}).get("results") or []):
            host = site_kinds.normalize_host(str(item.get("url") or ""))
            if not host or site_kinds.is_third_party(host):
                continue
            entry = stats[host]
            entry["hits"] += 1
            entry["best_rank"] = min(entry["best_rank"], rank)
            entry["titles"].append(f"{item.get('title') or ''} {item.get('snippet') or ''}".lower())

    scored = []
    for host, entry in stats.items():
        labels = host.split(".")
        in_host = any(t in label for t in tokens for label in labels)
        text = " ".join(entry["titles"])
        in_title = any(re.search(rf"\b{re.escape(t)}\b", text) for t in tokens)
        if not (in_host or in_title):
            continue
        if want_id and not (host.endswith(".id") or labels[0] == "id" or "indonesia" in text or "indonesia" in host):
            continue
        # Domain registri nasional negara lain (com.au, co.uk, com.sg) bukan milik pemberi kerja di
        # lowongan Indonesia, walau namanya sama (Trinity Success Group Australia vs PT Trinity).
        if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-1] != "id" and len(labels[-2]) <= 3:
            continue
        score = (2 if in_host else 0) + (1 if in_title else 0)
        score += 1 if entry["best_rank"] < 3 else 0
        score += 1 if entry["hits"] >= 2 else 0
        if score >= MIN_SCORE:
            scored.append({"domain": host, "score": score, "rank": entry["best_rank"]})
    scored.sort(key=lambda c: (-c["score"], c["rank"]))
    return scored


def find_official_domains(
    companies: list,
    searches: list,
    age_lookup: Callable[[str], dict] | None = None,
) -> list[dict[str, Any]]:
    """Kandidat lolos skor; kandidat teratas juga harus berumur ≥ 1 tahun bila umurnya diketahui.

    `age_lookup` dipanggil paling banyak sekali. Umur tidak diketahui tidak menggugurkan kandidat,
    karena banyak TLD (mis. `.sharp`) tidak menjawab WHOIS/RDAP.
    """
    candidates = score_candidates(companies, searches)[:3]
    if not candidates or age_lookup is None:
        return candidates
    top = candidates[0]
    try:
        age = age_lookup(top["domain"]) or {}
    except Exception:
        age = {}
    age_days = age.get("age_days")
    top["age_days"] = age_days if isinstance(age_days, int) and age_days >= 0 else None
    if top["age_days"] is not None and top["age_days"] < MIN_AGE_DAYS:
        return candidates[1:]
    return candidates
