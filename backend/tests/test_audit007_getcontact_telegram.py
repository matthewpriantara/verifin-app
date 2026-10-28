"""Uji sinyal Telegram, GetContact, domain bebas daftar, isi website
penipuan, lokasi tidak cocok, serta intervensi I-05/I-12/I-13 di tahap Memeriksa isi."""
from app.services.nlp.classifier import _has_telegram_apply, extract_behavioral_features
from app.services.osint.getcontact import (
    FEW,
    KNOWN,
    SPAM,
    UNKNOWN,
    WELL_KNOWN,
    classify_community_level,
)
from app.services.osint.web_evidence import (
    _cities_in,
    _fraud_site_matches,
    detect_location_mismatch,
    is_open_registration_domain,
)
from app.services.precheck import (
    apply_non_job_filter,
    detect_language_note,
    detect_personal_data,
    split_non_job,
)
from app.services.llm.verifin_reasoning import _fallback_analysis, _floor_fraud_site_content, _floor_telegram_channel
from app.services.xai.shap_explainer import explain_verification_shap


class TestTelegramSignal:
    def test_positive_cases(self):
        texts = [
            "Info lowongan admin, daftar di t.me/lokerxx",
            "Join grup telegram untuk info seleksi",
            "Kirim CV ke Telegram: @hrd",
            "Hubungi via Telegram untuk melamar",
            "Lamaran melalui https://telegram.me/hrdofficial",
        ]
        for text in texts:
            assert _has_telegram_apply(text.lower()) is True, text

    def test_negation_cases(self):
        texts = [
            "Rekrutmen ini tidak melalui Telegram. Kirim lamaran ke email resmi.",
            "Waspada penipuan via telegram yang mengatasnamakan perusahaan ini.",
            "Hati-hati modus telegram; kanal resmi hanya melalui portal karier.",
        ]
        for text in texts:
            assert _has_telegram_apply(text.lower()) is False, text

    def test_behavioral_feature_exposed(self):
        signals = extract_behavioral_features("Lowongan admin, hubungi via Telegram @hrd")
        assert signals["has_telegram_apply"] is True

    def test_floor_raises_aman_to_waspada_55(self):
        parsed = {"verdict": "AMAN", "risk_score": 20, "risk_factors": []}
        out = _floor_telegram_channel(parsed, {"has_telegram_apply": True})
        assert out["verdict"] == "WASPADA"
        assert out["risk_score"] == 55
        assert out["calibrated_telegram"] is True

    def test_floor_keeps_bahaya(self):
        parsed = {"verdict": "BAHAYA", "risk_score": 90, "risk_factors": []}
        out = _floor_telegram_channel(parsed, {"has_telegram_apply": True})
        assert out["risk_score"] == 90

    def test_floor_guard_label_in_xai(self):
        shap = explain_verification_shap(
            risk_score=55,
            verdict="WASPADA",
            osint_results={},
            risk_factors=[],
            safe_factors=[],
            nlp_result={"behavioral_features": {"has_telegram_apply": True}},
            model_used="gemini (Evidence Reasoning)",
            guard_rule="telegram",
        )
        labels = [c["feature"] for c in shap["feature_contributions"]]
        assert "Aturan Pengaman: Lamaran via Telegram" in labels
        assert "Lamaran Diarahkan ke Telegram" in labels


class TestGetContactLevels:
    def test_levels(self):
        assert classify_community_level(False, 0, False) == UNKNOWN
        assert classify_community_level(True, 0, False) == UNKNOWN
        assert classify_community_level(True, 5, False) == FEW
        assert classify_community_level(True, 71, False) == KNOWN
        assert classify_community_level(True, 150, False) == WELL_KNOWN
        assert classify_community_level(True, 71, True) == SPAM
        assert classify_community_level(True, 0, True) == SPAM

    def test_unavailable_when_not_configured(self, monkeypatch):
        import asyncio
        from app.services.osint import getcontact as mod

        monkeypatch.setattr(mod, "GETCONTACT_URL", "")
        result = asyncio.run(mod.lookup_getcontact("081234567890"))
        assert result["probe_status"] == "UNAVAILABLE"
        assert result["community_level"] is None
        assert result["tag_count"] is None

    def test_xai_ignores_unavailable(self):
        shap = explain_verification_shap(
            risk_score=12,
            verdict="AMAN",
            osint_results={"phones": [{"getcontact": {"probe_status": "UNAVAILABLE"}}]},
            risk_factors=[],
            safe_factors=[],
        )
        keys = {c["feature_key"] for c in shap["feature_contributions"]}
        assert not ({"phone_unknown_community", "phone_spam_label", "phone_well_known"} & keys)

    def test_xai_unknown_and_spam(self):
        shap = explain_verification_shap(
            risk_score=50,
            verdict="WASPADA",
            osint_results={"phones": [{"phone": "+62812", "getcontact": {
                "probe_status": "COMPLETED", "community_level": "UNKNOWN", "tag_count": 0, "spam_flagged": False,
            }}]},
            risk_factors=[],
            safe_factors=[],
        )
        keys = {c["feature_key"] for c in shap["feature_contributions"]}
        assert "phone_unknown_community" in keys


class TestWebHeuristics:
    def test_open_registration_domain(self):
        assert is_open_registration_domain("sharp-career.my.id") == "sharp-career.my.id"
        assert is_open_registration_domain("www.vercel.app") is None
        assert is_open_registration_domain("badapp.vercel.app") == "badapp.vercel.app"
        assert is_open_registration_domain("blogspot.com") is None
        assert is_open_registration_domain("komitrando.com") is None

    def test_fraud_site_matches(self):
        assert "akun kerja" in _fraud_site_matches("Akun Kerja", "Selesaikan tugas dan raih keuntungan")
        assert _fraud_site_matches("Beranda", "Profil perusahaan dan kontak") == []
        assert len(_fraud_site_matches("Promo", "dapatkan komisi dan tugas harian")) == 2

    def test_city_extraction(self):
        assert _cities_in("Jl. Raya Janti, Sleman, Yogyakarta") >= {"sleman", "yogyakarta"}
        assert _cities_in("Toko Bunga Roemah Boenga, Banda Aceh") == {"banda aceh"}

    def test_location_mismatch_flags_other_city(self):
        searches = [{"results": [{
            "title": "Roemah Boenga - Toko Bunga",
            "snippet": "Toko Bunga Roemah Boenga, Jl. Teuku Umar, Banda Aceh",
            "url": "https://instagram.com/roemahboenga",
        }]}]
        found = detect_location_mismatch(["Roemah Boenga"], ["Jl. Kemang Raya No. 5, Jakarta"], searches)
        assert found["posting_city"] == "jakarta"
        assert found["profile_city"] == "banda aceh"

    def test_location_mismatch_ignores_result_that_mentions_posting_city(self):
        # "Depok, Yogyakarta" adalah kecamatan, bukan kota lain.
        searches = [{"results": [{
            "title": "Hotel New Saphir Yogyakarta",
            "snippet": "Hotel New Saphir terletak di Jalan Laksda Adisucipto No. 38, Depok, Yogyakarta",
            "url": "https://www.traveloka.com/hotel-new-saphir",
        }]}]
        assert detect_location_mismatch(["Hotel New Saphir"], ["Jl. Laksda Adisucipto, Yogyakarta"], searches) == {}

    def test_location_mismatch_requires_street_address(self):
        searches = [{"results": [{
            "title": "PT Maju Jaya", "snippet": "cabang Bandung", "url": "https://example.com",
        }]}]
        assert detect_location_mismatch(["PT Maju Jaya"], ["Jakarta"], searches) == {}


class TestPrecheckInterventions:
    JOB = (
        "Lowongan Barista di PT Kopi Nusantara, Jl. Kaliurang No. 5, Sleman. "
        "Kualifikasi minimal SMA, gaji Rp3.000.000, kirim CV ke hrd@kopinusantara.com."
    )
    NEWS = (
        "Kementerian Perdagangan menyebut harga cabai di Pasar Beringharjo naik. "
        "Kepala Dinas Perdagangan mengatakan pasokan berkurang."
    )

    def test_split_non_job_span(self):
        text = f"{self.JOB}\n\n{self.NEWS}"
        kept, removed = split_non_job(text, [{"text": self.NEWS}])
        assert self.NEWS not in kept
        assert self.JOB in kept
        assert removed == [self.NEWS]

    def test_split_skips_unlocatable_or_short(self):
        kept, removed = split_non_job(self.JOB, [{"text": "tidak ada di teks ini sama sekali"}])
        assert kept == self.JOB and removed == []

    def test_filter_drops_entities_only_in_removed_text(self):
        entities = {
            "companies": ["PT Kopi Nusantara", "Dinas Perdagangan"],
            "phones": ["081234567890"],
            "emails": ["hrd@kopinusantara.com"],
        }
        dropped = apply_non_job_filter(entities, self.JOB, [self.NEWS + " 081234567890"])
        assert dropped == 2
        assert entities["companies"] == ["PT Kopi Nusantara"]
        assert entities["emails"] == ["hrd@kopinusantara.com"]

    def test_personal_data_detection(self):
        assert "NIK/KTP" in detect_personal_data("NIK 3404123456780001 mohon diisi")
        assert "nomor rekening" in detect_personal_data("transfer ke rekening 1234567890 a/n Budi")
        assert detect_personal_data(self.JOB) == []

    def test_language_note(self):
        english = (
            "We are hiring a barista for our new cafe. The candidate must have experience "
            "with espresso machines and be able to work in shifts. Please send your application "
            "to our email and include your resume. We will contact you for an interview soon."
        )
        assert detect_language_note(english) is not None
        assert detect_language_note(self.JOB) is None


class TestFraudSiteGuard:
    def test_floor_raises_aman_to_waspada_55(self):
        parsed = {"verdict": "AMAN", "risk_score": 12, "risk_factors": []}
        out = _floor_fraud_site_content(parsed, {"web": {"fraud_site_content": {"matches": ["akun kerja"]}}})
        assert out["verdict"] == "WASPADA"
        assert out["risk_score"] == 55
        assert out["calibrated_fraud_site"] is True

    def test_floor_ignores_empty_matches(self):
        parsed = {"verdict": "AMAN", "risk_score": 12, "risk_factors": []}
        out = _floor_fraud_site_content(parsed, {"web": {"fraud_site_content": {}}})
        assert out["risk_score"] == 12

    def test_fallback_keeps_fraud_site_floor(self):
        out = _fallback_analysis(
            {"companies": ["NEW TRENDY"]},
            {
                "phones": [{"probe_status": "UNAVAILABLE"}],
                "web": {
                    "fraud_site_content": {"matches": ["akun kerja", "t.me/"]},
                    "open_registration_domain": {"domain": "newtrendy.my.id"},
                    "websites": [{"website_status": "AVAILABLE"}],
                },
            },
        )
        assert out["verdict"] == "WASPADA"
        assert out["risk_score"] >= 55
        assert "Rule-Based Fallback" in out["model_used"]
