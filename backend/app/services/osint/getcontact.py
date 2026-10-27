"""Klien layanan `getcontact-api` di home server (uji coba, 27 Okt 2026).

GetContact dipakai hanya untuk jumlah tag dan label spam per nomor. Isi tag dan nama pemilik
adalah data pribadi pihak ketiga, jadi tidak diminta, tidak disimpan, dan tidak dikembalikan.
Layanan berjalan di Tailscale (100.82.95.50:8091) dan dimatikan dengan mengosongkan GETCONTACT_URL.
"""
from __future__ import annotations

import logging

import httpx

from app.config import GETCONTACT_TIMEOUT, GETCONTACT_TOKEN, GETCONTACT_URL
from app.services.osint.phone_validator import normalize_phone_id
from app.services.status_contract import COMPLETED, UNAVAILABLE

logger = logging.getLogger(__name__)

UNKNOWN = "UNKNOWN"
FEW = "FEW"
KNOWN = "KNOWN"
WELL_KNOWN = "WELL_KNOWN"
SPAM = "SPAM"


def classify_community_level(found: bool | None, tag_count: int | None, spam_flagged: bool) -> str:
    """Pemetaan jumlah tag ke tingkat kehadiran di komunitas GetContact.

    SPAM menang atas jumlah tag: nomor bisa punya banyak tag tetapi tetap ditandai spam.
    """
    if spam_flagged:
        return SPAM
    if not found or not tag_count or tag_count <= 0:
        return UNKNOWN
    if tag_count < 10:
        return FEW
    if tag_count < 100:
        return KNOWN
    return WELL_KNOWN


def _unavailable(reason: str) -> dict:
    return {
        "source": "getcontact",
        "probe_status": UNAVAILABLE,
        "found": False,
        "tag_count": None,
        "spam_flagged": False,
        "community_level": None,
        "reason": reason,
    }


async def lookup_getcontact(phone: str) -> dict:
    """Cek satu nomor. Tidak pernah melempar exception ke pemanggil."""
    if not GETCONTACT_URL:
        return _unavailable("layanan belum dikonfigurasi")
    meta = normalize_phone_id(phone)
    if not meta.get("local") or len(meta["local"]) < 8:
        return _unavailable("format nomor tidak valid")

    try:
        async with httpx.AsyncClient(timeout=GETCONTACT_TIMEOUT) as client:
            res = await client.get(
                f"{GETCONTACT_URL}/lookup",
                params={"phone": meta["e164"]},
                headers={"X-Api-Key": GETCONTACT_TOKEN},
            )
    except Exception as exc:
        logger.info("[getcontact] gagal memanggil layanan: %s", type(exc).__name__)
        return _unavailable("layanan tidak dapat dihubungi")

    if res.status_code != 200:
        return _unavailable(f"layanan menjawab HTTP {res.status_code}")

    try:
        data = res.json()
    except ValueError:
        return _unavailable("jawaban layanan bukan JSON")

    status = str(data.get("status") or "").upper()
    if status != COMPLETED:
        return _unavailable(f"status {status or 'tidak diketahui'}")

    found = bool(data.get("found"))
    raw_count = data.get("tag_count")
    tag_count = int(raw_count) if isinstance(raw_count, (int, float)) else 0
    spam_flagged = bool(data.get("spam_flagged"))
    return {
        "source": "getcontact",
        "probe_status": COMPLETED,
        "found": found,
        "tag_count": tag_count if found or tag_count else 0,
        "spam_flagged": spam_flagged,
        "community_level": classify_community_level(found, tag_count, spam_flagged),
    }
