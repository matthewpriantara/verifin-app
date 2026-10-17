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

