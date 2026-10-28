"""Layanan kecil GetContact untuk Verifin (uji coba, 27 Okt 2026).

Hanya mengembalikan jumlah tag dan label spam per nomor. Nama tampilan, email, dan isi tag
adalah data pribadi pihak ketiga, jadi tidak pernah disimpan atau dikembalikan.

Klien `gtc.py` tidak disalin ke repo publik ini; ia di-mount dari host ke /gtc/gtc.py.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import json
import os
import re
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Header, HTTPException, Query

sys.path.insert(0, "/gtc")
import gtc  # noqa: E402  (di-mount dari ~/Project/getcontact-cli/gtc.py)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("getcontact-api")

API_TOKEN = os.environ.get("GETCONTACT_API_TOKEN", "")
DAILY_LIMIT = int(os.environ.get("GTC_DAILY_LIMIT", "10"))
# B8/10.4: kuota number-detail terpisah dan sangat kecil (40/bulan di akun).
DETAIL_DAILY_LIMIT = int(os.environ.get("GTC_DETAIL_DAILY_LIMIT", "1"))
CACHE_TTL_DAYS = int(os.environ.get("GTC_CACHE_TTL_DAYS", "14"))
DB_PATH = os.environ.get("GTC_CACHE_DB", "/data/cache.db")
WIB = timezone(timedelta(hours=7))

app = FastAPI(title="Verifin GetContact API", version="1.0")
_lock = asyncio.Lock()
_last_status = "STARTING"


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cache ("
        " phone_hash TEXT PRIMARY KEY, found INTEGER, tag_count INTEGER, spam_degree TEXT,"
        " is_business INTEGER, checked_at TEXT)"
    )
    conn.execute("CREATE TABLE IF NOT EXISTS usage (day TEXT PRIMARY KEY, count INTEGER)")
    # 10.4: kolom tambahan untuk hasil number-detail (hanya hitungan, bukan teks tag).
    for column, decl in (
        ("fraud_tag_hits", "INTEGER"),
        ("fraud_tag_terms", "TEXT"),
        ("detail_checked_at", "TEXT"),
    ):
        try:
            conn.execute(f"ALTER TABLE cache ADD COLUMN {column} {decl}")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    return conn


def _today() -> str:
    return datetime.now(WIB).strftime("%Y-%m-%d")


def _hash(phone: str) -> str:
    return hashlib.sha256(phone.encode()).hexdigest()


def _cached(conn: sqlite3.Connection, phone_hash: str) -> dict | None:
    row = conn.execute(
        "SELECT found, tag_count, spam_degree, checked_at FROM cache WHERE phone_hash = ?",
        (phone_hash,),
    ).fetchone()
    if not row:
        return None
    checked_at = datetime.fromisoformat(row[3])
    if checked_at < datetime.now(timezone.utc) - timedelta(days=CACHE_TTL_DAYS):
        return None
    return {
        "status": "COMPLETED",
        "found": bool(row[0]),
        "tag_count": int(row[1] or 0),
        "spam_flagged": str(row[2] or "none").lower() == "flagged",
    }


def _store(conn: sqlite3.Connection, phone_hash: str, found: bool, tag_count: int, spam_degree: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO cache (phone_hash, found, tag_count, spam_degree, is_business, checked_at)"
        " VALUES (?, ?, ?, ?, 0, ?)",
        (phone_hash, int(found), tag_count, spam_degree, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def _used_today(conn: sqlite3.Connection, kind: str = "search") -> int:
    day = _today() if kind == "search" else f"{kind}:{_today()}"
    row = conn.execute("SELECT count FROM usage WHERE day = ?", (day,)).fetchone()
    return int(row[0]) if row else 0


def _consume_quota(conn: sqlite3.Connection, kind: str = "search") -> None:
    # B8: kuota dipanggil setelah jawaban sah (200/404), bukan sebelum request.
    day = _today() if kind == "search" else f"{kind}:{_today()}"
    conn.execute(
        "INSERT INTO usage (day, count) VALUES (?, 1) ON CONFLICT(day) DO UPDATE SET count = count + 1",
        (day,),
    )
    conn.commit()


def _is_spam(spam: dict) -> str:
    """GetContact memakai `degree` sebagai warna reputasi ("green" = aman) dan `type` untuk
    label spam. Nomor dengan 2 tag dan degree "green" bukan spam; hanya type spam/scam atau
    degree merah/oranye yang dihitung."""
    degree = str(spam.get("degree") or "none").lower()
    spam_type = str(spam.get("type") or "").lower()
    if spam_type in ("spam", "scam", "fraud"):
        return "flagged"
    if degree in ("red", "orange"):
        return "flagged"
    return degree


def _parse(body: dict) -> dict:
    result = body.get("result") or {}
    profile = result.get("profile") or {}
    spam = result.get("spamInfo") or {}
    return {
        "found": True,
        "tag_count": int(profile.get("tagCount") or 0),
        "spam_degree": _is_spam(spam),
    }


# 10.4: daftar kata tetap. Teks tag TIDAK PERNAH disimpan, dicatat di log, atau dikembalikan;
# yang keluar hanya jumlah tag yang cocok dan istilah dari daftar ini.
FRAUD_TERMS = (
    "penipu",
    "tipu",
    "scam",
    "scammer",
    "loker palsu",
    "lowongan palsu",
    "loker bodong",
    "bodong",
    "jangan diangkat",
    "jgn angkat",
    "investasi",
    "admin tugas",
    "like berbayar",
    "penipuan online",
    "hati hati",
)

_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})


def _normalize_tag(value: str) -> str:
    text = (value or "").lower().translate(_LEET)
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def count_fraud_tags(tags: list) -> tuple[int, list[str]]:
    """Hitung tag yang memuat kata penipuan. Kembalikan (jumlah_tag, istilah yang cocok)."""
    hits = 0
    matched: set[str] = set()
    for item in tags or []:
        raw = item.get("tag") if isinstance(item, dict) else item
        normalized = f" {_normalize_tag(str(raw or ''))} "
        if not normalized.strip():
            continue
        found = [term for term in FRAUD_TERMS if f" {term} " in normalized]
        if found:
            hits += 1
            matched.update(found)
    return hits, sorted(matched)


def _cached_tags(conn: sqlite3.Connection, phone_hash: str) -> dict | None:
    row = conn.execute(
        "SELECT fraud_tag_hits, fraud_tag_terms, detail_checked_at FROM cache WHERE phone_hash = ?",
        (phone_hash,),
    ).fetchone()
    if not row or row[2] is None:
        return None
    checked_at = datetime.fromisoformat(row[2])
    if checked_at < datetime.now(timezone.utc) - timedelta(days=CACHE_TTL_DAYS):
        return None
    return {
        "status": "COMPLETED",
        "fraud_tag_hits": int(row[0] or 0),
        "fraud_tag_terms": json.loads(row[1] or "[]"),
    }


@app.get("/lookup")
async def lookup(
    phone: str = Query(..., description="Nomor HP format bebas; dinormalisasi ke E.164"),
    x_api_key: str | None = Header(default=None),
):
    global _last_status
    if not API_TOKEN or x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="token salah")

    await asyncio.sleep(0)
    async with _lock:
        try:
            e164 = gtc.normalize_phone(phone)
        except gtc.GtcError:
            raise HTTPException(status_code=400, detail="nomor tidak valid")

        with closing(_db()) as conn:
            cached = _cached(conn, _hash(e164))
            if cached:
                _last_status = "CACHE"
                return cached
            if _used_today(conn) >= DAILY_LIMIT:
                _last_status = "QUOTA"
                return {"status": "QUOTA"}

        store = gtc.load_store()
        _, cred = gtc.get_cred(store, None)
        try:
            body = await asyncio.to_thread(gtc.api_search, cred, e164, "search")
        except gtc.GtcError as exc:
            message = str(exc)
            safe = "akun diblokir/captcha" if "403" in message else (
                "nomor tidak ditemukan" if "404" in message else "permintaan gagal"
            )
            logger.info("lookup %s: %s", _hash(e164)[:12], safe)
            if "404" in message:
                _last_status = "COMPLETED"
                with closing(_db()) as conn:
                    _store(conn, _hash(e164), False, 0, "none")
                    _consume_quota(conn)
                return {"status": "COMPLETED", "found": False, "tag_count": 0, "spam_flagged": False}
            _last_status = "BLOCKED" if "403" in message else "ERROR"
            return {"status": _last_status}
        except Exception:
            logger.exception("lookup %s gagal", _hash(e164)[:12])
            _last_status = "ERROR"
            return {"status": "ERROR"}

        parsed = _parse(body)
        with closing(_db()) as conn:
            _store(conn, _hash(e164), parsed["found"], parsed["tag_count"], parsed["spam_degree"])
            _consume_quota(conn)
        _last_status = "COMPLETED"
        return {
            "status": "COMPLETED",
            "found": parsed["found"],
            "tag_count": parsed["tag_count"],
            "spam_flagged": parsed["spam_degree"].lower() == "flagged",
        }


@app.get("/tags")
async def tags(
    phone: str = Query(..., description="Nomor HP; dinormalisasi ke E.164"),
    x_api_key: str | None = Header(default=None),
):
    """Baca isi tag untuk SATU nomor per hari, hanya mengembalikan hitungan kata penipuan."""
    global _last_status
    if not API_TOKEN or x_api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="token salah")

    async with _lock:
        try:
            e164 = gtc.normalize_phone(phone)
        except gtc.GtcError:
            raise HTTPException(status_code=400, detail="nomor tidak valid")

        phone_hash = _hash(e164)
        with closing(_db()) as conn:
            cached = _cached_tags(conn, phone_hash)
            if cached:
                _last_status = "CACHE"
                return cached
            lookup = _cached(conn, phone_hash)
            tag_count = int((lookup or {}).get("tag_count") or 0)
            spam_flagged = bool((lookup or {}).get("spam_flagged"))
            # Nomor 0 tag tidak punya isi; nomor >= 100 tag hampir pasti usaha mapan.
            if not lookup or not (1 <= tag_count <= 99) or spam_flagged:
                return {"status": "SKIPPED", "reason": "tag_count_out_of_range"}
            if _used_today(conn, "detail") >= DETAIL_DAILY_LIMIT:
                _last_status = "QUOTA"
                return {"status": "QUOTA"}

        store = gtc.load_store()
        _, cred = gtc.get_cred(store, None)
        try:
            body = await asyncio.to_thread(gtc.api_search, cred, e164, "tags")
        except gtc.GtcError as exc:
            message = str(exc)
            logger.info("tags %s: %s", phone_hash[:12], "403" if "403" in message else "gagal")
            _last_status = "BLOCKED" if "403" in message else "ERROR"
            return {"status": _last_status}
        except Exception:
            logger.exception("tags %s gagal", phone_hash[:12])
            _last_status = "ERROR"
            return {"status": "ERROR"}

        raw_tags = (body.get("result") or {}).get("tags") or []
        hits, matched = count_fraud_tags(raw_tags)
        # Teks tag hanya hidup di variabel lokal ini dan tidak pernah keluar dari fungsi.
        raw_tags = None
        with closing(_db()) as conn:
            conn.execute(
                "UPDATE cache SET fraud_tag_hits = ?, fraud_tag_terms = ?, detail_checked_at = ?"
                " WHERE phone_hash = ?",
                (hits, json.dumps(matched), datetime.now(timezone.utc).isoformat(), phone_hash),
            )
            conn.commit()
            _consume_quota(conn, "detail")
        _last_status = "COMPLETED"
        return {"status": "COMPLETED", "fraud_tag_hits": hits, "fraud_tag_terms": matched}


@app.get("/health")
async def health():
    with closing(_db()) as conn:
        rows = conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        used = _used_today(conn)
        detail_used = _used_today(conn, "detail")
    return {
        "ok": True,
        "daily_used": used,
        "daily_limit": DAILY_LIMIT,
        "detail_used_today": detail_used,
        "detail_daily_limit": DETAIL_DAILY_LIMIT,
        "cache_rows": rows,
        "last_status": _last_status,
    }
