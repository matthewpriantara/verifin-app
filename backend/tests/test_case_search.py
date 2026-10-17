from types import SimpleNamespace

from app.services.case_search import canonical_phone, classify_query, display_company, summarize


def test_classify_query_detects_each_kind():
    assert classify_query("https://www.threads.com/@hrd/post/abc") == "url"
    assert classify_query("www.instagram.com/p/xyz") == "url"
    assert classify_query("hrd.cuanrebahan@gmail.com") == "email"
    assert classify_query("0812-3456-7890") == "phone"
    assert classify_query("+62 812 3456 7890") == "phone"
    assert classify_query("PT Cuan Rebahan") == "company"


def test_classify_query_rejects_too_short_input():
    assert classify_query("") is None
    assert classify_query("pt") is None
    # 5 digit terlalu pendek untuk nomor; diperlakukan sebagai nama, bukan nomor
    assert classify_query("12345") == "company"


def test_canonical_phone_strips_country_and_trunk_prefix():
    assert canonical_phone("+62 812-3456-7890") == "81234567890"
    assert canonical_phone("081234567890") == "81234567890"
    assert canonical_phone("6281234567890") == "81234567890"


def _case(**kw):
    base = dict(
        id="c1", company_name="PT A", llm_output=None, source="text", verdict="AMAN",
        risk_score=12, osint_failed=False, created_at=None,
        raw_text_preview="Hubungi 0812...", phones=["+6281234567890"], emails=["a@b.com"],
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_display_company_prefers_llm_correction():
    assert display_company(_case(llm_output={"corrected_company_name": "PT Asli"})) == "PT Asli"
    assert display_company(_case(llm_output={"corrected_company_name": "  "})) == "PT A"


def test_summary_never_leaks_raw_text_phone_or_email():
    s = summarize(_case(), "company")
    assert set(s) == {"id", "company_name", "source", "verdict", "risk_score", "osint_failed", "matched_on", "created_at"}
    assert "0812" not in str(s) and "a@b.com" not in str(s)
