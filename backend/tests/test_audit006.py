"""Regresi untuk temuan audit-006 (20 Okt 2026)."""
import pytest

from app.services.db_cache import _normalize_url_variants
from app.services.case_search import like_escape
from app.services.llm.prompt_builder import _build_network_section
from app.services.llm.verifin_reasoning import (
    _calibrate_unknown_search_output,
    _fallback_analysis,
    _has_corrupt_text,
)
from app.services.ner import extract_entities_from_text
from app.services.nlp.classifier import classify_text
from app.services.osint.address_validator import _house_numbers
from app.services.osint.gform_inspector import is_gform_url
from app.services.osint.search_intelligence import _entity_match_score, resolve_entity
from app.services.osint.web_evidence import _result_matches_query, fetch_company_website
from app.services.url_guard import is_public_http_url, safe_get
from app.services.xai.shap_explainer import explain_verification_shap


# 1 · SSRF
@pytest.mark.parametrize("url", ["http://127.0.0.1:8000/api", "http://localhost/x", "http://10.0.0.5/", "http://169.254.169.254/latest"])
def test_internal_urls_are_rejected(url):
    assert not is_public_http_url(url)
    with pytest.raises(ValueError):
        safe_get(url)


def test_company_website_does_not_fetch_internal_address():
    result = fetch_company_website("http://127.0.0.1:8000/api/v1/health")
    assert result["website_status"] == "SKIPPED"
    assert result["ok"] is False and not result.get("snippet")


# 6 · cache URL
def test_url_variants_keep_post_identifier_and_drop_tracking():
    variants = _normalize_url_variants("https://www.facebook.com/permalink.php?story_fbid=111&id=9&mibextid=x")
    assert all("story_fbid=111" in v for v in variants)
    assert not any(v.endswith("permalink.php") for v in variants)
    assert "https://www.threads.com/@a/post/B" in _normalize_url_variants("https://www.threads.com/@a/post/B?xmt=1")


def test_like_escape():
    assert like_escape("100%_a") == "100\\%\\_a"


# 4 · urutan kata nama perusahaan
def _score(name, url, title):
    e = resolve_entity(name)
    return _entity_match_score(e["tokens"], url, title, "", canonical=e["canonical"], brand=e["brand"] or "")


def test_swapped_company_name_is_a_different_entity():
    assert _score("CV Kreasi Digital Nusantara", "https://id.linkedin.com/company/digital-kreasi-nusantara",
                  "Digital Kreasi Nusantara | LinkedIn") < 0.5
    assert _score("PT Sinar Rejeki Abadi Sentosa", "https://companyhouse.id/x", "PT. Sinar Abadi Rejeki") < 0.5
    assert not _result_matches_query("Kreasi Digital Nusantara", "https://a", "Digital Kreasi Nusantara", "")


def test_same_order_and_brand_short_forms_still_match():
    assert _score("PT Pos Indonesia (Persero)", "https://posindonesia.co.id", "Pos Indonesia Karir") >= 0.5
    assert _score("PT Komitrando Emporio", "https://komitrando.com", "Komitrando - Bag Manufacturer") >= 0.5
    assert _score("Hotel New Saphir", "https://newsaphirhotel.com", "New Saphir Hotel Yogyakarta") >= 0.5


# 9 · shortlink per host
def test_gform_detection_uses_hosts_not_substrings():
    assert is_gform_url("https://forms.gle/abc") and is_gform_url("https://s.id/xyz") and is_gform_url("bit.ly/a")
    assert not is_gform_url("https://glints.id/id/opportunities/jobs/1")
    assert not is_gform_url("https://www.kompas.id/artikel")


# 10 · KM bukan nomor bangunan
def test_kilometer_marker_is_not_house_number():
    assert _house_numbers("Jl. Magelang KM 10, Sleman") == set()
    assert _house_numbers("Jl. Raya Janti No. 96, RT 02") == {"96"}


# 31 · nomor perekrut tidak dibuang karena kata "admin"
def test_recruiter_phone_kept_when_line_mentions_admin_position():
    e = extract_entities_from_text("Lowongan Admin Gudang PT Maju. Kirim CV via WA 081322114455.")
    assert e["phones"] == ["+6281322114455"]


def test_promoter_phone_still_separated():
    e = extract_entities_from_text("Mau pasang loker? Hubungi 081299998888. Lowongan staf gudang: WA 081322114455")
    assert e["phones"] == ["+6281322114455"] and e["promoter_phones"] == ["+6281299998888"]


# 32 · tautan tanpa skema
def test_schemeless_links_are_extracted():
    e = extract_entities_from_text("Daftar di bit.ly/rekrut2026 atau forms.gle/AbC123. Email hrd@maju.co.id")
    assert "https://bit.ly/rekrut2026" in e["urls"] and "https://forms.gle/AbC123" in e["urls"]
    assert not any("maju.co.id" in u for u in e["urls"])


# 33 · negasi biaya
def test_free_recruitment_statement_is_not_fee_request():
    r = classify_text("PT Maju membuka lowongan. Proses rekrutmen tidak dipungut biaya pendaftaran apapun.")
    assert r["behavioral_features"]["has_fee_request"] is False
    assert extract_entities_from_text("Tidak dipungut biaya. Gaji Rp4.000.000/bulan")["salaries"] == ["Rp4.000.000/bulan"]


def test_real_fee_request_still_detected():
    assert classify_text("Wajib bayar biaya pendaftaran 150rb via DANA")["behavioral_features"]["has_fee_request"]


# 38 · negara tujuan
def test_common_migrant_destinations_are_foreign_work():
    for t in ("Kerja di Jepang program magang", "Lowongan TKI Malaysia dan Taiwan"):
        assert classify_text(t)["behavioral_features"]["has_foreign_work"]


# 5 · kalibrasi tidak boleh menurunkan permintaan biaya
def test_calibration_keeps_fee_request_dangerous():
    osint = {"web": {"searches": [{"status": "NO_RESULTS"}], "evidence_counts": {}}, "social": {"evidence_counts": {}}, "phones": []}
    llm = {"verdict": "BAHAYA", "risk_score": 85, "summary": "x", "risk_factors": [], "safe_factors": [], "recommendations": []}
    out = _calibrate_unknown_search_output(dict(llm), {}, osint, {"has_fee_request": True})
    assert out["verdict"] == "BAHAYA" and out["risk_score"] == 85


def test_fallback_uses_text_signals_and_does_not_invent_kaspersky_check():
    fb = _fallback_analysis({}, {"phones": []}, text_signals={"has_fee_request": True})
    assert fb["verdict"] == "BAHAYA"
    assert not any("Kaspersky" in f for f in fb["safe_factors"])


# 26 · domain/email bukan teks rusak
def test_domains_are_not_corrupt_text():
    assert not _has_corrupt_text("Email kontak memakai gmail.com, bukan domain perusahaan.")
    assert _has_corrupt_text("Kalimat,rusak tanpa spasi")


# 16 · artikel bantahan punya baris sendiri di XAI
def test_impersonation_warning_has_its_own_contribution():
    shap = explain_verification_shap(
        risk_score=60, verdict="WASPADA",
        osint_results={"web": {"scam_check": {"warnings": 3}}},
        risk_factors=[], safe_factors=[],
    )
    assert any(c["feature_key"] == "impersonation_warning" for c in shap["feature_contributions"])


# 34 · riwayat & laporan komunitas masuk ke prompt
def test_network_section_reports_approved_community_reports():
    text = _build_network_section({"status": "COMPLETED", "community_reports": {"report_count": 2}, "fraud_case_count": 1, "total_case_count": 3})
    assert "SUDAH DISETUJUI admin untuk nomor/email/nama/URL ini: 2" in text
    assert "1 di antaranya berverdict BAHAYA" in text


# Run 9: "Kirim CV terbaik Anda" bukan badan usaha; wilayah non-tempat tidak dipetakan
def test_cv_as_resume_is_not_a_company():
    assert extract_entities_from_text("Kirim CV terbaik Anda ke email hrd@x.com")["companies"] == []
    assert extract_entities_from_text("CV Sinar Jaya membuka lowongan")["companies"] == ["CV. Sinar Jaya"]


def test_country_or_company_phrases_are_not_places():
    from app.services.osint.runner import _NOT_A_PLACE
    assert _NOT_A_PLACE.search("Indonesia") and _NOT_A_PLACE.search("Wilayah Kerja PT. Pos Indonesia (Persero)")
    assert not _NOT_A_PLACE.search("Jakarta Selatan")


def test_recruiting_line_keeps_phone_even_if_line_above_mentions_admin_group():
    text = "Bawa bukti pembayaran dari admin grup.\nKonfirmasi kehadiran via WhatsApp +62 822-2133-3836"
    e = extract_entities_from_text(text)
    assert e["phones"] == ["+6282221333836"] and e["promoter_phones"] == []


def test_foreign_work_location_is_not_geocoded_in_indonesia():
    import re
    from app.services.osint.runner import _mappable_places

    non_geo = re.compile(r"^remote$", re.I)
    # Poster: OCR memisahkan "JAPAN" dan "Osaka"; Osaka tidak boleh dicari di peta Indonesia.
    assert _mappable_places(["JAPAN", "Osaka"], "location_candidate", non_geo) == ([], ["JAPAN"])
    # Alamat fisik yang tertulis tetap dipetakan walau lowongan menyebut kerja di Jepang.
    places, foreign = _mappable_places(["Jl. Ahmad Yani No. 5, Bekasi", "Jepang"], "posting_address", non_geo)
    assert places == ["Jl. Ahmad Yani No. 5, Bekasi"] and foreign == ["Jepang"]
    assert _mappable_places(["Sleman"], "location_candidate", non_geo) == (["Sleman"], [])
