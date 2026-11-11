"""Loader snapshot telemetri runtime sistem verifin.

Snapshot ini adalah sumber utama (single source of truth) untuk status layanan.
Dipakai bersama oleh `/health` dan `/verify/status` agar keduanya tidak pernah
menyimpang satu sama lain.
"""

import json
import os
from pathlib import Path

# Snapshot telemetri runtime sistem verifin (dibaca dinamis saat file tersedia)
SYSTEM_STATUS_FILE = Path(os.getenv("SYSTEM_STATUS_FILE", "/app/data/runtime/system_status.json"))


def load_runtime_telemetry():
    """Membaca snapshot telemetri sistem bila dikonfigurasi pada level runtime."""
    candidates = [
        SYSTEM_STATUS_FILE,
        Path("backend/data/runtime/system_status.json"),
        Path("data/runtime/system_status.json"),
    ]
    for path in candidates:
        try:
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except (OSError, ValueError):
            continue
    return None
