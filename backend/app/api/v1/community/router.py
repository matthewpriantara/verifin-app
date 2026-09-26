"""
Community Reports — laporan penipuan dari komunitas (suplemen Fraud Network).

Endpoint:
- POST /community/report   → kirim laporan baru (multipart: JSON fields + optional gambar)
- GET  /community/check    → cek berapa kali entitas dilaporkan
- GET  /community/recent   → laporan terbaru (transparansi publik)
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy import func, or_, text
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database.models import CommunityReport
from app.database.postgres_client import Base, engine, get_db
from app.services.ner import clean_indonesian_phone
from app.api.v1.community.schema import CommunityReportIn, CommunityReportOut, ModerationUpdate

logger = logging.getLogger(__name__)
router = APIRouter()

# Buat tabel bila belum ada (aman: checkfirst=True, tidak menimpa yang ada).
try:
    Base.metadata.create_all(bind=engine, tables=[CommunityReport.__table__], checkfirst=True)
except Exception as exc:  # noqa: BLE001 — jangan gagalkan boot bila DB sesaat down
    logger.warning("[community] create_all skipped: %s", exc)

# Migrasi ringan: tambah kolom moderasi bila tabel sudah ada dari versi lama.
try:
    with engine.begin() as conn:
        for ddl in (
            'ALTER TABLE community_reports ADD COLUMN IF NOT EXISTS status VARCHAR(12) NOT NULL DEFAULT \'pending\'',
            'ALTER TABLE community_reports ADD COLUMN IF NOT EXISTS reporter_ip VARCHAR(45)',
            'ALTER TABLE community_reports ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ',
            'ALTER TABLE community_reports ADD COLUMN IF NOT EXISTS reviewer_note TEXT',
            'ALTER TABLE community_reports ADD COLUMN IF NOT EXISTS case_id VARCHAR(64)',
            'ALTER TABLE community_reports ADD COLUMN IF NOT EXISTS evidence_file_url VARCHAR(512)',
            'CREATE INDEX IF NOT EXISTS ix_community_reports_status ON community_reports (status)',
        ):
            conn.execute(text(ddl))
except Exception as exc:  # noqa: BLE001
    logger.warning("[community] migration skipped: %s", exc)


@router.post("/community/report", status_code=201, summary="Kirim Laporan Penipuan Komunitas")
async def submit_report(
    request: Request,
    db: Session = Depends(get_db),
    company_name: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    url: Optional[str] = Form(None),
    report_type: str = Form("penipuan"),
    description: Optional[str] = Form(None),
    reporter_contact: Optional[str] = Form(None),
    case_id: Optional[str] = Form(None),
    evidence_file: Optional[UploadFile] = File(None),
):
    if not any([company_name, phone, email, url]):
        raise HTTPException(
            status_code=422,
            detail="Isi minimal satu entitas yang dilaporkan: nama perusahaan, nomor HP, email, atau URL.",
        )

    # Simpan gambar bukti jika ada
    evidence_file_url = None
    if evidence_file and evidence_file.filename:
        # Validasi tipe file (hanya gambar)
        allowed_types = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
        if evidence_file.content_type not in allowed_types:
            raise HTTPException(
                status_code=422,
                detail="Format file tidak didukung. Gunakan JPG, PNG, atau WebP.",
            )
        # Validasi ukuran (max 5MB)
        contents = await evidence_file.read()
        if len(contents) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=422,
                detail="Ukuran file terlalu besar. Maksimal 5MB.",
            )

        import uuid as _uuid
        ext = os.path.splitext(evidence_file.filename)[1].lower() or ".jpg"
        filename = f"{_uuid.uuid4().hex}{ext}"
        upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads", "evidence")
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)
        with open(filepath, "wb") as f:
            f.write(contents)
        evidence_file_url = f"/uploads/evidence/{filename}"

    report = CommunityReport(
        company_name=(company_name or "").strip() or None,
        phone=clean_indonesian_phone(phone) or None,
        email=(email or "").strip().lower() or None,
        url=(url or "").strip() or None,
        report_type=(report_type or "penipuan").strip(),
        description=(description or "").strip() or None,
        reporter_contact=(reporter_contact or "").strip() or None,
        reporter_ip=request.client.host if request.client else None,
        case_id=(case_id or "").strip() or None,
        evidence_file_url=evidence_file_url,
        status="pending",
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
        conditions.append(CommunityReport.phone == clean_indonesian_phone(phone))
    if email:
        conditions.append(func.lower(CommunityReport.email) == email.strip().lower())
    if url:
        conditions.append(CommunityReport.url == url.strip())

    try:
        count = db.query(func.count(CommunityReport.id)).filter(or_(*conditions)).scalar() or 0
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Gagal mengambil data: {exc}") from exc

    return {
        "status": "ok",
        "report_count": int(count),
        "reported_by_community": count > 0,
        "risk_signal": "HIGH" if count >= 3 else ("MEDIUM" if count == 2 else ("LOW" if count == 1 else "NONE")),
    }


@router.get("/community/recent", summary="Laporan Komunitas Terbaru")
def recent_reports(
    limit: int = Query(20, ge=1, le=100),
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
                reporter_ip=r.reporter_ip,
                case_id=r.case_id,
                evidence_file_url=r.evidence_file_url,
                status=r.status or "pending",
                reviewer_note=r.reviewer_note,
                reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
                created_at=r.created_at.isoformat() if r.created_at else "",
            ).model_dump()
            for r in rows
        ],
    }


@router.get("/community/reports", summary="Daftar laporan komunitas (termasuk status moderasi)")
def list_reports(
    status: Optional[str] = Query(None, pattern="^(pending|approved|rejected)$"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(CommunityReport)
    if status:
        query = query.filter(CommunityReport.status == status)
    try:
        rows = query.order_by(CommunityReport.created_at.desc()).limit(limit).all()
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
                reporter_ip=r.reporter_ip,
                case_id=r.case_id,
                evidence_file_url=r.evidence_file_url,
                status=r.status or "pending",
                reviewer_note=r.reviewer_note,
                reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
                created_at=r.created_at.isoformat() if r.created_at else "",
            ).model_dump()
            for r in rows
        ],
    }


@router.patch("/community/reports/{report_id}", summary="Tinjau laporan (approve/reject) oleh moderator")
def review_report(
    report_id: UUID,
    payload: ModerationUpdate,
    db: Session = Depends(get_db),
):
    report = db.query(CommunityReport).filter(CommunityReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Laporan tidak ditemukan.")

    report.status = payload.status
    report.reviewer_note = (payload.reviewer_note or "").strip() or None
    if payload.status in ("approved", "rejected"):
        report.reviewed_at = func.now()
    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Gagal menyimpan review: {exc}") from exc

    return {
        "status": "ok",
        "id": str(report.id),
        "report_status": report.status,
    }
