"""Sinkronkan laporan komunitas ke kasus tersimpan setelah laporan masuk atau dimoderasi.

Hasil verifikasi menyimpan potret `community_reports` saat pemeriksaan berjalan, dan potret itu
dipakai lagi oleh GET /cases/{id} serta cache. Tanpa sinkronisasi ini laporan yang baru disetujui
tetap tampil "menunggu tinjauan" sampai lowongan diperiksa ulang dari nol.

Kasus diperbarui di tempat, bukan dijalankan ulang: jumlah laporan dihitung ulang dari DB, lalu
kontribusi "Dilaporkan Komunitas" pada atribusi skor diganti (lihat `rescore_community_reports`).
Penilaian LLM lain tidak disentuh, jadi skor bergeser tepat sebesar bobot komunitas.
"""
from __future__ import annotations

import copy
import logging
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database.models import CommunityReport, JobCase
from app.services.ner import clean_indonesian_phone
from app.services.xai.shap_explainer import rescore_community_reports

logger = logging.getLogger(__name__)

COMMUNITY_RISK_FACTOR = "Pernah dilaporkan komunitas dan disetujui admin."
_MAX_CASES = 200


def _phone_variants(phone: str | None) -> list[str]:
    canon = clean_indonesian_phone(phone or "")
    if not canon:
        return []
    digits = canon.lstrip("+")
    return [canon, digits, "0" + digits[2:]]


def _related_cases(db: Session, report: CommunityReport) -> list[JobCase]:
    """Kandidat kasus yang mungkin cocok; kecocokan akhir ditentukan `_community_report_signal`."""
    conditions = []
    if report.case_id:
        try:
            conditions.append(JobCase.id == UUID(str(report.case_id)))
        except ValueError:
            pass
    for v in _phone_variants(report.phone):
        conditions.append(JobCase.phones.contains([v]))
    if report.email:
        conditions.append(JobCase.emails.contains([report.email]))
    if report.url:
        conditions.append(JobCase.urls.contains([report.url]))
    if report.company_name:
        name = report.company_name.strip()
        conditions.append(func.lower(JobCase.company_name) == name.lower())
        conditions.append(JobCase.companies.contains([name]))
    if not conditions:
        return []
    return db.query(JobCase).filter(or_(*conditions)).limit(_MAX_CASES).all()


def _case_entities(case: JobCase) -> dict:
    ent = case.entities or {}
    return {
        "companies": case.companies or ent.get("companies") or [],
        "phones": case.phones or ent.get("phones") or [],
        "emails": case.emails or ent.get("emails") or [],
        "urls": case.urls or ent.get("urls") or [],
    }


def apply_community_signal(case: JobCase, community: dict) -> bool:
    """Tulis hasil hitung ulang ke kasus. True bila ada yang berubah."""
    osint_summary = copy.deepcopy(case.osint_summary or {})
    response_osint = osint_summary.get("response_osint")
    if not isinstance(response_osint, dict):
        return False
    network = dict(response_osint.get("fraud_network") or {})
    old = network.get("community_reports") or {}
    approved = int(community.get("report_count") or 0)
    if (
        int(old.get("report_count") or 0) == approved
        and int(old.get("pending_report_count") or 0) == int(community.get("pending_report_count") or 0)
        and old.get("status") == community.get("status")
        and (old.get("reported_phones") or []) == (community.get("reported_phones") or [])
    ):
        return False

    network["community_reports"] = community
    network["reported_by_community"] = approved > 0
    if approved >= 3:
        network["threat_level"] = "HIGH"
    elif approved > 0 and network.get("threat_level") != "HIGH":
        network["threat_level"] = "MEDIUM"
    response_osint["fraud_network"] = network
    osint_summary["response_osint"] = response_osint
    case.osint_summary = osint_summary

    llm_output = copy.deepcopy(case.llm_output or {})
    shap = llm_output.get("shap_explanation")
    if isinstance(shap, dict) and shap.get("feature_contributions") is not None:
        risk_score, verdict, llm_output["shap_explanation"] = rescore_community_reports(shap, approved)
        case.risk_score = risk_score
        case.verdict = verdict
    risk_factors = [f for f in (llm_output.get("risk_factors") or []) if f != COMMUNITY_RISK_FACTOR]
    if approved > 0:
        risk_factors.insert(0, COMMUNITY_RISK_FACTOR)
    llm_output["risk_factors"] = risk_factors
    case.llm_output = llm_output
    return True


def refresh_cases_for_report(db: Session, report: CommunityReport) -> int:
    """Hitung ulang laporan komunitas untuk kasus yang terkait dengan `report`; kembalikan jumlah kasus berubah."""
    from app.api.v1.verify.pipeline import _community_report_signal

    changed = 0
    for case in _related_cases(db, report):
        community = _community_report_signal(db, _case_entities(case))
        if community.get("status") != "COMPLETED":
            continue
        if apply_community_signal(case, community):
            changed += 1
    if changed:
        db.commit()
        logger.info("[Community] %d kasus diperbarui setelah laporan %s (%s)", changed, report.id, report.status)
    return changed
