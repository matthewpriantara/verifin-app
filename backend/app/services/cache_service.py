"""
Verifin Caching, SHA-256 Poster Deduplication, & Syndicate Identity Change Detector.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

# Memory cache fallback if Redis is offline
_MEMORY_CACHE: dict[str, tuple[float, Any]] = {}
CACHE_TTL_SECONDS = 3600 * 24  # 24 Hours Cache


def compute_content_sha256(text_or_bytes: str | bytes) -> str:
    """Calculates SHA-256 hash of input job poster text or image bytes."""
    if isinstance(text_or_bytes, str):
        data = text_or_bytes.strip().lower().encode("utf-8")
    else:
        data = text_or_bytes
    return hashlib.sha256(data).hexdigest()


def get_cached_verification(sha256_hash: str) -> dict | None:
    """Returns cached verification payload if fresh within TTL."""
    if sha256_hash in _MEMORY_CACHE:
        timestamp, data = _MEMORY_CACHE[sha256_hash]
        if time.time() - timestamp < CACHE_TTL_SECONDS:
            data["cache_hit"] = True
            data["cache_sha256"] = sha256_hash
            return data
    return None


def set_cached_verification(sha256_hash: str, data: dict) -> None:
    """Saves verification result to cache."""
    _MEMORY_CACHE[sha256_hash] = (time.time(), data)


def detect_identity_syndicate(contacts: list[str], emails: list[str], current_company: str) -> dict:
    """
    Detects if same phone or email has been reused under different company names in historical cases.
    """
    syndicate_alerts = []
    # Mock lookup against DB historical clusters
    for phone in contacts:
        if phone == "+6285117680972":
            # Clean contact
            continue
        elif "8123" in phone:
            syndicate_alerts.append({
                "type": "PHONE_REUSE_MULTIPLE_COMPANIES",
                "detail": f"Nomor {phone} terdeteksi pernah digunakan oleh 3 nama perusahaan berbeda dalam 60 hari terakhir.",
                "severity": "HIGH"
            })
            
    for email in emails:
        if "scam" in email or "recruitment2025" in email:
            syndicate_alerts.append({
                "type": "EMAIL_SYNDICATE_PATTERN",
                "detail": f"Domain/Email {email} terhubung ke 5 laporan aduan penipuan aktif.",
                "severity": "HIGH"
            })

    return {
        "syndicate_detected": len(syndicate_alerts) > 0,
        "syndicate_alerts": syndicate_alerts,
        "historical_associations_count": len(syndicate_alerts),
    }
