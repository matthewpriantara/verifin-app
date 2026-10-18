from app.services.llm.prompt_builder import build_text_verify_prompt
from app.services.nlp.classifier import extract_behavioral_features as features

T2 = (
    "PABRIK BARU DI PASAR KEMIS LAGI BUKA LOWONGAN!\n"
    "Pagi Rp120rb | Malam Rp130rb/hari\nLokasi: Pasar Kemis, Tangerang\nKirim CV: 0896-7951-0296"
)


def test_kirim_cv_is_not_read_as_a_cv_company():
    f = features(T2)
    assert f["has_company"] is False
    assert f["salary_no_company"] is True
    assert f["anonymous_employer_claim"] is True
    assert f["has_whatsapp_apply"] is True


def test_named_legal_entities_are_recognised():
    assert features("CV. Sinar Abadi butuh admin, kirim CV ke email")["has_company"] is True
    assert features("PT Maju Jaya membuka lowongan")["has_company"] is True
    assert features("Nama Perusahaan/Usaha: HOTEL NEW SAPHIR")["has_company"] is True
    assert features("Kirim CV terbaru dan KTP ke WA 0812")["has_company"] is False


def test_ner_company_counts_as_named_employer():
    f = features("Perusahaan kami butuh staf, gaji Rp3jt", companies=["Hotel New Saphir"])
    assert f["has_company"] is True
    assert f["anonymous_employer_claim"] is False


def test_street_abbreviation_counts_as_address():
    assert features("Lokasi: Jl. Laksda Adisucipto No. 38")["has_address"] is True


def test_small_shop_is_not_an_anonymous_employer():
    assert features("Toko kami butuh kasir, WA 0812-1111-2222")["anonymous_employer_claim"] is False


def test_text_signals_reach_the_llm_prompt():
    prompt = build_text_verify_prompt(T2, {}, {}, features(T2))
    assert "## SINYAL TEKS" in prompt
    assert "Mengaku pabrik/perusahaan/kantor tetapi tidak menyebut namanya: YA" in prompt


POS = (
    "Dibuka lowongan kerja PT pos Indonesia persero (2026)\n"
    "Posisi jabatan, kualifikasi, penempatan, dan cara pendaftaran silakan WhatsApp admin\n"
    "DAFTAR MELALUI LINK YANG ADA DIBIO GRATIS!"
)


def test_bumn_name_with_whatsapp_only_channel_is_flagged():
    f = features(POS)
    assert f["has_whatsapp_apply"] is True
    assert f["brand_unofficial_channel"] is True


def test_bumn_name_is_not_a_safe_keyword():
    assert features("PT Contoh (Persero) Tbk membuka lowongan")["safe_keyword_count"] == 0


def test_bumn_with_official_portal_is_not_flagged():
    text = "PT Pos Indonesia (Persero) membuka lowongan. Daftar di https://posindonesia.rakamin.com"
    assert features(text)["brand_unofficial_channel"] is False
