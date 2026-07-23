"""
Community Reports Router — laporan penipuan dari komunitas (Layer 5 suplemen).

Pengguna dapat melaporkan lowongan/entitas yang terbukti menipu. Agregasi
laporan lintas entitas (HP/email/PT/URL) memperkuat Fraud Network: entitas
yang berulang dilaporkan menjadi sinyal risiko kuat.

Endpoint:
- POST /community/report          → kirim laporan baru
- GET  /community/check           → cek berapa kali entitas dilaporkan (agregasi)
- GET  /community/recent          → laporan terbaru (untuk transparansi publik)
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database.models import CommunityReport
from app.database.postgres_client import Base, engine, get_db

logger = logging.getLogger(__name__)
router = APIRouter()

# Buat tabel bila belum ada (aman: checkfirst=True, tidak menimpa yang ada).
try:
    Base.metadata.create_all(bind=engine, tables=[CommunityReport.__table__], checkfirst=True)
except Exception as exc:  # noqa: BLE001 — jangan gagalkan boot bila DB sesaat down
    logger.warning("[community] create_all skipped: %s", exc)


# ─── Schemas ─────────────────────────────────────────────────────────────────
class CommunityReportIn(BaseModel):
    company_name: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=32)
    email: Optional[str] = Field(None, max_length=255)
    url: Optional[str] = Field(None, max_length=512)
    report_type: str = Field("penipuan", max_length=24)
    description: Optional[str] = Field(None, max_length=4000)
    reporter_contact: Optional[str] = Field(None, max_length=255)


class CommunityReportOut(BaseModel):
    id: str
    report_type: str
    company_name: Optional[str]
    phone: Optional[str]
    email: Optional[str]
    url: Optional[str]
    description: Optional[str]
    created_at: str


def _normalize_phone(phone: str) -> str:
    digits = "".join(c for c in (phone or "") if c.isdigit())
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    return digits


# ─── Endpoints ───────────────────────────────────────────────────────────────
@router.post("/community/report", status_code=201, summary="Kirim Laporan Penipuan Komunitas")
def submit_report(payload: CommunityReportIn, db: Session = Depends(get_db)):
    # Minimal satu entitas target harus ada
    if not any([payload.company_name, payload.phone, payload.email, payload.url]):
        raise HTTPException(
            status_code=422,
            detail="Isi minimal satu entitas yang dilaporkan: nama perusahaan, nomor HP, email, atau URL.",
        )

    report = CommunityReport(
        company_name=(payload.company_name or "").strip() or None,
        phone=_normalize_phone(payload.phone) or None,
        email=(payload.email or "").strip().lower() or None,
        url=(payload.url or "").strip() or None,
        report_type=(payload.report_type or "penipuan").strip(),
        description=(payload.description or "").strip() or None,
        reporter_contact=(payload.reporter_contact or "").strip() or None,
    )
    db.add(report)
    try:
        db.commit()
        db.refresh(report)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan laporan: {exc}") from exc

    return {
        "status": "ok",
        "message": "Laporan diterima. Terima kasih telah membantu melindungi pencari kerja lain.",
        "id": str(report.id),
    }


@router.get("/community/check", summary="Cek Agregasi Laporan untuk Suatu Entitas")
def check_entity(
    company_name: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    url: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Kembalikan berapa kali entitas dilaporkan — dipakai Fraud Network."""
    if not any([company_name, phone, email, url]):
        raise HTTPException(status_code=422, detail="Sertakan minimal satu parameter entitas.")

    conditions = []
    if company_name:
        conditions.append(func.lower(CommunityReport.company_name) == company_name.strip().lower())
    if phone:
        conditions.append(CommunityReport.phone == _normalize_phone(phone))
    if email:
        conditions.append(func.lower(CommunityReport.email) == email.strip().lower())
    if url:
        conditions.append(CommunityReport.url == url.strip())

    try:
        count = db.query(func.count(CommunityReport.id)).filter(or_(*conditions)).scalar() or 0
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Gagal memeriksa laporan: {exc}") from exc

    return {
        "status": "ok",
        "report_count": int(count),
        "reported_by_community": count > 0,
        "risk_signal": "HIGH" if count >= 3 else ("MEDIUM" if count == 2 else ("LOW" if count == 1 else "NONE")),
    }


@router.get("/community/recent", summary="Laporan Komunitas Terbaru (Transparansi Publik)")
def recent_reports(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    try:
        rows = (
            db.query(CommunityReport)
            .order_by(CommunityReport.created_at.desc())
            .limit(limit)
            .all()
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Gagal mengambil laporan: {exc}") from exc

    return {
        "status": "ok",
        "count": len(rows),
        "reports": [
            CommunityReportOut(
                id=str(r.id),
                report_type=r.report_type,
                company_name=r.company_name,
                phone=r.phone,
                email=r.email,
                url=r.url,
                description=r.description,
                created_at=r.created_at.isoformat() if r.created_at else "",
            ).model_dump()
            for r in rows
        ],
    }
