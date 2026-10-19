from app.services.llm.verifin_reasoning import _soften_summary_claims


def test_removes_official_claim_from_summary():
    text = "Lowongan resmi dengan domain email korporat terverifikasi dan jejak digital konsisten."
    out = _soften_summary_claims(text)
    assert "resmi" not in out.lower()
    assert "terverifikasi" not in out.lower()
    assert out.startswith("Lowongan dengan domain email korporat")


def test_keeps_risk_summary_untouched():
    text = "Nomor terindikasi penipuan dan lowongan meminta biaya seleksi."
    assert _soften_summary_claims(text) == text


def test_removes_credibility_and_official_domain_claims():
    text = "Lowongan sangat kredibel menggunakan domain resmi berusia lebih dari 13 tahun tanpa indikasi pungutan biaya."
    out = _soften_summary_claims(text)
    assert out == "Lowongan menggunakan domain berusia lebih dari 13 tahun tanpa indikasi pungutan biaya."
