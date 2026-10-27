from app.services.web_fetcher import _job_posting_page_text

_HTML = """<html><head>
<meta property="og:image" content="https://www.lokerjogja.id/wp-content/uploads/banner.jpeg">
<script type="application/ld+json">{"@context":"https://schema.org","@graph":[{"@type":"WebPage","name":"x"}]}</script>
<script type="application/ld+json">
{ "@context": "http://schema.org/", "@type": "JobPosting", "title": "SPV CS Sales & CRM",
  "description": "<p>Al-Kautsar Cater Indonesia membuka lowongan.</p><ul><li>Laki-laki</li></ul>",
  "hiringOrganization": {"@type": "Organization", "name": "PT. Alkautsar Cater Indonesia"},
  "jobLocation": {"@type": "Place", "address": {"streetAddress": "Alamat di Yogyakarta, detail tidak diketahui   ", "addressLocality": "Yogyakarta"}},
  "validThrough": "2026-11-10" }
</script></head><body>
<div class="loker-detail"><a href="https://s.id/alkautsarfuturetalent">Formulir</a>
<a href="https://wa.me/6285189288924?text=Halo">WhatsApp</a>
<a href="/cdn-cgi/l/email-protection#{cf}">[email&#160;protected]</a></div>
<aside><a href="https://www.lokerjogja.id/lowongan/lain/">Batik Ambo Malioboro</a><a href="https://wa.me/6281111111111">WA lain</a></aside>
<footer><a href="https://wa.me/6287782292585">CS LokerJogja</a></footer>
</body></html>"""


def _cf(email: str, key: int = 0x42) -> str:
    return f"{key:02x}" + "".join(f"{ord(c) ^ key:02x}" for c in email)


def test_job_posting_page_keeps_main_contacts_and_skips_sidebar():
    html = _HTML.replace("{cf}", _cf("hrd@alkautsar.co.id"))
    text, img = _job_posting_page_text(html, "https://www.lokerjogja.id/lowongan/spv-cs/")
    assert "Posisi: SPV CS Sales & CRM" in text
    assert "Perusahaan: PT. Alkautsar Cater Indonesia" in text
    assert "WhatsApp: +6285189288924" in text
    assert "Tautan lamaran: https://s.id/alkautsarfuturetalent" in text
    assert "Email: hrd@alkautsar.co.id" in text
    assert "tidak diketahui" not in text
    assert "Batik Ambo" not in text and "6281111111111" not in text and "6287782292585" not in text
    assert img.endswith("banner.jpeg")


def test_page_without_job_posting_returns_empty():
    assert _job_posting_page_text("<html><body><p>berita</p></body></html>", "https://contoh.id/") == ("", None)


def test_job_posting_with_unescaped_html_attributes():
    html = """<html><head><script type="application/ld+json">
{ "@type": "JobPosting", "title": "Marketing Executive",
  "description": "<p>Excelland Properti membuka lowongan.</p><p data-path-to-node="7">Benefit</p><ul><li id="p-rc_1" data-path-to-node="9,0,0">Gaji 3 Juta</li></ul>",
  "hiringOrganization": {"@type": "Organization", "name": "Excelland Properti"} }
</script></head><body><a href="https://wa.me/6288983124299">WhatsApp</a></body></html>"""
    text, _ = _job_posting_page_text(html, "https://www.lokerjogja.id/lowongan/x/")
    assert "Perusahaan: Excelland Properti" in text
    assert "Gaji 3 Juta" in text
    assert "WhatsApp: +6288983124299" in text
