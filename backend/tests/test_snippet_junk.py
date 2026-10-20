from app.services.osint.web_evidence import _is_script_or_ad_junk as evidence_junk
from app.services.web_fetcher import _is_script_or_ad_junk as fetcher_junk

CSS = (
    ".elementor-26052 .elementor-element.elementor-element-a359d4c > .elementor-container > "
    ".elementor-column > .elementor-widget-wrap{align-content:center;}"
)
PROSE = [
    "Hotel New Saphir Yogyakarta membuka lowongan Chef de Partie. Kirim lamaran ke hrd@newsaphirhotel.com.",
    "PT. Komitrando Emporio. Jl. Kaliurang Km 5. Sleman, D.I. Yogyakarta.",
]


def test_css_selector_snippet_is_junk():
    assert evidence_junk(CSS)
    assert fetcher_junk(CSS)


def test_page_prose_is_kept():
    for text in PROSE:
        assert not evidence_junk(text)
        assert not fetcher_junk(text)
