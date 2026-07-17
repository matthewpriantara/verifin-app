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


def _search_company_traces(company: str) -> list[dict[str, Any]]:
    """Beberapa query search nyata; hasil = URL yang benar-benar muncul di SERP."""
    queries = [
        f'"{company}"',
        f'"{company}" AHU OR OSS OR NIB',
        f'"{company}" lowongan penipuan OR penipu',
        f'"{company}" site:jobstreet.co.id OR site:linkedin.com OR site:glints.com',
    ]
    out = []
    for q in queries:
        res = search_web_evidence(q, max_results=4)
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


def _probe_ahu_landing() -> dict[str, Any]:
    """
    Cek ketersediaan portal AHU (bukan klaim PT terdaftar).
    Hanya: apakah situs AHU merespons.
    """
    url = "https://ahu.go.id/pencarian/profil-pt"
    try:
        page = Fetcher.get(url, stealthy_headers=True)
        status = getattr(page, "status", None) or getattr(page, "status_code", None)
        title = ""
        try:
            title = (page.css("title::text").get() or "").strip()
        except Exception:
            pass
        return {
            "source": "ahu.go.id",
            "url": url,
            "ok": status is None or int(status) < 400,
            "status": status,
            "title": title[:160],
            "note": (
                "Portal AHU dapat diakses, tetapi pencarian profil PT resmi "
                "belum diotomasi (sering butuh captcha/sesi). "
                "Status legalitas PT individual = BELUM TERVERIFIKASI lewat API AHU."
            ),
            "pt_registry_verified": False,
        }
    except Exception as exc:
        return {
            "source": "ahu.go.id",
            "url": url,
            "ok": False,
            "error": str(exc),
            "pt_registry_verified": False,
            "note": "Gagal menghubungi portal AHU; legalitas PT tidak diverifikasi.",
        }


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

    # 1) Website dari domain email / urls
    domains = []
    for em in (entities.get("emails") or [])[:2]:
        d = _domain_from_email(em)
        if d:
            domains.append(d)
    for u in (entities.get("urls") or [])[:2]:
        if u:
            domains.append(u)

    websites = []
    for d in list(dict.fromkeys(domains))[:2]:
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
        if w.get("ok") is False:
            risk_flags.append(f"Website terkait tidak dapat diakses: {w.get('url')}")

    # 2) Search jejak publik
    searches = _search_company_traces(name)
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
        for r in s.get("results") or []:
            mention_count += 1
            blob = f"{r.get('title','')} {r.get('snippet','')}".lower()
            if any(k in blob for k in ("penipu", "penipuan", "scam", "berkedok", "waspada tipu")):
                fraud_mentions += 1
        risk_flags.extend(s.get("risk_flags") or [])

    if fraud_mentions >= 1:
        risk_flags.append(
            f"Pencarian web memuat {fraud_mentions} hasil dengan indikasi penipuan terkait nama PT "
            f"(lihat evidence URL)."
        )
    if mention_count == 0:
        risk_flags.append(
            "Tidak ditemukan jejak publik yang jelas untuk nama PT di hasil pencarian terbatas."
        )
    elif mention_count >= 3 and fraud_mentions == 0:
        safe_flags.append(
            f"Ditemukan {mention_count} jejak publik di search (bukan klaim legalitas AHU)."
        )

    # 3) Portal AHU availability (bukan status registrasi PT)
    registry = _probe_ahu_landing()
    evidence.append(
        {
            "type": "registry_portal_probe",
            "source": "ahu.go.id",
            "url": registry.get("url"),
            "ok": registry.get("ok"),
            "title": registry.get("title"),
            "note": registry.get("note"),
            "pt_registry_verified": False,
        }
    )

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
