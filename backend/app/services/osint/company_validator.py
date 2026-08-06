"""
Validasi nama PT/perusahaan — HANYA dari sumber publik yang benar-benar di-fetch.

PENTING (metodologi Verifin):
- Kita TIDAK mengklaim "terdaftar di AHU/OSS" kecuali ada bukti fetch nyata.
- AHU/OSS resmi sering butuh captcha/login; tanpa API resmi, status = unverified.
- Yang kita lakukan: jejak publik (website, hasil search, sebutan NIB/AHU di web).

Sumber yang dipakai:
1) Fetch website domain (jika ada di entities/email)
2) DuckDuckGo search fakta: nama PT + (AHU|OSS|NIB|lowongan penipuan)
3) Scrapling — data mentah disimpan di results (URL + title + snippet)
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus

from scrapling.fetchers import Fetcher

from app.services.osint.web_evidence import (
    fetch_company_website,
    search_web_evidence,
    _domain_from_email,
)


def _normalize_company_name(name: str) -> str:
    n = re.sub(r"\s+", " ", (name or "").strip())
    return n


_FREE_EMAIL_DOMAINS = {
    "gmail.com",
    "yahoo.com",
    "yahoo.co.id",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "ymail.com",
    "icloud.com",
    "protonmail.com",
    "mail.com",
}


def _search_company_traces(company: str, location: str | None = None) -> list[dict[str, Any]]:
    """1 query scam check saja (web_evidence sudah cover presence search)."""
    norm_comp = company.strip()
    if len(norm_comp) <= 6 and location:
        queries = [f'"{norm_comp}" "{location}" lowongan OR profil OR penipuan OR penipu OR scam']
    else:
        queries = [f'"{norm_comp}" lowongan penipuan OR penipu OR scam']
    out = []
    for q in queries:
        res = search_web_evidence(q, max_results=3)
        out.append(
            {
                "query": q,
                "ok": res.get("ok"),
                "source": "duckduckgo_html",
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
    name = _normalize_company_name(company)
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

    # Extract location context if available in entities
    location_ctx = None
    addrs = entities.get("addresses") or []
    if addrs and isinstance(addrs, list):
        # Pick city/location token from address if available
        first_addr = str(addrs[0])
        # Simple extraction of last parts or city names if present
        location_parts = [p.strip() for p in first_addr.split(",") if p.strip()]
        if location_parts:
            location_ctx = location_parts[-1] if len(location_parts) == 1 else location_parts[-2]
    elif isinstance(entities.get("location"), str):
        location_ctx = entities["location"]

    # 2) 1 search scam (presence search sudah di web_evidence)
    searches = _search_company_traces(name, location=location_ctx)
    mention_count = 0
    fraud_mentions = 0
    for s in searches:
        evidence.append(
            {
                "type": "web_search",
                "source": "duckduckgo_html",
                "query": s.get("query"),
                "search_url": s.get("search_url"),
                "ok": s.get("ok"),
                "results": s.get("results") or [],
                "error": s.get("error"),
            }
        )
        comp_tokens = [
            t
            for t in re.split(r"\s+", name.lower())
            if len(t) > 3 and t not in ("center", "management", "group", "utama", "persada", "pt", "cv")
        ]
        unique_tokens = [
            t
            for t in comp_tokens
            if t not in ("badan", "nasional", "gizi", "sppg", "indonesia", "instansi", "dinas")
        ]

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
            is_general_news_or_advice = any(
                n in blob
                for n in (
                    "aparat memburu",
                    "satgas pasti",
                    "cek fakta",
                    "deretan hoaks",
                    "siaran pers",
                    "cara cek",
                    "tips",
                    "mengenali penipuan",
                )
            )

            if has_comp and has_scam_report and not is_general_news_or_advice:
                fraud_mentions += 1
        risk_flags.extend(s.get("risk_flags") or [])

    if fraud_mentions >= 1:
        risk_flags.append(
            f"Pencarian web memuat {fraud_mentions} hasil indikasi penipuan spesifik terkait {name}."
        )
    elif mention_count >= 1:
        safe_flags.append(
            f"Ditemukan {mention_count} jejak publik di search (bukan klaim legalitas AHU)."
        )

    # AHU probe di-skip (selalu unverified + lambat); legalitas tetap jujur
    registry = {
        "source": "ahu.go.id",
        "ok": False,
        "pt_registry_verified": False,
        "note": "Legalitas formal PT (AHU/OSS) tidak diotomasi; hanya jejak web publik.",
        "skipped": True,
    }

    # Dedup flags
    def uniq(xs: list[str]) -> list[str]:
        seen = set()
        out = []
        for x in xs:
            if not x or x in seen:
                continue
            seen.add(x)
            out.append(x)
        return out

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
        },
        "risk_flags": uniq(risk_flags),
        "safe_flags": uniq(safe_flags),
    }


async def validate_companies(entities: dict, limit: int = 1) -> list[dict[str, Any]]:
    import asyncio

    companies = [c for c in (entities.get("companies") or []) if c][:limit]
    if not companies:
        return []

    loop = asyncio.get_event_loop()
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
