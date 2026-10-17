import pytest
from fastapi import HTTPException

from app.services import security
from app.services.security import RateLimiter, require_admin


def test_admin_endpoints_fail_closed_without_server_token(monkeypatch):
    monkeypatch.setattr(security, "ADMIN_API_TOKEN", "")
    with pytest.raises(HTTPException) as exc:
        require_admin("apa-saja")
    assert exc.value.status_code == 503


def test_admin_token_must_match(monkeypatch):
    monkeypatch.setattr(security, "ADMIN_API_TOKEN", "rahasia-benar")
    for wrong in (None, "", "rahasia-salah"):
        with pytest.raises(HTTPException) as exc:
            require_admin(wrong)
        assert exc.value.status_code == 401
    assert require_admin("rahasia-benar") is None


def test_rate_limiter_blocks_after_limit_and_recovers():
    rl = RateLimiter(limit=2, window_sec=60)
    assert rl.hit("ip", now=0) is None
    assert rl.hit("ip", now=1) is None
    wait = rl.hit("ip", now=2)
    assert wait is not None and 57 < wait <= 58
    assert rl.hit("ip-lain", now=2) is None  # batas dihitung per IP
    assert rl.hit("ip", now=61) is None  # jendela bergeser


def _request(method: str, path: str, **kwargs):
    """Panggil app lewat ASGI tanpa menjalankan lifespan (warmup OCR/DB)."""
    import asyncio
    import httpx
    from app.main import app

    async def go():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(go())


def test_protected_routes_reject_requests_without_token(monkeypatch):
    monkeypatch.setattr(security, "ADMIN_API_TOKEN", "rahasia-benar")
    assert _request("GET", "/api/v1/cases").status_code == 401
    assert _request("GET", "/api/v1/community/reports").status_code == 401
    r = _request(
        "PATCH",
        "/api/v1/community/reports/00000000-0000-0000-0000-000000000000",
        json={"status": "approved"},
    )
    assert r.status_code == 401


def test_case_lookup_rejects_short_prefix():
    assert _request("GET", "/api/v1/cases/a").status_code == 404
