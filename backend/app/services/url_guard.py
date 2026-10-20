import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

_REDIRECT_CODES = {301, 302, 303, 307, 308}


def validate_public_http_url(value: str) -> str:
    parsed = urlparse((value or "").strip())
    if parsed.scheme.lower() not in {"http", "https"}:
        raise ValueError("URL harus menggunakan http atau https.")
    if parsed.username or parsed.password:
        raise ValueError("URL dengan kredensial tidak didukung.")
    host = (parsed.hostname or "").rstrip(".").lower()
    if not host:
        raise ValueError("URL tidak memiliki hostname.")
    if host in {"localhost", "localhost.localdomain", "metadata.google.internal"}:
        raise ValueError("Hostname internal tidak diizinkan.")
    addresses = []
    try:
        addresses = [item[4][0] for item in socket.getaddrinfo(host, None)]
    except socket.gaierror:
        pass
    for address in {ip for ip in addresses if ip}:
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("URL menuju jaringan internal tidak diizinkan.")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal and (literal.is_private or literal.is_loopback or literal.is_link_local or literal.is_reserved):
        raise ValueError("IP internal tidak diizinkan.")
    return (value or "").strip()


def is_public_http_url(value: str) -> bool:
    try:
        validate_public_http_url(value)
        return True
    except ValueError:
        return False


# URL di teks lowongan berasal dari pengguna. Setiap lompatan redirect divalidasi ulang supaya
# tautan publik tidak bisa diarahkan ke layanan internal server (SSRF).
def safe_get(
    url: str,
    *,
    headers: dict | None = None,
    timeout: float = 8.0,
    max_hops: int = 5,
) -> httpx.Response:
    current = validate_public_http_url(url)
    with httpx.Client(timeout=timeout, headers=headers, follow_redirects=False) as client:
        for _ in range(max_hops + 1):
            response = client.get(current)
            location = response.headers.get("location")
            if response.status_code not in _REDIRECT_CODES or not location:
                return response
            current = validate_public_http_url(urljoin(current, location))
    raise ValueError("Terlalu banyak redirect.")


async def safe_get_async(
    url: str,
    *,
    headers: dict | None = None,
    timeout: float = 15.0,
    max_hops: int = 5,
) -> httpx.Response:
    current = validate_public_http_url(url)
    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=False) as client:
        for _ in range(max_hops + 1):
            response = await client.get(current)
            location = response.headers.get("location")
            if response.status_code not in _REDIRECT_CODES or not location:
                return response
            current = validate_public_http_url(urljoin(current, location))
    raise ValueError("Terlalu banyak redirect.")


def resolve_public_url(url: str, *, headers: dict | None = None, timeout: float = 6.0, max_hops: int = 5) -> str:
    """URL akhir setelah redirect, dengan setiap lompatan divalidasi. Dipakai sebelum Scrapling,
    yang lalu dipanggil dengan follow_redirects=False."""
    current = validate_public_http_url(url)
    with httpx.Client(timeout=timeout, headers=headers, follow_redirects=False) as client:
        for _ in range(max_hops + 1):
            try:
                response = client.head(current)
            except httpx.HTTPError:
                return current
            location = response.headers.get("location")
            if response.status_code not in _REDIRECT_CODES or not location:
                return current
            current = validate_public_http_url(urljoin(current, location))
    raise ValueError("Terlalu banyak redirect.")
