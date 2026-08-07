"""Validation for user-supplied URLs before server-side fetching."""

import ipaddress
import socket
from urllib.parse import urlparse


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
