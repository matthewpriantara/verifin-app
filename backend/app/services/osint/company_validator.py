"""
Validator reputasi perusahaan berbasis sumber publik — bukan cek registrasi AHU/OSS.

Fungsi utama: deteksi jejak penipuan di web untuk nama perusahaan dari poster lowongan.
Dipanggil dari pipeline.py setelah NER mengekstrak nama perusahaan.

Metodologi:
- TIDAK mengklaim "terdaftar di AHU/OSS" — API resmi butuh captcha/login, tidak tersedia.
- Yang dilakukan: cari jejak publik (website, hasil search, laporan penipuan di web).
- Output berupa risk_flags/safe_flags yang digabung di pipeline, bukan verdict final.

Sumber data:
1. Website dan search evidence yang sudah dikumpulkan oleh web_evidence.py
2. Tidak ada request jaringan yang dilakukan dari modul ini.
"""

import re
from typing import Any

from app.services.status_contract import COMPLETED
from app.services.osint.web_evidence import _result_matches_query

# Token umum yang tidak bermakna untuk deteksi nama perusahaan di blob search
_COMP_GENERIC_TOKENS = frozenset({
    "center", "management", "group", "utama", "persada", "pt", "cv",
    "badan", "nasional", "gizi", "sppg", "indonesia", "instansi", "dinas",
})

# Keyword yang menandakan artikel umum (bukan laporan penipuan spesifik)
_GENERAL_NEWS_KEYWORDS = frozenset({
    "aparat memburu", "satgas pasti", "cek fakta", "deretan hoaks",
    "siaran pers", "cara cek", "tips", "mengenali penipuan",
})


def validate_company_public(
    company: str,
    entities: dict | None = None,
    web_evidence: dict | None = None,
) -> dict[str, Any]:
    """
    Validasi publik untuk satu nama perusahaan.
    Semua field evidence berasal dari fetch/search nyata.
    """
    entities = entities or {}
    name = re.sub(r"\s+", " ", (company or "").strip())
    if not name or len(name) < 3:
        return {
            "name": company,
            "checked": False,
            "error": "Nama perusahaan kosong/terlalu pendek.",
            "evidence": [],
            "registry": {"pt_registry_verified": False},
            "risk_flags": [],
            "safe_flags": [],
        }

    risk_flags: list[str] = []
    safe_flags: list[str] = []

    # Web fetching/searching is owned by web_evidence.py. This module only
    # projects the already-fetched evidence into a company-level record.
    web_evidence = web_evidence if isinstance(web_evidence, dict) else {}
    websites = [
        w for w in (web_evidence.get("websites") or [])
        if isinstance(w, dict)
    ]
    searches = [
        s for s in (web_evidence.get("searches") or [])
        if isinstance(s, dict)
    ]
    for w in websites:
        risk_flags.extend(w.get("risk_flags") or [])
        safe_flags.extend(w.get("safe_flags") or [])

    # Search evidence is already filtered/normalized by web_evidence.py.
    mention_count = 0
    fraud_mentions = 0
    legality_mentions = 0
    successful_requests = 0
    for s in searches:
        if s.get("request_status") == COMPLETED:
            successful_requests += 1
        is_legality_query = any(
            token in s.get("query", "").lower()
            for token in ("nib", "akta pendirian", "terdaftar", "ahu", "oss")
        )
        comp_tokens = [
            t for t in re.split(r"\s+", name.lower())
            if len(t) > 3 and t not in {"pt", "cv", "ud", "tb", "firma"}
        ]
        # Token unik = comp_tokens minus kata geografis/industri generik Indonesia
        unique_tokens = [t for t in comp_tokens if t not in _COMP_GENERIC_TOKENS]

        for r in s.get("results") or []:
            blob = f"{r.get('title','')} {r.get('snippet','')}".lower()

            if not _result_matches_query(s.get("query", ""), r.get("url", ""), r.get("title", ""), r.get("snippet", "")):
                continue

            if unique_tokens:
                matched_unique = [tok for tok in unique_tokens if tok in blob]
                matched_all = [tok for tok in comp_tokens if tok in blob]
                has_comp = len(matched_unique) >= 1 and len(matched_all) >= 2
            else:
                matched_all = [tok for tok in comp_tokens if tok in blob]
                has_comp = len(matched_all) >= 2 or (name.lower() in blob)

            if has_comp:
                mention_count += 1

            has_scam_report = any(
                k in blob
                for k in (
                    "laporan penipuan",
                    "korban penipuan",
                    "loker palsu",
                    "penipu loker",
                    "scam loker",
                    "terbukti menipu",
                )
            )
            is_general_news_or_advice = any(kw in blob for kw in _GENERAL_NEWS_KEYWORDS)

            if has_comp and has_scam_report and not is_general_news_or_advice:
                fraud_mentions += 1

            # Deteksi jejak legalitas dari query kedua
            if is_legality_query and has_comp and any(
                kw in blob for kw in ("nib", "akta", "terdaftar", "ahu", "oss", "nomor induk")
            ):
                legality_mentions += 1

        risk_flags.extend(s.get("risk_flags") or [])

    if fraud_mentions >= 1:
        risk_flags.append(
            f"Pencarian web memuat {fraud_mentions} hasil indikasi penipuan spesifik terkait {name}."
        )
    elif mention_count >= 1:
        safe_flags.append(
            f"Ditemukan {mention_count} jejak publik di search (bukan klaim legalitas AHU)."
        )

    if legality_mentions >= 1:
        safe_flags.append(
            f"Ditemukan {legality_mentions} jejak legalitas (NIB/AHU/akta) di web publik untuk {name}."
        )
    # AHU probe di-skip (selalu unverified + lambat); legalitas tetap jujur
    registry = {
        "source": "ahu.go.id",
        "ok": False,
        "pt_registry_verified": False,
        "note": "Legalitas formal PT (AHU/OSS) tidak diotomasi; hanya jejak web publik.",
        "skipped": True,
    }

    # Dedup flags — dict.fromkeys preserves order
    def uniq(xs: list[str]) -> list[str]:
        return list(dict.fromkeys(x for x in xs if x))

    return {
        "name": name,
        "checked": True,
        "method": "public_web_only",
        "registry": {
            "pt_registry_verified": False,
            "portal": registry,
            "disclaimer": (
                "Legalitas formal PT (AHU/OSS) BELUM diverifikasi per-entitas. "
                "Hanya probe portal + jejak web publik."
            ),
        },
        "stats": {
            "search_count": len(searches),
            "public_mentions": mention_count,
            "fraud_related_mentions": fraud_mentions,
            "legality_mentions": legality_mentions,
            "successful_requests": successful_requests,
            "relevant_results": mention_count,
        },
        "neutral_notes": (
            ["Search engine tidak mengembalikan hasil yang dapat diverifikasi."]
            if successful_requests == 0 else (
                [f"Tidak ada hasil relevan untuk '{name}' pada request yang berhasil; ini bukan bukti ketiadaan jejak publik."]
                if mention_count == 0 else []
            )
        ),
        "risk_flags": uniq(risk_flags),
        "safe_flags": uniq(safe_flags),
    }


async def validate_companies(
    entities: dict,
    limit: int = 1,
    web_evidence: dict | None = None,
) -> list[dict[str, Any]]:
    companies = [c for c in (entities.get("companies") or []) if c][:limit]
    if not companies:
        return []

    out = []
    for name in companies:
        result = validate_company_public(name, entities, web_evidence)
        out.append(result)
    return out


# kompatibilitas nama lama
async def validate_company(name: str) -> dict:
    return validate_company_public(name, {})
