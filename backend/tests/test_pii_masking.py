import asyncio
import json

import httpx

from app.services.pii import PiiMasker


def test_phone_formats_share_one_token_and_times_are_untouched():
    m = PiiMasker()
    out = m.mask("WA 0823 2386 3434 atau +6282323863434. Jam kerja 08.00-20.00 WIB")
    assert out == "WA [NOMOR_1] atau [NOMOR_1]. Jam kerja 08.00-20.00 WIB"


def test_email_keeps_domain_for_domain_evidence():
    m = PiiMasker()
    assert m.mask("Kirim ke hrm@newsaphirhotel.com") == "Kirim ke [EMAIL_1]@newsaphirhotel.com"


def test_nik_and_bank_account_are_masked():
    m = PiiMasker()
    out = m.mask("NIK 3404011234567890, transfer ke rek BCA 1234567890 a.n. Budi")
    assert "3404011234567890" not in out and "1234567890" not in out
    assert "[NIK_1]" in out and "[REKENING_1]" in out


def test_salary_and_dates_are_not_masked():
    text = "Gaji Rp4.500.000, tes 02-03-2026, kode pos 10110"
    assert PiiMasker().mask(text) == text


def test_unmask_restores_original_values():
    m = PiiMasker()
    masked = m.mask("Hubungi 0896-7951-0296")
    assert m.unmask(f"Nomor {masked[8:]} bersih") == "Nomor 0896-7951-0296 bersih"


def test_chat_completion_never_sends_raw_pii(monkeypatch):
    from app.services.llm import client

    sent = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent["body"] = request.content.decode()
        body = json.loads(sent["body"])
        token = "[NOMOR_1]" if "[NOMOR_1]" in body["messages"][0]["content"] else "?"
        return httpx.Response(200, json={"choices": [{"message": {"content": f"Nomor {token} bersih"}}]})

    transport = httpx.MockTransport(handler)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(client, "LLM_API_KEY", "test")
    # CI tidak punya .env; tanpa base URL request jadi "/chat/completions" dan ditolak httpx.
    monkeypatch.setattr(client, "LLM_BASE_URL", "http://llm.test/v1")
    monkeypatch.setattr(client.httpx, "AsyncClient", lambda **kw: real_client(transport=transport))
    reply = asyncio.run(client.chat_completion([{"role": "user", "content": "WA 0812-3456-7890, email budi@gmail.com"}]))
    assert "0812-3456-7890" not in sent["body"] and "budi@" not in sent["body"]
    assert "gmail.com" in sent["body"]
    assert reply == "Nomor 0812-3456-7890 bersih"
