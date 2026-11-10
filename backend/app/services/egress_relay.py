"""Relai TCP lokal ke unix socket proxy keluar.

Dipakai saat jaringan host menahan HTTPS keluar (portal login kampus di VPS). Home membuka
reverse SSH tunnel ke unix socket di VPS yang berujung di tinyproxy home. Container tidak bisa
menjangkau port host, dan pustaka HTTP tidak bisa memakai proxy lewat unix socket, jadi backend
membuka port loopback sendiri yang meneruskan byte ke socket itu. `HTTPS_PROXY` cukup menunjuk
ke port loopback ini. Kosongkan `EGRESS_PROXY_UDS` untuk mematikan.
"""
import asyncio
import logging
import os

logger = logging.getLogger(__name__)

EGRESS_PROXY_UDS = os.getenv("EGRESS_PROXY_UDS", "")
EGRESS_PROXY_PORT = int(os.getenv("EGRESS_PROXY_PORT", "8899"))


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, asyncio.IncompleteReadError, OSError):
        pass
    finally:
        try:
            writer.close()
        except OSError:
            pass


async def _handle(client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter) -> None:
    try:
        up_reader, up_writer = await asyncio.open_unix_connection(EGRESS_PROXY_UDS)
    except OSError as e:
        logger.warning("[egress] socket proxy %s tidak bisa dibuka: %s", EGRESS_PROXY_UDS, e)
        client_writer.close()
        return
    await asyncio.gather(_pipe(client_reader, up_writer), _pipe(up_reader, client_writer))


async def start_egress_relay() -> asyncio.AbstractServer | None:
    if not EGRESS_PROXY_UDS:
        return None
    server = await asyncio.start_server(_handle, "127.0.0.1", EGRESS_PROXY_PORT)
    logger.info("[egress] relai proxy aktif: 127.0.0.1:%s -> %s", EGRESS_PROXY_PORT, EGRESS_PROXY_UDS)
    return server
