import pytest
from app.services.xai.shap_explainer import explain_verification_shap


class TestXAIShapExplainer:
    def test_effective_weight_zero_when_probe_inapplicable(self):
        exp = explain_verification_shap(
            risk_score=20,
            verdict="AMAN",
            osint_results={"phones": [], "domain": {}, "web": {}},
            risk_factors=[],
            safe_factors=[],
            nlp_result={},
            entities={"companies": ["PT X"], "phones": []},
        )
        weights_by_name = {p["probe"]: p for p in exp["probe_weights"]}
        # Inapplicable probe (no phones provided) gets 0.0 effective weight
        phone_weight = weights_by_name["Phone Reputation (Kaspersky Who Calls)"]
        assert phone_weight["effective_weight"] == 0.0
        assert phone_weight["applicable"] is False
        assert phone_weight["configured_weight"] > 0.0

    def test_configured_vs_effective_weight_consistency(self):
        exp = explain_verification_shap(
            risk_score=20,
            verdict="AMAN",
            osint_results={
                "phones": [{"phone": "+6281234567890", "reported_fraud": False}],
                "domain": {"domain": "bca.co.id", "age_years": 15},
                "email_security": {"spf_active": True, "dmarc_active": True},
                "web": {"safe_flags": ["Official site"]},
            },
            risk_factors=[],
            safe_factors=["Terdaftar resmi"],
            nlp_result={},
            entities={"companies": ["PT Bank Central Asia"], "phones": ["+6281234567890"]},
        )
        assert all("configured_weight" in p for p in exp["probe_weights"])
        assert all("effective_weight" in p for p in exp["probe_weights"])
        assert all("applicable" in p for p in exp["probe_weights"])

    def test_shap_metadata_and_dns_records(self):
        exp = explain_verification_shap(
            risk_score=10,
            verdict="AMAN",
            osint_results={
                "phones": [],
                "domain": {"domain": "esthygroup.com"},
                "email_security": {"spf_active": True, "dmarc_active": True},
                "web": {},
            },
            risk_factors=[],
            safe_factors=[],
            nlp_result={},
            entities={"companies": ["Esthy Group"]},
        )
        assert "dns_records" in exp
        assert "not_verified" in exp
        assert len(exp["not_verified"]) >= 3
        assert exp["dns_records"]["spf_active"] is True
        assert exp["dns_records"]["dmarc_active"] is True

    def test_shap_with_fraud_network_context(self):
        fraud_network_ctx = {
            "entity_in_fraud_network": True,
            "fraud_case_count": 3,
            "total_case_count": 5,
        }
        exp = explain_verification_shap(
            risk_score=85,
            verdict="BAHAYA",
            osint_results={"phones": [], "domain": {}, "web": {}, "fraud_network": fraud_network_ctx},
            risk_factors=["Entitas terhubung sindikat penipuan"],
            safe_factors=[],
            nlp_result={},
            entities={"companies": ["PT SCAM"]},
            network_context=fraud_network_ctx,
        )
        assert exp["networkx_graph_analytics"]["entity_in_fraud_network"] is True
        assert isinstance(exp["decision_path"], list)
        assert len(exp["decision_path"]) > 0
        step_names = [s["step"] for s in exp["decision_path"]]
        assert any("Fraud Network Case Memory" in s for s in step_names)


def test_spf_penalty_requires_corporate_domain():
    from app.services.xai.shap_explainer import explain_verification_shap
    no_domain = explain_verification_shap(28, "AMAN", {"domain": {"age_years": None}, "email_security": {"spf_active": False}}, [], [], entities={})
    labels = [c.get("label") for c in no_domain.get("waterfall_chart", [])]
    assert "Tidak Ada SPF/DMARC pada Domain Korporat" not in labels
    with_domain = explain_verification_shap(28, "AMAN", {"domain": {"domain": "contoh.co.id", "age_years": 5}, "email_security": {"spf_active": False, "domain": "contoh.co.id"}}, [], [], entities={})
    labels = [c.get("label") for c in with_domain.get("waterfall_chart", [])]
    assert "Tidak Ada SPF/DMARC pada Domain Korporat" in labels


def test_whatsapp_only_apply_detected_but_not_when_email_present():
    from app.services.nlp.classifier import extract_behavioral_features as f
    assert f("Operator packing. Kirim CV: 0896-7951-0296")["has_whatsapp_apply"]
    assert f("Cantumkan nama dan usia pada pesan WhatsApp")["has_whatsapp_apply"]
    assert not f("Kirim lamaran ke hrm@newsaphirhotel.com\\nNo Whatsapp : 0823 2386 3434")["has_whatsapp_apply"]
