"""
Regression corpus — verifikasi fakta kunci sebelum FE (tanpa framework).

Jalankan: .venv311/bin/python3 test_regression.py
Menutup: multi-address, shortlink, scam phone, SSRF, verdict-score,
single-token search, dedup alamat, effective weight SHAP.
"""
import sys
sys.path.insert(0, ".")

def _run(name, fn):
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as e:
        print(f"  FAIL  {name}: {e}")
        raise SystemExit(1)

def test_multi_address():
    from app.services.ner import extract_entities_from_text
    text = """Lowongan Marketing
Alamat: Jl. Sudirman No. 10, Jakarta
Alamat lain: Jl. Sudirman No. 20, Jakarta
Kirim CV ke hrd@mail.com"""
    addrs = extract_entities_from_text(text)["addresses"]
    assert "Jl. Sudirman No. 10, Jakarta" in addrs
    assert "Jl. Sudirman No. 20, Jakarta" in addrs  # nomor rumah beda = jangan dedup
    assert not any("Alamat lain" in a for a in addrs)  # label = hard boundary

def test_cabang_boundary():
    from app.services.ner import extract_entities_from_text
    text = "Kantor: Jl. Malioboro No. 12, Yogyakarta\nCabang: Jl. Kaliurang KM 5, Sleman"
    addrs = extract_entities_from_text(text)["addresses"]
    assert "Jl. Malioboro No. 12, Yogyakarta" in addrs
    assert "Jl. Kaliurang KM 5, Sleman" in addrs
    assert not any("Cabang" in a or "Kantor:" in a for a in addrs)

def test_shortlink_and_scam_phone():
    from app.services.ner import extract_entities_from_text
    text = "Daftar via bit.ly/FormLamaranKerja. WA 085174156091 atau +6285174156091. Bayar biaya Rp 350.000."
    r = extract_entities_from_text(text)
    assert any("bit.ly/FormLamaranKerja" in u for u in r["urls"]), r["urls"]
    assert "+6285174156091" in r["phones"], r["phones"]  # 08... dinormalisasi ke +62...

def test_ssrf_guard():
    from app.services.url_guard import validate_public_http_url
    for bad in ("http://localhost:8000/x", "http://127.0.0.1/x",
                "http://192.168.1.1/x", "http://10.0.0.5/x", "file:///etc/passwd"):
        try:
            validate_public_http_url(bad)
            raise AssertionError(f"harus ditolak: {bad}")
        except ValueError:
            pass
    assert validate_public_http_url("https://example.com/jobs") == "https://example.com/jobs"

def test_verdict_score_contract():
    from app.services.llm.verifin_reasoning import _is_valid_llm_output
    assert _is_valid_llm_output({"verdict": "AMAN", "risk_score": 30, "summary": "aman", "risk_factors": [], "safe_factors": [], "recommendations": []})
    assert not _is_valid_llm_output({"verdict": "AMAN", "risk_score": 90, "summary": "aman", "risk_factors": [], "safe_factors": [], "recommendations": []})
    assert _is_valid_llm_output({"verdict": "BAHAYA", "risk_score": 90, "summary": "bahaya", "risk_factors": [], "safe_factors": [], "recommendations": []})

def test_single_token_search():
    from app.services.osint.web_evidence import _result_matches_query
    assert not _result_matches_query('"Bangor"', "https://news.example/article", "Bangor City", "berita umum")
    assert _result_matches_query('"Bangor"', "https://bangor.example.com", "Welcome", "")

def test_address_dedup_house_number():
    from app.services.ner import _uniq_addresses
    out = _uniq_addresses(["Jl. Sudirman No. 10, Jakarta", "Jl. Sudirman No. 20, Jakarta"])
    assert len(out) == 2

def test_effective_weight_shap():
    from app.services.xai.shap_explainer import explain_verification_shap
    exp = explain_verification_shap(risk_score=20, verdict="AMAN",
                                    osint_results={"phones": [], "domain": {}, "web": {}},
                                    risk_factors=[], safe_factors=[], nlp_result={},
                                    entities={"companies": ["PT X"], "phones": []})
    w = {p["probe"]: p for p in exp["probe_weights"]}
    assert w["Phone Reputation (Kaspersky Who Calls)"]["effective_weight"] == 0.0
    assert w["Web Evidence (SERP)"]["effective_weight"] == 0.20
    assert all("configured_weight" in p and "applicable" in p for p in exp["probe_weights"])

def test_nlp_stub_metadata():
    from app.services.nlp.classifier import classify_text
    meta = classify_text("lowongan")
    assert meta["enabled"] is False and meta["status"] == "STUB"

if __name__ == "__main__":
    print("Regression corpus (wajib sebelum FE):")
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            _run(name, fn)
    print("ALL PASS")
