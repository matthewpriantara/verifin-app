"""Thread pool khusus probe OSINT yang memblokir (SearXNG, Kaspersky, WHOIS, sosial).

Dipisah dari thread pool bawaan asyncio supaya saat banyak permintaan menunggu jeda
pencarian, pekerjaan lain (cek cache, simpan ke DB, NER regex) tidak ikut tertahan.
"""
import os
from concurrent.futures import ThreadPoolExecutor

OSINT_EXECUTOR = ThreadPoolExecutor(
    max_workers=int(os.getenv("OSINT_MAX_WORKERS", "64")), thread_name_prefix="osint"
)
