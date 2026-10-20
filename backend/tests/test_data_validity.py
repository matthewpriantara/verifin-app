"""Kevalidan data OSINT (audit-003): cache, label sumber, peta, dan prompt alamat."""
from app.api.v1.verify.pipeline import _dedupe_salaries
from app.services.db_cache import _case_hash, _osint_has_failures
from app.services.llm.prompt_builder import _build_address_osint_section
from app.services.llm.verifin_reasoning import _mark_social_link_status
from app.services.osint.address_validator import _area_display_name, _is_business_match, _plain_display_name, _business_tokens
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
    komitrando = {"name": "Komitrando", "class": "shop",
                  "display_name": "Komitrando, Potorono, Bantul, Daerah Istimewa Yogyakarta, Indonesia"}
    assert _is_business_match(komitrando, tokens, "Jalan Wonosari Km 8, Potorono, Banguntapan, Kabupaten Bantul")
    # Jalan di kota lain yang kebetulan memuat nama merek bukan tempat usahanya
    road = {"name": "Jalan Batu Saphir", "class": "highway",
            "display_name": "Jalan Batu Saphir, Kayu Putih, Pulo Gadung, Jakarta Timur"}
    assert not _is_business_match(road, _business_tokens("HOTEL NEW SAPHIR YOGYAKARTA"),
                                  "Jl. Laksda Adisucipto No. 38, Yogyakarta")
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


def test_area_display_shows_region_only():
    result = {
        "display_name": "Jalan Haji Mohammad Saleh Ishak, RW 05, Gondangdia, Menteng, Jakarta Pusat, 10350",
        "address": {"road": "Jalan Haji Mohammad Saleh Ishak", "suburb": "Gondangdia",
                    "city_district": "Menteng", "city": "Jakarta Pusat", "postcode": "10350"},
    }
    assert _area_display_name(result) == "Gondangdia, Menteng, Jakarta Pusat, 10350"


def test_scam_check_ignores_generic_disclaimers(monkeypatch):
    from app.services.osint import search_intelligence as si
    import app.services.osint.searxng_client as sx

    results = [
        {"url": "https://arest.web.id/content/lowongan-hr-generalist-di-pt-komitrando-emporio",
         "title": "Lowongan HR Generalist di PT Komitrando Emporio Penempatan Bantul",
         "snippet": "Berkenaan dengan kian maraknya modus penipuan penerimaan calon tenaga kerja, kami mengingatkan pelamar."},
        {"url": "https://www.komdigi.go.id/berita/hoaks-lowongan-komitrando",
         "title": "[HOAKS] Lowongan Kerja Komitrando Emporio", "snippet": "Lowongan kerja palsu."},
        {"url": "https://careers.example.com/komitrando",
         "title": "Komitrando Careers",
         "snippet": "Waspada penipuan rekrutmen yang mengatasnamakan PT Komitrando Emporio, seleksi kerja tanpa biaya."},
    ]
    monkeypatch.setattr(sx, "is_searxng_available", lambda: True)
    monkeypatch.setattr(sx, "searxng_search", lambda q, max_results=15: {"ok": True, "results": results})
    out = si.scam_report_search("PT KOMITRANDO EMPORIO")
    urls = [r["url"] for r in out["results"]]
    assert "https://arest.web.id/content/lowongan-hr-generalist-di-pt-komitrando-emporio" not in urls
    assert len(urls) == 2


def test_legal_form_in_parentheses_is_not_brand():
    from app.services.osint.search_intelligence import resolve_entity

    pos = resolve_entity("PT Pos Indonesia (Persero)")
    assert pos["brand"] is None
    assert pos["canonical"] == "Pos Indonesia"
    assert pos["search_names"][0] == "Pos Indonesia"
    assert resolve_entity("PT Pertamina (Persero) Tbk")["canonical"] == "Pertamina"
    assert resolve_entity("Anugrah Argon Medica (AAM)")["brand"] == "AAM"
