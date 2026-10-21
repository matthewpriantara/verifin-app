"""Laporan komunitas yang dimoderasi harus langsung tampil di kasus tersimpan (GET /cases/{id} & cache)."""
from types import SimpleNamespace

import pytest

from app.services import community_refresh
from app.services.community_refresh import COMMUNITY_RISK_FACTOR, apply_community_signal, refresh_cases_for_report
from app.services.db_cache import CACHE_SCHEMA_VERSION, _job_case_to_response
from app.services.xai.shap_explainer import explain_verification_shap, rescore_community_reports

PENDING = {"status": "COMPLETED", "report_count": 0, "pending_report_count": 1, "reported_by_community": False}
APPROVED = {"status": "COMPLETED", "report_count": 1, "pending_report_count": 0, "reported_by_community": True}
REJECTED = {"status": "COMPLETED", "report_count": 0, "pending_report_count": 0, "reported_by_community": False}
NLP = {"enabled": True, "behavioral_features": {"has_fee_request": True}}


def _total(exp: dict) -> float:
    return exp["base_value"] + sum(c["delta"] for c in exp["feature_contributions"])


def _shap(risk_score: int, community: dict) -> dict:
    return explain_verification_shap(
        risk_score=risk_score,
        verdict="WASPADA",
        osint_results={},
        risk_factors=[],
        safe_factors=[],
        nlp_result=NLP,
        network_context={"status": "COMPLETED", "community_reports": community},
    )


def _case(risk_score: int = 60, community: dict = PENDING) -> SimpleNamespace:
    import uuid
    from datetime import datetime, timezone

    return SimpleNamespace(
        id=uuid.uuid4(),
        verdict="WASPADA",
        risk_score=risk_score,
        companies=None,
        phones=["+6281234567890"],
        emails=None,
        urls=None,
        addresses=None,
        salaries=None,
        entities={"phones": ["+6281234567890"]},
        llm_output={
            "summary": "Ringkasan.",
            "risk_factors": ["Meminta biaya pendaftaran."],
            "safe_factors": [],
            "recommendations": [],
            "model_used": "test",
            "shap_explanation": _shap(risk_score, community),
        },
        osint_summary={
            "cache_schema_version": CACHE_SCHEMA_VERSION,
            "response_osint": {"fraud_network": {"status": "COMPLETED", "community_reports": dict(community)}},
        },
        osint_failed=False,
        created_at=datetime.now(timezone.utc),
    )


class TestRescore:
    @pytest.mark.parametrize("score", [60, 12, 95, 100])
    def test_approve_adds_weight_and_keeps_sum(self, score):
        new_score, verdict, shap = rescore_community_reports(_shap(score, PENDING), 1)
        assert new_score == min(100, score + 20)
        assert shap["final_risk_score"] == new_score
        assert _total(shap) == pytest.approx(new_score, abs=0.01)
        assert any(c["feature_key"] == "community_reported" for c in shap["feature_contributions"])
        assert shap["waterfall_chart"][-1]["cumulative"] == pytest.approx(new_score, abs=0.01)

    def test_reject_after_approve_removes_weight(self):
        new_score, _, shap = rescore_community_reports(_shap(80, APPROVED), 0)
        assert new_score == 60
        assert not any(c["feature_key"] == "community_reported" for c in shap["feature_contributions"])
        assert _total(shap) == pytest.approx(60, abs=0.01)

    def test_verdict_follows_threshold(self):
        _, verdict, shap = rescore_community_reports(_shap(60, PENDING), 1)
        assert verdict == shap["verdict"] == "BAHAYA"  # 60 + 20 = 80


class TestApplyToCase:
    def test_approved_report_visible_in_cached_response(self):
        case = _case(60, PENDING)
        assert apply_community_signal(case, APPROVED) is True

        resp = _job_case_to_response(case)
        community = resp.osint["fraud_network"]["community_reports"]
        assert community["report_count"] == 1
        assert community["pending_report_count"] == 0
        assert resp.risk_score == 80
        assert resp.verdict == "BAHAYA"
        assert resp.risk_factors[0] == COMMUNITY_RISK_FACTOR
        assert _total(case.llm_output["shap_explanation"]) == pytest.approx(80, abs=0.01)

    def test_rejected_pending_report_only_clears_pending(self):
        case = _case(60, PENDING)
        assert apply_community_signal(case, REJECTED) is True
        assert case.risk_score == 60
        assert case.osint_summary["response_osint"]["fraud_network"]["community_reports"]["pending_report_count"] == 0
        assert COMMUNITY_RISK_FACTOR not in case.llm_output["risk_factors"]

    def test_no_change_is_noop(self):
        case = _case(60, PENDING)
        assert apply_community_signal(case, dict(PENDING)) is False
        assert case.risk_score == 60

    def test_reported_phone_list_alone_triggers_update(self):
        # Kasus lama yang tersimpan sebelum field reported_phones ada tetap ikut diperbarui.
        case = _case(80, APPROVED)
        with_phone = dict(APPROVED, reported_phones=["+6281234567890"])
        assert apply_community_signal(case, with_phone) is True
        community = case.osint_summary["response_osint"]["fraud_network"]["community_reports"]
        assert community["reported_phones"] == ["+6281234567890"]
        assert case.risk_score == 80

    def test_case_without_osint_payload_is_skipped(self):
        case = _case(60, PENDING)
        case.osint_summary = None
        assert apply_community_signal(case, APPROVED) is False


class TestRefreshForReport:
    def test_commits_once_for_changed_cases(self, monkeypatch):
        cases = [_case(60, PENDING), _case(30, APPROVED)]
        monkeypatch.setattr(community_refresh, "_related_cases", lambda db, report: cases)
        monkeypatch.setattr(
            "app.api.v1.verify.pipeline._community_report_signal",
            lambda db, entities: dict(APPROVED),
        )
        commits = []
        db = SimpleNamespace(commit=lambda: commits.append(1))
        report = SimpleNamespace(id="r1", status="approved")

        assert refresh_cases_for_report(db, report) == 1
        assert commits == [1]
        assert cases[0].risk_score == 80
        assert cases[1].risk_score == 30

    def test_phone_variants_cover_stored_formats(self):
        assert community_refresh._phone_variants("0812-3456-7890") == ["+6281234567890", "6281234567890", "081234567890"]
        assert community_refresh._phone_variants("") == []
