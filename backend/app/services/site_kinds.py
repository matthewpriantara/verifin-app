"""Jenis situs dari satu berkas data (`app/data/site_kinds.json`, audit-007 10.7 C).

Sebelumnya daftar pemendek URL, marketplace, portal loker, domain bebas daftar, dan email gratisan
tersebar di beberapa modul yang tidak saling tahu. Menambah portal baru cukup mengubah JSON.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

_DATA = Path(__file__).resolve().parent.parent / "data" / "site_kinds.json"

# Jenis yang berarti "situs pihak ketiga", bukan milik pemberi kerja.
THIRD_PARTY_KINDS = frozenset({
    "free_email", "shortener", "form", "open_registration", "social_platform",
    "marketplace", "job_portal", "directory", "travel", "news",
})


@lru_cache(maxsize=1)
def _data() -> dict:
    return json.loads(_DATA.read_text(encoding="utf-8"))


def hosts(kind: str) -> tuple[str, ...]:
    return tuple(_data().get(kind) or ())


def tokens(kind: str) -> tuple[str, ...]:
    return tuple(_data().get(kind) or ())


def normalize_host(value: str) -> str:
    value = (value or "").strip().lower()
    if "://" in value:
        value = urlparse(value).hostname or ""
    elif "@" in value:
        value = value.rsplit("@", 1)[-1]
    else:
        value = value.split("/")[0]
    return value.removeprefix("www.").rstrip(".")


def _matches(host: str, listed: tuple[str, ...]) -> bool:
    return any(host == h or host.endswith("." + h) for h in listed)


def is_open_registration(host: str) -> bool:
    host = normalize_host(host)
    if not host:
        return False
    if any(host.endswith(s) and host.count(".") >= 2 for s in hosts("open_registration_suffix")):
        return True
    # Domain induknya sendiri (mis. vercel.app) bukan situs milik pengguna.
    return any(host.endswith("." + h) for h in hosts("open_registration_host"))


def kind_of(value: str) -> str:
    """Kembalikan jenis host ("shortener", "marketplace", …) atau "" bila tidak dikenal."""
    host = normalize_host(value)
    if not host:
        return ""
    for kind in ("free_email", "shortener", "form", "social_platform", "marketplace",
                 "job_portal", "directory", "travel", "news"):
        if _matches(host, hosts(kind)):
            return kind
    if is_open_registration(host):
        return "open_registration"
    return ""


def is_third_party(value: str) -> bool:
    return kind_of(value) in THIRD_PARTY_KINDS
