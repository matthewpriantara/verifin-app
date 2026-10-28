"""Uji blind spot run 14 (pencatutan merek, tautan pendek, isi situs, Telegram, masking, kuota) dan pembacaan isi tag GetContact."""
import importlib.util
import sys
import types
from pathlib import Path

from app.services.llm.verifin_reasoning import (
    _apply_brand_impersonation,
    _fallback_analysis,
    _has_hard_risk_evidence,
)
from app.services.nlp.classifier import _has_telegram_apply
from app.services.osint.getcontact import fraud_tag_summary
from app.services.osint.web_evidence import _fraud_site_matches
from app.services.pii import PiiMasker
from app.services.xai.shap_explainer import explain_verification_shap


def _load_getcontact_service():
    """Muat infra/getcontact-api/app.py dengan `gtc` tiruan (klien aslinya hanya ada di home)."""
    fake = types.ModuleType("gtc")
    fake.GtcError = type("GtcError", (Exception,), {})
    sys.modules.setdefault("gtc", fake)
    path = Path(__file__).resolve().parents[2] / "infra" / "getcontact-api" / "app.py"
    spec = importlib.util.spec_from_file_location("getcontact_service", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _phone_with_tags(hits: int, terms: list[str]) -> dict:
    return {
        "phone": "+6281200000000",
        "getcontact": {
            "probe_status": "COMPLETED",
            "community_level": "FEW",
            "tag_count": 6,
            "fraud_tags": {"probe_status": "COMPLETED", "fraud_tag_hits": hits, "fraud_tag_terms": terms},
        },
    }


class TestTelegramB4:
    def test_scammer_negation_after_handle_still_counts(self):
        assert _has_telegram_apply("daftar lewat telegram @cs_sinarmedia, dijamin bukan penipuan.") is True

    def test_short_forms(self):
        assert _has_telegram_apply("minat? langsung chat tele: @rekrut_x") is True
        assert _has_telegram_apply("info di tg @lokerjogja_admin") is True

    def test_warning_and_job_titles_stay_negative(self):
        assert _has_telegram_apply("kami tidak pernah merekrut melalui telegram.") is False
        assert _has_telegram_apply("posisi telemarketing dan tele sales") is False


class TestPiiB5:
    def test_transfer_and_digital_bank(self):
        masked = PiiMasker().mask("transfer ke 1234567890 a.n. Budi Santoso. Seabank 901234567890")
        assert "1234567890" not in masked and "901234567890" not in masked
        assert "Budi" not in masked

    def test_spaced_nik(self):
        assert "3404" not in PiiMasker().mask("NIK: 3404 0123 4567 0001")

    def test_words_starting_with_an_are_untouched(self):
        text = "Dibutuhkan Analis Data dan Anak magang, angkatan 2024"
        assert PiiMasker().mask(text) == text

    def test_account_name_roundtrip(self):
        masker = PiiMasker()
        masked = masker.mask("rek BCA 123456789 A/N Rudi")
        assert "Rudi" not in masked
        assert "Rudi" in masker.unmask(masked)


class TestFraudSiteB3:
    def test_title_only_matches(self):
        assert "tiktok task" in _fraud_site_matches("Tiktok Task", "")

    def test_deposit_alone_is_weak(self):
        assert _fraud_site_matches("Bank Syariah", "produk deposito dan deposit") == []


class TestGetcontactTagService:
    def test_counts_only_fraud_terms(self):
        service = _load_getcontact_service()
        hits, terms = service.count_fraud_tags([
            {"tag": "P3NIPU LOKER"},
            {"tag": "Pak Budi Toko Bangunan"},
            {"tag": "HRD Hotel"},
            {"tag": "investasi bodong"},
        ])
        assert hits == 2
        assert terms == ["bodong", "investasi", "penipu"]
        assert all(t in service.FRAUD_TERMS for t in terms)

    def test_empty_tags(self):
        service = _load_getcontact_service()
        assert service.count_fraud_tags([]) == (0, [])


class TestFraudTagScoring:
    def test_summary_picks_highest(self):
        phones = [_phone_with_tags(1, ["tipu"]), _phone_with_tags(3, ["penipu", "scam"])]
        assert fraud_tag_summary(phones) == (3, ["penipu", "scam"])

    def test_two_hits_are_hard_evidence(self):
        assert _has_hard_risk_evidence({}, {"phones": [_phone_with_tags(2, ["penipu"])]}) is True
        assert _has_hard_risk_evidence({}, {"phones": [_phone_with_tags(1, ["penipu"])]}) is False

    def test_fallback_weights(self):
        base = _fallback_analysis({"companies": ["PT Contoh"]}, {"phones": [_phone_with_tags(0, [])]})
        one = _fallback_analysis({"companies": ["PT Contoh"]}, {"phones": [_phone_with_tags(1, ["tipu"])]})
        two = _fallback_analysis({"companies": ["PT Contoh"]}, {"phones": [_phone_with_tags(2, ["penipu"])]})
        assert one["risk_score"] - base["risk_score"] == 10
        assert two["risk_score"] - base["risk_score"] == 20

    def test_xai_row_never_contains_tag_text(self):
        shap = explain_verification_shap(
            risk_score=80,
            verdict="BAHAYA",
            osint_results={"phones": [_phone_with_tags(2, ["penipu", "scam"])]},
            risk_factors=[],
            safe_factors=[],
            entities={"companies": ["PT Contoh"]},
        )
        rows = [c for c in shap["feature_contributions"] if c.get("feature_key") == "phone_fraud_tags"]
        assert rows and "penipu" in rows[0]["description"]


class TestBrandImpersonationB1:
    @staticmethod
    def _osint(extra_web: dict | None = None, phones: list | None = None) -> dict:
        web = {
            "websites": [{"url": "https://www.guardian.co.id", "website_status": "AVAILABLE"}],
            "scam_check": {"warnings": 0},
        }
        web.update(extra_web or {})
        return {"web": web, "phones": phones or [], "domain": {}}

    def test_brand_gmail_unknown_number_raises(self):
        parsed = {"verdict": "WASPADA", "risk_score": 50, "risk_factors": []}
        phones = [{"getcontact": {"probe_status": "COMPLETED", "community_level": "UNKNOWN"}}]
        out = _apply_brand_impersonation(
            parsed, {"emails": ["guardiankarir@gmail.com"]}, self._osint(phones=phones), {}
        )
        assert out["risk_score"] >= 68 and out.get("brand_impersonation_guard")

    def test_umkm_gmail_without_official_site_untouched(self):
        parsed = {"verdict": "AMAN", "risk_score": 18, "risk_factors": []}
        osint = {"web": {"websites": [], "scam_check": {"warnings": 0}}, "phones": [], "domain": {}}
        out = _apply_brand_impersonation(parsed, {"emails": ["recruitmentmorganskebab@gmail.com"]}, osint, {})
        assert out["risk_score"] == 18 and not out.get("brand_impersonation_guard")

    def test_no_extra_evidence_untouched(self):
        parsed = {"verdict": "AMAN", "risk_score": 20, "risk_factors": []}
        out = _apply_brand_impersonation(parsed, {"emails": ["hrd.toko@gmail.com"]}, self._osint(), {})
        assert out["risk_score"] == 20


class TestOfficialDomainDiscovery:
    @staticmethod
    def _search(*items: tuple[str, str]) -> list[dict]:
        return [{"results": [{"url": u, "title": t} for u, t in items]}]

    def test_brand_site_found_platforms_ignored(self):
        from app.services.osint.official_domain import find_official_domains

        found = find_official_domains(
            ["guardian INDONESIA"],
            self._search(
                ("https://www.instagram.com/guardian_id/", "Guardian Indonesia (@guardian_id)"),
                ("https://guardianindonesia.co.id/", "Guardian Online Shop - Guardian Indonesia"),
                ("https://www.tokopedia.com/guardian-official", "Toko Guardian Official Store"),
                ("https://www.theguardian.com/world", "The Guardian"),
            ),
        )
        assert [c["domain"] for c in found] == ["guardianindonesia.co.id"]

    def test_job_boards_and_directories_are_not_official(self):
        from app.services.osint.official_domain import find_official_domains

        found = find_official_domains(
            ["Excelland Properti"],
            self._search(
                ("https://www.lokerjogja.id/lowongan/excelland", "Excelland Properti"),
                ("https://idalamat.com/alamat/excelland", "Kantor Excelland Properti"),
            ),
        )
        assert found == []

    def test_country_mismatch_rejected(self):
        from app.services.osint.official_domain import find_official_domains

        found = find_official_domains(
            ["PT TRINITY SUCCESS GROUP"],
            self._search(("https://trinitysuccessgroup.com.au/", "Trinity Success Group Australia")),
        )
        assert found == []

    def test_young_top_candidate_dropped(self):
        from app.services.osint.official_domain import find_official_domains

        found = find_official_domains(
            ["glowberry"],
            self._search(("https://www.glowberry.com/", "Glowberry"), ("https://www.glowberry.com/about", "Glowberry")),
            age_lookup=lambda _d: {"age_days": 40},
        )
        assert found == []

    def test_unknown_age_keeps_candidate(self):
        from app.services.osint.official_domain import find_official_domains

        found = find_official_domains(
            ["SHARP ELECTRONICS INDONESIA"],
            self._search(("https://id.sharp/contact_us", "Kontak Kami | SHARP Indonesia")),
            age_lookup=lambda _d: {"age_days": -1},
        )
        assert [c["domain"] for c in found] == ["id.sharp"]

    def test_vision_only_shortener_counts_as_hidden_channel(self):
        parsed = {"verdict": "WASPADA", "risk_score": 50, "risk_factors": []}
        osint = {
            "web": {
                "official_domains": [{"domain": "sociolla.com", "score": 4}],
                "scam_check": {"warnings": 1},
                "vision_shortener_failures": ["https://tinyurl.com/Sciolla"],
            },
            "phones": [],
            "domain": {},
        }
        out = _apply_brand_impersonation(parsed, {"companies": ["sociolla"]}, osint, {})
        assert out["risk_score"] == 68


class TestSiteKinds:
    def test_kinds_from_data_file(self):
        from app.services.site_kinds import kind_of

        assert kind_of("https://bit.ly/x") == "shortener"
        assert kind_of("hrd@gmail.com") == "free_email"
        assert kind_of("sharp-career.my.id") == "open_registration"
        assert kind_of("my.id") == ""
        assert kind_of("m.tokopedia.com") == "marketplace"
        assert kind_of("guardianindonesia.co.id") == ""

    def test_no_host_lists_left_in_code(self):
        """Daftar host hanya boleh ada di app/data/site_kinds.json."""
        import re
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "app"
        pattern = re.compile(r'\(\s*"(?:bit\.ly|tinyurl\.com)"|"tokopedia\.com",\s*"shopee\.co\.id"|"\.my\.id",\s*\n')
        offenders = [str(p) for p in root.rglob("*.py") if pattern.search(p.read_text(encoding="utf-8"))]
        assert offenders == []


class TestEmployerRegistry:
    def test_registry_wins_over_search(self):
        from app.services.osint.official_domain import find_official_domains

        found = find_official_domains(
            ["PT SHARP ELECTRONICS INDONESIA"],
            [{"results": [{"url": "https://sharp-career.my.id/", "title": "Sharp Career"}]}],
            age_lookup=lambda _d: (_ for _ in ()).throw(AssertionError("WHOIS tidak boleh dipanggil")),
        )
        assert [c["domain"] for c in found] == ["id.sharp"]
        assert found[0]["source"] == "registry"

    def test_unlisted_brand_falls_back_to_search(self):
        from app.services.osint.official_domain import registry_domains

        assert registry_domains(["Morgans Kebab"]) == []


class TestBrandGuardNegatives:
    def test_title_only_match_is_not_official(self):
        from app.services.osint.official_domain import find_official_domains

        found = find_official_domains(
            ["ALFAMART CABANG SLEMAN", "PT Sumber Alfaria Trijaya Tbk"],
            [{"results": [{"url": "https://semuabis.com/pt-sumber-alfaria", "title": "PT Sumber Alfaria Trijaya - Semuabis"}]}],
        )
        assert found == []

    def test_walk_in_at_address_skips_guard(self):
        from app.services.nlp.classifier import extract_behavioral_features

        text = "Walk-in interview di Kantor Cabang Alfamart Sleman, Jl. Magelang Km 10. Email rekrutmen.alfa@gmail.com"
        signals = extract_behavioral_features(text, ["Alfamart"])
        assert signals["has_walk_in"] and signals["has_address"]
        parsed = {"verdict": "WASPADA", "risk_score": 41, "risk_factors": []}
        osint = {
            "web": {"official_domains": [{"domain": "alfamart.co.id"}], "scam_check": {"warnings": 2}},
            "phones": [],
            "domain": {},
        }
        out = _apply_brand_impersonation(parsed, {"emails": ["rekrutmen.alfa@gmail.com"]}, osint, signals)
        assert out["risk_score"] == 41
