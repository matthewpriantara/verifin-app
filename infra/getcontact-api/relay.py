"""Relay TCP di VPS produksi untuk layanan getcontact-api (audit-007 RC7).

Tailnet VPS tidak bisa membuka TCP ke home, tetapi home bisa SSH ke VPS. Home membuka reverse
tunnel `-R 127.0.0.1:8091:100.82.95.50:8091`, dan sshd VPS hanya mengizinkan bind ke loopback
(GatewayPorts no, tanpa sudo). Relay ini meneruskan gateway bridge Docker (mis. 172.26.0.1:8091)
ke loopback itu, supaya container backend produksi bisa memanggilnya. Tidak ada data yang disimpan.
"""
from __future__ import annotations

import asyncio
import os

LISTEN_HOST = os.environ.get("RELAY_LISTEN_HOST", "172.26.0.1")
LISTEN_PORT = int(os.environ.get("RELAY_LISTEN_PORT", "8091"))
TARGET_HOST = os.environ.get("RELAY_TARGET_HOST", "127.0.0.1")
TARGET_PORT = int(os.environ.get("RELAY_TARGET_PORT", "8091"))


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.CancelledError):
        pass
    finally:
        writer.close()


async def _handle(client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
    try:
        target_reader, target_writer = await asyncio.wait_for(
            asyncio.open_connection(TARGET_HOST, TARGET_PORT), timeout=5
        )
    except (OSError, asyncio.TimeoutError):
        client_writer.close()
        return
    await asyncio.gather(_pipe(client_reader, target_writer), _pipe(target_reader, client_writer))


async def main() -> None:
    server = await asyncio.start_server(_handle, LISTEN_HOST, LISTEN_PORT)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
