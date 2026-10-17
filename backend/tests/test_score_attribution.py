from types import SimpleNamespace

import pytest

from app.api.v1.verify.pipeline import _to_response, attach_shap_explanation
from app.services.db_cache import _save_case_to_db
from app.services.osint.phone_validator import _parse_kaspersky_page
from app.services.xai.shap_explainer import explain_verification_shap


def _total(exp: dict) -> float:
    return exp["base_value"] + sum(c["delta"] for c in exp["feature_contributions"])


# Bentuk data mengikuti respons uji 17 Okt 2026 (laporan-uji-17-okt-2026.md bagian 3A).
SCAM_NLP = {
    "enabled": True,
    "behavioral_features": {"has_fee_request": True, "fraud_keyword_count": 1},
}
SCAM_OSINT = {
    "domain": {"skipped": "free_email"},
    "email_security": {"skipped": "free_email"},
    "companies": [{"name": "PT Sejagat Energi Tbk", "stats": {"public_mentions": 3}}],
    "web": {"evidence_counts": {"relevant_results": 10}},
}
BIKER_OSINT = {
    "domain": {"skipped": "free_email"},
    "email_security": {"skipped": "free_email"},
    "companies": [{"name": "The Biker Shop", "stats": {"public_mentions": 10}}],
    "web": {"evidence_counts": {"relevant_results": 10}},
    "phones": [{"phone": "+6285738325536", "probe_status": "COMPLETED", "reputation_status": "CLEAN"}],
}
BIKER_ENTITIES = {
    "companies": ["The Biker Shop"],
    "emails": ["hrdthebikershop@gmail.com"],
    "phones": ["+6285738325536"],
    "addresses": ["Jl. Parangtritis No.38, Mantrijeron, Kota Jogja"],
}
BIKER_NETWORK = {
    "status": "COMPLETED",
    "entity_in_fraud_network": False,
    "fraud_case_count": 0,
    "total_case_count": 4,
    "community_reports": {"status": "COMPLETED", "report_count": 0, "pending_report_count": 0},
}


class TestScoreEqualsBasePlusContributions:
    @pytest.mark.parametrize("risk_score", [95, 85, 58, 12, 0, 100])
    def test_scam_case_sums_to_final_score(self, risk_score):
        exp = explain_verification_shap(
            risk_score=risk_score,
            verdict="BAHAYA",
            osint_results=SCAM_OSINT,
            risk_factors=[],
            safe_factors=[],
            nlp_result=SCAM_NLP,
            entities={"companies": ["PT Sejagat Energi Tbk"], "emails": ["hrd@gmail.com"]},
        )
        assert _total(exp) == pytest.approx(risk_score, abs=0.01)
        assert exp["final_risk_score"] == risk_score

    def test_evidence_weights_not_rescaled(self):
        exp = explain_verification_shap(
            risk_score=95, verdict="BAHAYA", osint_results=SCAM_OSINT,
            risk_factors=[], safe_factors=[], nlp_result=SCAM_NLP,
            entities={"companies": ["PT Sejagat Energi Tbk"]},
        )
        by_key = {c["feature_key"]: c for c in exp["feature_contributions"]}
        assert by_key["has_fee_request"]["contribution"] == 40.0
        assert by_key["free_email_only"]["contribution"] == 8.0
        calibration = by_key["model_calibration"]
        assert calibration["delta"] == pytest.approx(exp["calibration_delta"])
        assert calibration["delta"] == pytest.approx(95 - 12 - exp["evidence_delta"])

    def test_biker_shop_sums_to_final_score(self):
        exp = explain_verification_shap(
            risk_score=12, verdict="AMAN", osint_results=BIKER_OSINT,
            risk_factors=[], safe_factors=[], nlp_result=None,
            network_context=BIKER_NETWORK, entities=BIKER_ENTITIES,
        )
        assert _total(exp) == pytest.approx(12, abs=0.01)
        calibration = next(c for c in exp["feature_contributions"] if c["feature_key"] == "model_calibration")
        assert calibration["impact"] == "safe"

    def test_no_calibration_when_evidence_already_matches(self):
        exp = explain_verification_shap(
            risk_score=20, verdict="AMAN",
            osint_results={"domain": {"skipped": "free_email"}, "email_security": {"skipped": "free_email"}},
            risk_factors=[], safe_factors=[], nlp_result=None, entities=None,
        )
        assert [c["feature_key"] for c in exp["feature_contributions"]] == ["free_email_only"]
        assert exp["calibration_delta"] == 0
        assert exp["waterfall_chart"][-1]["cumulative"] == 20


class TestFraudNetworkFeature:
    def test_inactive_when_zero_fraud_cases(self):
        # Kasus 17 Okt: flag True dari laporan komunitas, padahal 0 kasus BAHAYA.
        ctx = {**BIKER_NETWORK, "entity_in_fraud_network": True, "fraud_case_count": 0}
        exp = explain_verification_shap(
            risk_score=12, verdict="AMAN", osint_results=BIKER_OSINT,
            risk_factors=[], safe_factors=[], network_context=ctx, entities=BIKER_ENTITIES,
        )
        keys = [c["feature_key"] for c in exp["feature_contributions"]]
        assert "entity_in_fraud_network" not in keys
        step = next(s for s in exp["decision_path"] if "Fraud Network" in s["step"])
        assert step["status"] != "FLAG"

    def test_active_with_real_fraud_cases(self):
        ctx = {"status": "COMPLETED", "entity_in_fraud_network": True, "fraud_case_count": 2, "total_case_count": 3}
        exp = explain_verification_shap(
            risk_score=90, verdict="BAHAYA", osint_results={}, risk_factors=[], safe_factors=[],
            network_context=ctx, entities={},
        )
        contrib = next(c for c in exp["feature_contributions"] if c["feature_key"] == "entity_in_fraud_network")
        assert "2 kasus" in contrib["description"]

    def test_approved_community_reports_are_separate_feature(self):
        ctx = {
            "status": "COMPLETED", "entity_in_fraud_network": False, "fraud_case_count": 0,
            "community_reports": {"status": "COMPLETED", "report_count": 2},
        }
        exp = explain_verification_shap(
            risk_score=60, verdict="WASPADA", osint_results={}, risk_factors=[], safe_factors=[],
            network_context=ctx, entities={},
        )
        keys = [c["feature_key"] for c in exp["feature_contributions"]]
        assert "community_reported" in keys
        assert "entity_in_fraud_network" not in keys


class TestShapPersisted:
    def test_shap_saved_to_db_payload(self):
        saved = {}

        class FakeQuery:
            def filter(self, *a, **k):
                return self

            def first(self):
                return None

        class FakeSession:
            def query(self, *a, **k):
                return FakeQuery()

            def add(self, obj):
                obj.id = "00000000-0000-0000-0000-000000000001"
                saved["case"] = obj

            def commit(self):
                pass

            def rollback(self):
                pass

        analysis = {"verdict": "AMAN", "risk_score": 12, "summary": "ok", "network_context": BIKER_NETWORK}
        attach_shap_explanation(analysis, BIKER_ENTITIES, BIKER_OSINT)
        status = _save_case_to_db(FakeSession(), "teks", analysis, BIKER_OSINT, entities=BIKER_ENTITIES)

        assert status["status"] == "SAVED"
        stored = saved["case"].llm_output["shap_explanation"]
        assert stored is not None
        assert _total(stored) == pytest.approx(12, abs=0.01)

        response = _to_response(analysis, BIKER_ENTITIES, dict(BIKER_OSINT))
        assert response.shap_explanation == stored


class _FakeEl(SimpleNamespace):
    def get_all_text(self, strip=True):
        return self.text


class _FakeList(list):
    @property
    def first(self):
        return self[0] if self else None


class _FakePage:
    def __init__(self, verdict, comments=()):
        self.verdict = verdict
        self.comments = comments

    def css(self, selector):
        if "NumberInfoWrapper_title" in selector:
            return _FakeList([_FakeEl(text=self.verdict)] if self.verdict is not None else [])
        return _FakeList(_FakeEl(text=c) for c in self.comments)


def _base_result():
    return {"checked": False, "probe_status": "UNAVAILABLE", "reputation_status": "UNAVAILABLE",
            "scam_confirmed": False, "risk_flags": []}


class TestKasperskyParser:
    def test_netral_is_clean_and_completed(self):
        page = _FakePage("NETRAL", ["Coba Kaspersky Who Calls secara gratis.\nTidak ada laporan spam."])
        r = _parse_kaspersky_page(page, _base_result())
        assert r["probe_status"] == "COMPLETED"
        assert r["reputation_status"] == "CLEAN"
        assert r["comments"] == ["Tidak ada laporan spam."]

    def test_spam_is_flagged(self):
        r = _parse_kaspersky_page(_FakePage("SPAM"), _base_result())
        assert r["reputation_status"] == "FLAGGED"
        assert r["scam_confirmed"] is True

    def test_missing_verdict_element_stays_unavailable(self):
        r = _parse_kaspersky_page(_FakePage(None), _base_result())
        assert r["probe_status"] == "UNAVAILABLE"
        assert r["checked"] is False
        assert "error" in r
