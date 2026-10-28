"""Masking data pribadi sebelum teks dikirim ke LLM eksternal.

Nomor telepon, bagian lokal email, NIK, dan nomor rekening diganti token (`[NOMOR_1]`,
`[EMAIL_1]@domain.com`, `[NIK_1]`, `[REKENING_1]`). Domain email tetap dikirim karena umur
domain dan SPF/DMARC adalah bukti yang dinilai. Nomor yang sama dalam format berbeda
("0823 2386 3434", "+6282323863434") mendapat token yang sama, sehingga LLM tetap bisa
mencocokkan nomor dengan hasil OSINT-nya. Token di jawaban LLM dikembalikan ke nilai asli
sebelum ditampilkan ke pengguna; nilai asli tidak pernah meninggalkan server.
"""
from __future__ import annotations

import re
from typing import Any

_EMAIL = re.compile(r"\b([A-Za-z0-9._%+-]+)@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)\b")
# Nomor seluler Indonesia; jumlah digit dicek terpisah supaya jam "08.00-20.00" tidak ikut.
_PHONE = re.compile(r"(?<![\w.])(?:\+?62|0)\s?8[\d\s.\-]{7,16}\d(?!\d)")
# NIK boleh ditulis berspasi atau bertitik ("3404 0123 4567 0001").
_NIK = re.compile(r"(?<!\d)(?:\d{4}[\s.]?){3}\d{4}(?!\d)")
_ACCOUNT = re.compile(
    r"(?i)\b((?:no\.?\s*)?rek(?:ening)?\.?(?:\s+(?:bank\s+)?[A-Za-z]{2,10})?|virtual\s*account|va"
    r"|bca|bri|bni|mandiri|bsi|btn|cimb|permata|dana|ovo|gopay|shopeepay"
    r"|seabank|jago|blu|neo\s*bank|line\s*bank|btpn|jenius|allo\s*bank|bank\s*jago)"
    r"\s*[:\-]?\s*((?:\d[\s\-]?){8,18}\d)"
)
# "transfer ke 1234567890", "tf 9012...", "kirim ke rek BCA 123..." tanpa kata "rekening".
_TRANSFER_ACCOUNT = re.compile(
    r"(?i)\b(transfer|tf|kirim(?:kan)?)\s+(?:ke\s+)?(?:(?:rek(?:ening)?|akun|bank)\s+)?(?:[A-Za-z]{2,12}\s+)?((?:\d[\s\-]?){8,18}\d)"
)
# Nama pemilik rekening ("a.n. Budi Santoso", "atas nama: Budi") adalah data pribadi.
_ACCOUNT_NAME = re.compile(
    # Titik atau garis miring wajib: "an" tanpa tanda baca adalah awal kata biasa ("Analis", "Anak").
    r"(?i)\b(a\.\s?n\b\.?|a\s?[/\\]\s?n\b\.?|atas\s+nama)\s*[:\-]?\s*([A-Za-z][A-Za-z.'\-]*(?:\s+[A-Za-z][A-Za-z.'\-]*){0,3})"
)
_TOKEN = re.compile(r"\[(?:NOMOR|EMAIL|NIK|REKENING|NAMA_REK)_\d+\]")


def _canonical_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("62"):
        digits = "0" + digits[2:]
    return digits


class PiiMasker:
    def __init__(self) -> None:
        self._token_of: dict[tuple[str, str], str] = {}
        self._value_of: dict[str, str] = {}
        self._counts: dict[str, int] = {}

    def _token(self, kind: str, key: str, original: str) -> str:
        token = self._token_of.get((kind, key))
        if token is None:
            self._counts[kind] = self._counts.get(kind, 0) + 1
            token = f"[{kind}_{self._counts[kind]}]"
            self._token_of[(kind, key)] = token
            self._value_of[token] = original
        return token

    def mask(self, text: str) -> str:
        if not text:
            return text

        def email(m: re.Match) -> str:
            local, domain = m.group(1), m.group(2)
            return f"{self._token('EMAIL', local.lower(), local)}@{domain}"

        def account(m: re.Match) -> str:
            key = re.sub(r"\D", "", m.group(2))
            return f"{m.group(1)} {self._token('REKENING', key, m.group(2))}"

        def phone(m: re.Match) -> str:
            raw = m.group(0)
            key = _canonical_phone(raw)
            if not 10 <= len(key) <= 13:
                return raw
            return self._token("NOMOR", key, raw.strip())

        def transfer_account(m: re.Match) -> str:
            digits = re.sub(r"\D", "", m.group(2))
            if not 8 <= len(digits) <= 18:
                return m.group(0)
            return f"{m.group(1)} ke {self._token('REKENING', digits, m.group(2))}"

        def account_name(m: re.Match) -> str:
            return f"{m.group(1)} {self._token('NAMA_REK', m.group(2).lower(), m.group(2))}"

        def nik(m: re.Match) -> str:
            digits = re.sub(r"\D", "", m.group(0))
            return self._token("NIK", digits, m.group(0))

        text = _EMAIL.sub(email, text)
        text = _ACCOUNT.sub(account, text)
        text = _TRANSFER_ACCOUNT.sub(transfer_account, text)
        text = _PHONE.sub(phone, text)
        text = _NIK.sub(nik, text)
        text = _ACCOUNT_NAME.sub(account_name, text)
        return text

    def mask_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        masked = []
        for msg in messages:
            content = msg.get("content")
            masked.append({**msg, "content": self.mask(content) if isinstance(content, str) else content})
        return masked

    def unmask(self, text: str) -> str:
        if not text or not self._value_of:
            return text
        return _TOKEN.sub(lambda m: self._value_of.get(m.group(0), m.group(0)), text)

    @property
    def masked_count(self) -> int:
        return len(self._value_of)
