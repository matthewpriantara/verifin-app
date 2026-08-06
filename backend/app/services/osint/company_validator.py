"""
Validator reputasi perusahaan berbasis sumber publik — bukan cek registrasi AHU/OSS.

Fungsi utama: deteksi jejak penipuan di web untuk nama perusahaan dari poster lowongan.
Dipanggil dari pipeline.py setelah NER mengekstrak nama perusahaan.

Metodologi:
- TIDAK mengklaim "terdaftar di AHU/OSS" — API resmi butuh captcha/login, tidak tersedia.
- Yang dilakukan: cari jejak publik (website, hasil search, laporan penipuan di web).
- Output berupa risk_flags/safe_flags yang digabung di pipeline, bukan verdict final.

Sumber data:
1. Website domain perusahaan (dari email di entities) — cek konten nyata
2. Web search: nama PT + kata kunci penipuan (DuckDuckGo → Yahoo → Bing fallback)
"""

import re
from typing import Any

from app.services.constants import FREE_EMAIL_DOMAINS as _FREE_EMAIL_DOMAINS
from app.services.osint.web_evidence import (
    _domain_from_email,
    fetch_company_website,
    search_web_evidence,
)

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


def _search_company_traces(company: str) -> list[dict[str, Any]]:
    """Dua query: scam check + jejak legalitas (NIB/AHU/akta via web publik)."""
    queries = [
        f'"{company}" lowongan penipuan OR penipu OR scam',
        f'"{company}" NIB OR "akta pendirian" OR "terdaftar" OR AHU OR OSS',
    ]
    out = []
    for q in queries:
        res = search_web_evidence(q, max_results=3)
        out.append(
            {
                "query": q,
                "ok": res.get("ok"),
                "source": res.get("engine", "searxng"),
                "search_url": res.get("url"),
                "results": res.get("results") or [],
                "error": res.get("error"),
                "risk_flags": res.get("risk_flags") or [],
            }
        )
    return out


def validate_company_public(company: str, entities: dict | None = None) -> dict[str, Any]:
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

    evidence: list[dict[str, Any]] = []
    risk_flags: list[str] = []
    safe_flags: list[str] = []

    # 1) Website hanya domain korporat (skip Gmail dll) — max 1
    domains = []
    for em in (entities.get("emails") or [])[:1]:
        d = _domain_from_email(em)
        if d and d not in _FREE_EMAIL_DOMAINS:
            domains.append(d)
    for u in (entities.get("urls") or [])[:1]:
        if u:
            domains.append(u)

    websites = []
    for d in list(dict.fromkeys(domains))[:1]:
        w = fetch_company_website(d)
        websites.append(w)
        evidence.append(
            {
                "type": "website_fetch",
                "source": "scrapling",
                "url": w.get("url"),
                "ok": w.get("ok"),
                "title": w.get("title"),
                "snippet": (w.get("snippet") or "")[:240],
                "raw_status": w.get("status"),
                "error": w.get("error"),
            }
        )
        risk_flags.extend(w.get("risk_flags") or [])
        safe_flags.extend(w.get("safe_flags") or [])

    # 2) search scam + jejak legalitas
    searches = _search_company_traces(name)
    mention_count = 0
    fraud_mentions = 0
    legality_mentions = 0
    for s in searches:
        is_legality_query = "NIB" in s.get("query", "") or "akta pendirian" in s.get("query", "")
        evidence.append(
            {
                "type": "web_search",
                "source": s.get("source", "searxng"),
                "query": s.get("query"),
                "search_url": s.get("search_url"),
                "ok": s.get("ok"),
                "results": s.get("results") or [],
                "error": s.get("error"),
            }
        )
        comp_tokens = [
            t for t in re.split(r"\s+", name.lower())
            if len(t) > 3 and t not in {"pt", "cv", "ud", "tb", "firma"}
        ]
        # Token unik = comp_tokens minus kata geografis/industri generik Indonesia
        unique_tokens = [t for t in comp_tokens if t not in _COMP_GENERIC_TOKENS]

        for r in s.get("results") or []:
            mention_count += 1
            blob = f"{r.get('title','')} {r.get('snippet','')}".lower()

            if unique_tokens:
                matched_unique = [tok for tok in unique_tokens if tok in blob]
                matched_all = [tok for tok in comp_tokens if tok in blob]
                has_comp = len(matched_unique) >= 1 and len(matched_all) >= 2
            else:
                matched_all = [tok for tok in comp_tokens if tok in blob]
                has_comp = len(matched_all) >= 2 or (name.lower() in blob)

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
    elif mention_count == 0:
        risk_flags.append(
            f"Tidak ditemukan jejak publik maupun legalitas untuk '{name}' — perusahaan baru atau fiktif."
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
        "websites": websites,
        "searches": searches,
        "evidence": evidence,
        "stats": {
            "public_mentions": mention_count,
            "fraud_related_mentions": fraud_mentions,
            "legality_mentions": legality_mentions,
        },
        "risk_flags": uniq(risk_flags),
        "safe_flags": uniq(safe_flags),
    }


async def validate_companies(entities: dict, limit: int = 1) -> list[dict[str, Any]]:
    import asyncio

    companies = [c for c in (entities.get("companies") or []) if c][:limit]
    if not companies:
        return []

    loop = asyncio.get_running_loop()
    out = []
    for name in companies:
        result = await loop.run_in_executor(
            None, validate_company_public, name, entities
        )
        out.append(result)
    return out


# kompatibilitas nama lama
async def validate_company(name: str) -> dict:
    return validate_company_public(name, {})
