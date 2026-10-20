"""Kevalidan data OSINT (audit-003): cache, label sumber, peta, dan prompt alamat."""
from app.api.v1.verify.pipeline import _dedupe_salaries
from app.services.db_cache import _case_hash, _osint_has_failures
from app.services.llm.prompt_builder import _build_address_osint_section
from app.services.llm.verifin_reasoning import _mark_social_link_status
from app.services.osint.address_validator import _is_business_match, _plain_display_name, _business_tokens
from app.services.osint.search_intelligence import _url_key, classify_result


def test_case_hash_ignores_trailing_and_repeated_whitespace():
    text = "LOWONGAN PT X\nKontak: 0812"
    assert _case_hash(text) == _case_hash(text + "\n")
    assert _case_hash(text) == _case_hash("LOWONGAN  PT X \n Kontak: 0812")


def test_unavailable_web_search_marks_osint_failed():
    osint = {"web": {"searches": [{"status": "UNAVAILABLE"}]}}
    assert _osint_has_failures(osint)
    assert not _osint_has_failures({"web": {"searches": [{"status": "FOUND"}]}})


def test_salary_duplicates_with_plus_minus_are_merged():
    values = ["Rp3.500.000–Rp4.500.000", "± Rp3.500.000–Rp4.500.000", "Rp3.000.000–Rp4.000.000"]
    assert _dedupe_salaries(values) == ["Rp3.500.000–Rp4.500.000", "Rp3.000.000–Rp4.000.000"]


def test_official_only_when_domain_matches_posting():
    assert classify_result("https://www.komitrando.com/", "KOMITRANDO", "", ("komitrando.com",)) == "official"
    # Agregator dengan kata "contact" bukan situs resmi
    assert classify_result("https://panjiva.com/PT-Komitrando", "Komitrando contact", "", ("komitrando.com",)) == "web"


def test_language_variants_share_url_key():
    a = "https://www.booking.com/hotel/id/saphir-yogyakarta.id.html"
    b = "https://www.booking.com/hotel/id/saphir-yogyakarta.html"
    assert _url_key(a) == _url_key(b)


def test_business_poi_match_and_plain_display():
    tokens = _business_tokens("PT KOMITRANDO EMPORIO")
    assert _is_business_match({"name": "Komitrando"}, tokens)
    poi = {
        "name": "De Britto",
        "display_name": "De Britto, Jalan Laksda Adisucipto, Catur Tunggal, Sleman",
        "address": {"road": "Jalan Laksda Adisucipto"},
    }
    assert _plain_display_name(poi) == "Jalan Laksda Adisucipto, Catur Tunggal, Sleman"


def test_area_match_never_claims_street_confirmed():
    section = _build_address_osint_section([{
        "address_input": "Gedung Perwira Jl. Merdeka Timur, Jakarta Pusat 10110",
        "address_found": True,
        "address_details": {"match_level": "area", "display_name": "Gambir, Jakarta Pusat, 10110"},
    }])
    assert "street_match=false" in section
    assert "✅" not in section


def test_profiles_found_by_name_only_are_flagged():
    osint = {"social": {"profiles": [{"url": "https://instagram.com/posindonesia"}]}}
    _mark_social_link_status(osint, {"urls": []}, "Daftar lewat link di bio", {})
    assert osint["social"]["found_by_name_only"] is True
    osint = {"social": {"profiles": [{"url": "https://instagram.com/tokoku"}]}}
    _mark_social_link_status(osint, {"urls": []}, "Info: IG @tokoku", {})
    assert osint["social"]["found_by_name_only"] is False
