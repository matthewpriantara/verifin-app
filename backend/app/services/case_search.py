"""Pencarian publik atas lowongan yang sudah pernah dianalisis.

Hanya ringkasan yang dikembalikan (nama perusahaan, verdict, skor, sumber, tanggal).
Teks mentah, nomor, dan email tidak pernah dikirim: teks lowongan bisa memuat
nomor orang yang tidak terkait penipuan.
"""

import re
from typing import Literal

from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from app.database.models import JobCase
from app.services.db_cache import _normalize_url_variants, _url_conditions

QueryKind = Literal["url", "phone", "email", "company"]

MIN_PHONE_DIGITS = 8
MIN_TEXT_CHARS = 3
VERDICTS = ("AMAN", "WASPADA", "BAHAYA")


def classify_query(q: str) -> QueryKind | None:
    """Tebak jenis kata kunci supaya kolom yang dicocokkan tepat."""
    q = q.strip()
    if not q:
        return None
    if re.match(r"^(https?://|www\.)", q, re.I):
        return "url"
    if "@" in q and " " not in q:
        return "email"
    digits = re.sub(r"\D", "", q)
    if re.fullmatch(r"[+\d\s().-]+", q) and len(digits) >= MIN_PHONE_DIGITS:
        return "phone"
    if len(q) >= MIN_TEXT_CHARS:
        return "company"
    return None


def like_escape(value: str) -> str:
    """Input pengguna di pola LIKE: % dan _ diperlakukan sebagai huruf biasa."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def canonical_phone(q: str) -> str:
    """Buang awalan 62/0 supaya 0812..., +62812..., dan 62812... cocok satu sama lain."""
    digits = re.sub(r"\D", "", q)
    if digits.startswith("62"):
        return digits[2:]
    if digits.startswith("0"):
        return digits[1:]
    return digits


def display_company(case: JobCase) -> str | None:
    llm = case.llm_output if isinstance(case.llm_output, dict) else {}
    corrected = llm.get("corrected_company_name")
    if isinstance(corrected, str) and corrected.strip():
        return corrected.strip()
    return case.company_name


def summarize(case: JobCase, matched_on: QueryKind | None) -> dict:
    return {
        "id": str(case.id),
        "company_name": display_company(case),
        "source": case.source,
        "verdict": case.verdict,
        "risk_score": case.risk_score,
        "osint_failed": bool(case.osint_failed),
        "matched_on": matched_on,
        "created_at": case.created_at.isoformat() if case.created_at else None,
    }


def search_cases(
    db: Session,
    q: str | None,
    verdict: str | None = None,
    limit: int = 20,
    skip: int = 0,
) -> dict:
    q = (q or "").strip()
    kind = classify_query(q) if q else None
    if q and kind is None:
        return {"query_kind": None, "total": 0, "cases": [], "too_short": True}

    query = db.query(JobCase).filter(JobCase.verdict.in_(VERDICTS))
    if verdict in VERDICTS:
        query = query.filter(JobCase.verdict == verdict)

    if kind == "url":
        variants = _normalize_url_variants(q if q.lower().startswith("http") else f"https://{q}")
        query = query.filter(or_(*_url_conditions(variants)))
    elif kind == "phone":
        query = query.filter(cast(JobCase.phones, String).like(f"%{like_escape(canonical_phone(q))}%", escape="\\"))
    elif kind == "email":
        query = query.filter(cast(JobCase.emails, String).ilike(f"%{like_escape(q.lower())}%", escape="\\"))
    elif kind == "company":
        like = f"%{like_escape(q.lower())}%"
        query = query.filter(
            or_(
                func.lower(JobCase.company_name).like(like, escape="\\"),
                func.lower(cast(JobCase.companies, String)).like(like, escape="\\"),
                func.lower(JobCase.llm_output["corrected_company_name"].astext).like(like, escape="\\"),
            )
        )

    total = query.count()
    rows = query.order_by(JobCase.created_at.desc()).offset(skip).limit(limit).all()
    return {
        "query_kind": kind,
        "total": total,
        "cases": [summarize(r, kind) for r in rows],
        "too_short": False,
    }
