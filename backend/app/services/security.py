"""Autentikasi endpoint admin dan pembatas laju per IP.

Endpoint admin hanya bisa dipanggil lewat proxy server Next.js, yang menyisipkan
X-Admin-Token setelah memeriksa cookie sesi admin. Browser tidak pernah memegang token ini.
"""

import hmac
import threading
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

from app.config import ADMIN_API_TOKEN


def require_admin(x_admin_token: str | None = Header(None)) -> None:
    if not ADMIN_API_TOKEN:
        raise HTTPException(status_code=503, detail="Akses admin belum dikonfigurasi di server.")
    if not x_admin_token or not hmac.compare_digest(x_admin_token, ADMIN_API_TOKEN):
        raise HTTPException(status_code=401, detail="Akses admin ditolak.")


def client_ip(request: Request) -> str:
    # Di balik Cloudflare Tunnel/reverse proxy, IP asli ada di header ini.
    for header in ("cf-connecting-ip", "x-forwarded-for"):
        value = request.headers.get(header)
        if value:
            return value.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """Sliding window di memori. Cukup untuk satu proses server; bukan pengganti limiter terdistribusi."""

    def __init__(self, limit: int, window_sec: float = 60.0):
        self.limit = limit
        self.window = window_sec
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, now: float | None = None) -> float | None:
        """Catat satu permintaan. Kembalikan detik tunggu bila melewati batas, None bila lolos."""
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] >= self.window:
                q.popleft()
            if len(q) >= self.limit:
                return self.window - (now - q[0])
            q.append(now)
            return None

    def dependency(self, scope: str):
        def check(request: Request) -> None:
            if self.limit <= 0:
                return
            wait = self.hit(f"{scope}:{client_ip(request)}")
            if wait is not None:
                raise HTTPException(
                    status_code=429,
                    detail=f"Terlalu banyak permintaan. Coba lagi dalam {int(wait) + 1} detik.",
                    headers={"Retry-After": str(int(wait) + 1)},
                )
        return check
