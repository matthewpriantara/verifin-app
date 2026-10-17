import pytest
from app.services.osint.gform_inspector import is_gform_url, PHISHING_KEYWORDS
from app.services.osint.web_evidence import _result_matches_query


class TestGFormInspector:
    def test_detect_gform_urls(self):
        assert is_gform_url("https://forms.gle/N6mfqUbVnC2JF68y6") is True
        assert is_gform_url("https://docs.google.com/forms/d/e/1FAIpQLSc.../viewform") is True
        assert is_gform_url("http://bit.ly/form-lamaran") is True

    def test_non_gform_urls_rejected(self):
        assert is_gform_url("https://example.com/careers") is False
        assert is_gform_url("https://linkedin.com/jobs/view/12345") is False

    def test_phishing_keywords_coverage(self):
        # Critical high-risk terms in Indonesian job scams
        assert "rekening" in PHISHING_KEYWORDS
        assert "biaya" in PHISHING_KEYWORDS
        assert "transfer" in PHISHING_KEYWORDS
        assert "deposit" in PHISHING_KEYWORDS
        assert "foto ktp" in PHISHING_KEYWORDS


class TestWebEvidenceMatching:
    def test_exact_token_match_in_url(self):
        # When token is explicitly in the domain/URL
        matched = _result_matches_query('"Bangor"', "https://bangor.example.com", "Welcome", "")
        assert matched is True

    def test_negative_generic_mention_anti_false_positive(self):
        # Bangor mentioned in generic news article should not match company query
        matched = _result_matches_query(
            '"Bangor"',
            "https://news.example/article",
            "Bangor City",
            "berita umum kota Bangor",
        )
        assert matched is False



def test_company_mentions_follow_web_evidence_when_validator_finds_nothing():
    from app.services.osint.runner import _attach_company_evidence_counts

    companies = [{
        "name": "Qhomemart",
        "stats": {"public_mentions": 0},
        "neutral_notes": ["Tidak ada hasil relevan untuk 'Qhomemart' pada request ini.", "Legalitas belum diverifikasi."],
    }]
    web = {"evidence_counts": {"relevant_results": 7}, "searches": [{"results": [{}, {}]}]}
    _attach_company_evidence_counts(companies, web, {"posts": []})

    stats = companies[0]["stats"]
    assert stats["public_mentions"] == 7
    assert stats["public_mentions_source"] == "web_evidence"
    assert companies[0]["neutral_notes"] == ["Legalitas belum diverifikasi."]


def test_company_mentions_untouched_when_validator_already_higher():
    from app.services.osint.runner import _attach_company_evidence_counts

    companies = [{"name": "PT A", "stats": {"public_mentions": 9}}]
    _attach_company_evidence_counts(companies, {"evidence_counts": {"relevant_results": 3}}, {})
    assert companies[0]["stats"]["public_mentions"] == 9
    assert "public_mentions_source" not in companies[0]["stats"]
