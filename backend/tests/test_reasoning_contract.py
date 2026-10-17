import pytest
from app.services.llm.verifin_reasoning import (
    _is_valid_llm_output,
    _sanitize_llm_output,
    _fallback_analysis,
)


class TestVerdictScoreContract:
    def test_aman_valid_score_range(self):
        valid_aman = {
            "verdict": "AMAN",
            "risk_score": 25,
            "summary": "Lowongan terverifikasi aman.",
            "risk_factors": [],
            "safe_factors": ["Perusahaan terdaftar resmi"],
            "recommendations": ["Tetap waspada"],
        }
        assert _is_valid_llm_output(valid_aman) is True

    def test_aman_invalid_high_score_rejected(self):
        invalid_aman = {
            "verdict": "AMAN",
            "risk_score": 65,  # Score > 39 violates AMAN contract
            "summary": "Lowongan aman tapi skor tinggi",
            "risk_factors": [],
            "safe_factors": [],
            "recommendations": [],
        }
        assert _is_valid_llm_output(invalid_aman) is False

    def test_waspada_valid_and_invalid_scores(self):
        valid_waspada = {
            "verdict": "WASPADA",
            "risk_score": 55,
            "summary": "Informasi lowongan minim identitas.",
            "risk_factors": ["Alamat tidak terverifikasi"],
            "safe_factors": [],
            "recommendations": ["Konfirmasi ke kantor cabang"],
        }
        assert _is_valid_llm_output(valid_waspada) is True

        invalid_waspada_low = {**valid_waspada, "risk_score": 20}
        assert _is_valid_llm_output(invalid_waspada_low) is False

        invalid_waspada_high = {**valid_waspada, "risk_score": 85}
        assert _is_valid_llm_output(invalid_waspada_high) is False

    def test_bahaya_valid_and_invalid_scores(self):
        valid_bahaya = {
            "verdict": "BAHAYA",
            "risk_score": 90,
            "summary": "Terindikasi kuat sindikat penipuan tenaga kerja.",
            "risk_factors": ["Permintaan transfer uang muka"],
            "safe_factors": [],
            "recommendations": ["Jangan transfer uang"],
        }
        assert _is_valid_llm_output(valid_bahaya) is True

        invalid_bahaya_low = {**valid_bahaya, "risk_score": 30}
        assert _is_valid_llm_output(invalid_bahaya_low) is False

    def test_corrupt_or_truncated_text_rejected(self):
        corrupt_output = {
            "verdict": "AMAN",
            "risk_score": 10,
            "summary": "abcdefghijklmnopqrstuvwxyz1234567890",  # Single 36-char word without spaces
            "risk_factors": [],
            "safe_factors": [],
            "recommendations": [],
        }
        assert _is_valid_llm_output(corrupt_output) is False


class TestAntiHallucinationSanitizer:
    def test_sanitizes_unfounded_official_claims(self):
        raw_output = {
            "verdict": "AMAN",
            "risk_score": 15,
            "summary": "Website resmi dan Toko resmi terverifikasi.",
            "risk_factors": [],
            "safe_factors": ["Akun resmi Instagram aktif"],
            "recommendations": ["Kunjungi website resmi"],
        }
        entities = {"companies": ["PT Contoh"]}
        osint_results = {}
        sanitized = _sanitize_llm_output(raw_output, entities, osint_results)

        # "resmi" claims should be downgraded to objective "publik" phrasing
        assert "Website resmi" not in sanitized["summary"]
        assert "Website publik" in sanitized["summary"]
        assert "Toko resmi" not in sanitized["summary"]
        assert "Akun publik" in sanitized["safe_factors"][0]

    def test_evidence_fallback_structure(self):
        entities = {"companies": ["PT Fiktif"], "phones": ["081234567890"]}
        osint_results = {"phones": [{"reported_fraud": True}]}
        fb = _fallback_analysis(entities, osint_results)
        assert fb["verdict"] in ("AMAN", "WASPADA", "BAHAYA")
        assert 0 <= fb["risk_score"] <= 100
        assert "model_used" in fb
        assert "Fallback" in fb["model_used"]
