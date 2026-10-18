import asyncio

from app.api.v1.verify import pipeline
from app.api.v1.verify.pipeline import _extract_entities_hybrid, _is_grounded
from app.services.ner import extract_entities_from_text, is_junk_entity

QHOMEMART = (
    "LOWONGAN KERJA -JOGJA\n"
    "Nama Perusahaan/Usaha: Qhomemart\n"
    "Lokasi: JL.RAYA JANTI No.96 YOGYAKARTA\n"
    "Kirim Lamaran ke: recruitment@qhomemart.co.id\n"
    "No Whatsapp : 0857-0129-9095\n"
    "Punya lowongan kerja dan mau dipromosikan?\n"
    "Hubungi Admin sekarang\n"
    "ADMIN: 085117775180\n"
)


def _run(text, llm_result):
    async def fake_llm(_text):
        return llm_result

    orig = pipeline._run_llm_ner
    pipeline._run_llm_ner = fake_llm
    try:
        return asyncio.run(_extract_entities_hybrid(text))
    finally:
        pipeline._run_llm_ner = orig


def test_regex_reads_company_label_with_slash_and_separates_promoter_phone():
    r = extract_entities_from_text(QHOMEMART)
    assert r["companies"] == ["Qhomemart"]
    assert r["phones"] == ["+6285701299095"]
    assert r["promoter_phones"] == ["+6285117775180"]


def test_regex_location_requires_separator():
    text = "Lokasi Kerja:\nThe Biker Shop Jogja\nBersedia ditempatkan di seluruh jaringan cabang perusahaan"
    assert extract_entities_from_text(text)["location_candidates"] == []


def test_regex_salary_formats():
    sal = extract_entities_from_text("Pagi Rp120rb | Malam Rp130rb/hari. Gaji UMR + bonus. Rp 4.500.000/bulan")["salaries"]
    assert {"Rp120rb", "Rp130rb/hari", "Rp 4.500.000/bulan"} <= set(sal)
    assert any("UMR" in s for s in sal)


def test_fee_amount_is_not_counted_as_salary():
    r = extract_entities_from_text("Wajib transfer biaya seragam Rp150.000 ke rekening admin")
    assert r["salaries"] == []
    assert r["fee_requests"]


def test_grounding_tolerates_ocr_spacing_but_rejects_invented_names():
    assert _is_grounded("PT Indokarya Global Sinergi", "PT.INDOKARYA\nGLOBALSINERGI")
    assert not _is_grounded("PT Maju Sejahtera Abadi", "Kirim CV ke 0896-7951-0296")


def test_hybrid_drops_hallucinated_company_and_junk():
    llm = {
        "companies": ["PT Qhomemart Indonesia Raya"],  # "Indonesia Raya" tidak ada di teks
        "addresses": ["JL.RAYA JANTI No.96 YOGYAKARTA"],
        "location_candidates": ["Kerja", "YOGYAKARTA"],
        "salaries": ["Kompetitif"],
    }
    r = _run(QHOMEMART, llm)
    assert r["companies"] == ["Qhomemart"]  # jatuh ke hasil regex
    assert "PT Qhomemart Indonesia Raya" in r["_ner_meta"]["dropped_ungrounded"]
    assert "Kerja" not in r["location_candidates"] and "YOGYAKARTA" in r["location_candidates"]
    assert r["salaries"] == []
    assert r["_ner_meta"]["validation_applied"] is True


def test_hybrid_prefers_grounded_llm_company():
    r = _run("The Biker Shop membuka lowongan Mekanik Motor. WA 085738325536", {"companies": ["The Biker Shop"]})
    assert r["companies"] == ["The Biker Shop"]
    assert r["_ner_meta"]["source"] == "hybrid_llm_regex"


def test_fallback_without_llm_still_filters_junk():
    r = _run(QHOMEMART, None)
    assert r["_ner_meta"]["source"] == "regex_fallback"
    assert r["companies"] == ["Qhomemart"]
    assert all(not is_junk_entity(v) for v in r["location_candidates"])


def test_hybrid_drops_descriptive_location_and_case_duplicates():
    llm = {"location_candidates": ["seluruh jaringan cabang perusahaan", "PASAR KEMIS", "Pasar Kemis"]}
    r = _run("Lokasi: Pasar Kemis\nBersedia ditempatkan di seluruh jaringan cabang perusahaan", llm)
    assert r["location_candidates"] == ["Pasar Kemis"]


def test_ocr_split_company_name_is_merged_and_logo_acronym_dropped():
    from app.api.v1.verify.pipeline import _merge_company_fragments
    # Urutan baca dari order_text_by_layout: baris kedua logo tepat di bawah baris pertama.
    ocr = "iGS\nLOWONGAN KERJA\n\nPT.INDOKARYA\nGLOBAL SINERGI\nPEOPLESOLUTIONGROWTH\n\nKERJA STABIL"
    assert _merge_company_fragments(["PT.INDOKARYA", "GLOBAL SINERGI", "iGS"], ocr) == ["PT INDOKARYA GLOBAL SINERGI"]


def test_company_fragment_far_away_is_not_merged():
    from app.api.v1.verify.pipeline import _merge_company_fragments
    text = "PT.INDOKARYA\nOPERATOR PACKING\n\nKERJA STABIL\nGLOBAL SINERGI"
    assert _merge_company_fragments(["PT.INDOKARYA", "GLOBAL SINERGI"], text) == ["PT INDOKARYA", "GLOBAL SINERGI"]


def test_separate_companies_are_not_merged():
    from app.api.v1.verify.pipeline import _merge_company_fragments
    text = "Hotel New Saphir Yogyakarta\nAkun IG / Website: New Saphir Hotel Yogyakarta"
    names = ["HOTEL NEW SAPHIR YOGYAKARTA", "New Saphir Hotel Yogyakarta"]
    assert _merge_company_fragments(names, text) == names


def test_company_spelling_variants_are_deduplicated():
    from app.api.v1.verify.pipeline import _dedupe_companies
    names = ["PT pos Indonesia persero", "PT POS INDONESIA", "PT Pos Indonesia (Persero)", "Pertamina Group"]
    assert _dedupe_companies(names) == ["PT Pos Indonesia (Persero)", "Pertamina Group"]
