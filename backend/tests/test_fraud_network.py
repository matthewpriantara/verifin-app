import pytest
from app.services.graph.fraud_network import (
    build_fraud_network,
    check_entity_in_network,
    get_network_graph_data,
    _extract_domain,
)


class TestFraudNetworkGraph:
    def test_extract_domain_cleaning(self):
        assert _extract_domain("https://www.example.com/jobs/123") == "example.com"
        assert _extract_domain("http://bit.ly/scam-apply") == "bit.ly"
        assert _extract_domain("") is None

    def test_build_network_and_node_types(self, sample_historical_cases):
        G = build_fraud_network(sample_historical_cases)
        # Check node presence
        assert G.has_node("case:case-001")
        assert G.has_node("phone:6281234567890")
        assert G.has_node("email:recruitment.fakecorp@gmail.com")
        assert G.has_node("company:PT SCAM INDONESIA")
        assert G.has_node("url:bit.ly")

        # Check edge types
        edge_data = G.get_edge_data("case:case-001", "phone:6281234567890")[0]
        assert edge_data["edge_type"] == "USES_PHONE"
        assert edge_data["verdict"] == "BAHAYA"

    def test_entity_detected_in_fraud_network(self, sample_historical_cases):
        G = build_fraud_network(sample_historical_cases)
        # Checking phone reused by scam syndicate
        new_vacancy_entities = {
            "phones": ["082199887766"],
            "emails": ["random_new@gmail.com"],
            "companies": ["PT BARU SEJAHTERA"],
        }
        res = check_entity_in_network(G, new_vacancy_entities)
        assert res["entity_in_fraud_network"] is True
        assert res["fraud_case_count"] >= 1
        assert len(res["matched_entities"]) > 0
        matched = res["matched_entities"][0]
        assert matched["entity_type"] == "phones"
        assert "BAHAYA" in matched["verdicts"]

    def test_clean_entity_not_in_fraud_network(self, sample_historical_cases):
        G = build_fraud_network(sample_historical_cases)
        new_clean_entities = {
            "phones": ["+6285738325536"],
            "emails": ["hrdthebikershop@gmail.com"],
            "companies": ["The Biker Shop"],
        }
        res = check_entity_in_network(G, new_clean_entities)
        # Case 002 is AMAN, so entity_in_fraud_network should be False
        assert res["entity_in_fraud_network"] is False
        assert res["fraud_case_count"] == 0

    def test_network_graph_data_export(self, sample_historical_cases):
        G = build_fraud_network(sample_historical_cases)
        export = get_network_graph_data(G, max_nodes=20)
        assert "nodes" in export
        assert "edges" in export
        assert len(export["nodes"]) > 0
        assert any(n["verdict"] == "BAHAYA" for n in export["nodes"])

    def test_case_matched_by_several_entities_counted_once(self, sample_historical_cases):
        G = build_fraud_network(sample_historical_cases)
        res = check_entity_in_network(G, {
            "emails": ["recruitment.fakecorp@gmail.com"],
            "companies": ["PT SCAM INDONESIA"],
        })
        assert res["fraud_case_count"] == 1
        assert res["total_case_count"] == 1
