from __future__ import annotations

import hashlib
from typing import Any


def compute_content_sha256(text_or_bytes: str | bytes) -> str:
    if isinstance(text_or_bytes, str):
        data = text_or_bytes.strip().lower().encode("utf-8")
    else:
        data = text_or_bytes
    return hashlib.sha256(data).hexdigest()


def detect_identity_syndicate(
    contacts: list[str],
    emails: list[str],
    current_company: str,
    historical_cases: list[dict] | None = None,
) -> dict:
    syndicate_alerts: list[dict] = []
    cases = historical_cases or []
    current_company_norm = (current_company or "").strip().lower()

    def _companies_using(key: str, value: str) -> set[str]:
        names: set[str] = set()
        for c in cases:
            pool = (c.get("phones") or []) if key == "phone" else (c.get("emails") or [])
            if value in pool:
                nm = (c.get("company_name") or "").strip().lower()
                if nm and nm != current_company_norm:
                    names.add(nm)
        return names

    if cases:
        for phone in contacts or []:
            other = _companies_using("phone", phone)
            if other:
                syndicate_alerts.append({
                    "type": "PHONE_REUSE_MULTIPLE_COMPANIES",
                    "detail": (
                        f"Nomor {phone} tercatat dipakai oleh {len(other)} perusahaan lain: "
                        f"{', '.join(sorted(other))}."
                    ),
                    "severity": "HIGH" if len(other) >= 2 else "MEDIUM",
                    "evidence_count": len(other),
                })
        for email in emails or []:
            other = _companies_using("email", email)
            if other:
                syndicate_alerts.append({
                    "type": "EMAIL_REUSE_MULTIPLE_COMPANIES",
                    "detail": (
                        f"Email {email} tercatat dipakai oleh {len(other)} perusahaan lain: "
                        f"{', '.join(sorted(other))}."
                    ),
                    "severity": "HIGH" if len(other) >= 2 else "MEDIUM",
                    "evidence_count": len(other),
                })

    return {
        "syndicate_detected": len(syndicate_alerts) > 0,
        "syndicate_alerts": syndicate_alerts,
        "historical_associations_count": sum(a.get("evidence_count", 0) for a in syndicate_alerts),
        "data_source": "database_historical_cases" if cases else "no_historical_data",
        "note": (
            "Dihitung dari riwayat job_cases nyata."
            if cases else
            "Belum ada data historis untuk analisis sindikat — hasil jujur kosong."
        ),
    }
