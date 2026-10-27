import pytest
from app.services.graph.fraud_network import build_fraud_network, check_entity_in_network
from app.services.nlp.classifier import check_content_safety_and_type, classify_text
from app.services.xai.shap_explainer import explain_verification_shap, _FEATURE_WEIGHTS
from app.services.llm.verifin_reasoning import _calibrate_unknown_search_output


class TestAudit007GraphIsolation:
    """Temuan 1: Pengujian anti-kontaminasi graf penipuan pada input campuran (E2 -> E5)."""

    def test_multi_employer_case_skipped_from_fraud_network(self):
        # Skenario E2: Kasus penipuan yang mencampurkan Komitrando HR dan Pertamina Scam
        mixed_historical_cases = [
            {
                "id": "case-e2-mixed",
                "verdict": "BAHAYA",
                "risk_score": 95,
                "phones": ["+6288700015063", "+6281299998888"],
                "emails": ["hrd@komitrando.com", "pertamina.recruitment@gmail.com"],
                "companies": ["PT KOMITRANDO EMPORIO", "PERTAMINA"],
                "is_multi_employer": True,
            },
            {
                "id": "case-real-scam",
                "verdict": "BAHAYA",
                "risk_score": 92,
                "phones": ["+6281299998888"],
                "emails": ["pertamina.recruitment@gmail.com"],
                "companies": ["PERTAMINA"],
                "is_multi_employer": False,
            },
        ]

        G = build_fraud_network(mixed_historical_cases, skip_multi_employer=True)

        # Kasus campuran tidak boleh menjadi node di graf
        assert not G.has_node("case:case-e2-mixed")
        # Kasus penipuan murni tetap masuk
        assert G.has_node("case:case-real-scam")

        # Cek entitas Komitrando (perusahaan legal): TIDAK boleh terhubung ke jaringan penipuan
        check_komitrando = {
            "phones": ["+6288700015063"],
            "emails": ["hrd@komitrando.com"],
            "companies": ["PT KOMITRANDO EMPORIO"],
        }
        res_komitrando = check_entity_in_network(G, check_komitrando)
        assert res_komitrando["entity_in_fraud_network"] is False
        assert res_komitrando["fraud_case_count"] == 0

        # Cek nomor penipu murni: tetap terdeteksi
        check_scammer = {"phones": ["+6281299998888"]}
        res_scammer = check_entity_in_network(G, check_scammer)
        assert res_scammer["entity_in_fraud_network"] is True
        assert res_scammer["fraud_case_count"] == 1

    def test_non_job_posting_skipped_from_fraud_network(self):
        cases = [
            {
                "id": "case-news",
                "verdict": "BAHAYA",
                "risk_score": 80,
                "phones": ["+62811223344"],
                "companies": ["KEMENTERIAN"],
                "not_a_job_posting": True,
            }
        ]
        G = build_fraud_network(cases)
        assert not G.has_node("case:case-news")


class TestAudit007ContentGating:
    """Temuan 2: Deteksi gerbang isi lowongan (E1, E4, E6 vs loker sah)."""

    def test_e1_news_article_detected_as_non_job(self):
        news_text = (
            "YOGYAKARTA - Harga cabai rawit merah di Pasar Beringharjo Kota Yogyakarta mengalami kenaikan "
            "tajam menjelang akhir pekan. Berdasarkan pantauan wartawan, harga mencapai Rp80.000 per kilogram. "
            "Kepala Dinas Perdagangan Kota Yogyakarta, sebagaimana dikutip detikcom, menyatakan bahwa cuaca ekstrem "
            "di sentra produksi menjadi penyebab utama tersendatnya pasokan cabai ke pasar tradisional."
        )
        res = check_content_safety_and_type(news_text)
        assert res["is_job_posting"] is False
        assert res["content_type"] == "news_article"
        assert "berita" in res["warning"].lower()

    def test_invoice_detected_as_non_job(self):
        invoice_text = (
            "INVOICE TAGIHAN RESMI No. INV/2026/10/9981\n"
            "Kepada: PT Media Cipta Bersama\n"
            "Subtotal: Rp 2.500.000\n"
            "Total Bayar: Rp 2.775.000 (PPN 11%)\n"
            "Jatuh Tempo: 30 Oktober 2026\n"
            "Silakan transfer ke nomor pesanan di rekening BCA 8829102910."
        )
        res = check_content_safety_and_type(invoice_text)
        assert res["is_job_posting"] is False
        assert res["content_type"] == "invoice_receipt"

    def test_e6_logo_short_text_detected_as_non_job(self):
        logo_text = "Gemma 4 12B IT QAT"
        res = check_content_safety_and_type(logo_text)
        assert res["is_job_posting"] is False
        assert res["text_too_short"] is True
        assert res["content_type"] == "non_job_text"

    def test_e4_short_job_text_flagged_as_too_short(self):
        short_text = "loker admin wa 0812345678"
        res = check_content_safety_and_type(short_text)
        assert res["is_job_posting"] is True
        assert res["text_too_short"] is True
        assert res["content_type"] == "job_posting_minimal"

    def test_legitimate_job_posting_classified_as_job(self, sample_legit_text):
        res = check_content_safety_and_type(sample_legit_text)
        assert res["is_job_posting"] is True
        assert res["content_type"] == "job_posting"


class TestAudit007XAIExplanationAndWeights:
    """Temuan 4, 6, 7, 11: Sinkronisasi bobot XAI, penanganan pemotongan (capping), dan fallback label."""

    def test_feature_weights_table_completeness(self):
        # Memastikan bobot aktif ada di _FEATURE_WEIGHTS
        assert _FEATURE_WEIGHTS["free_email_only"] == 8.0
        assert _FEATURE_WEIGHTS["address_osm_valid"] == 12.0
        assert _FEATURE_WEIGHTS["address_not_verified"] == 10.0
        assert _FEATURE_WEIGHTS["company_found_web"] == 10.0
        assert _FEATURE_WEIGHTS["has_fee_request"] == 40.0

    def test_score_cap_clamping_prevents_misleading_negative_ai_delta(self):
        # Skenario T3: Akumulasi bukti +158, skor dibatasi pada 96 (maks 100)
        # Sebelumnya: Penyesuaian AI = -74 (seolah AI membela penipu)
        # Sesudah perbaikan: Pemotongan batas atas = -70, Penyesuaian AI = -4
        nlp_res = {
            "behavioral_features": {
                "has_fee_request": True,       # +40
                "has_foreign_work": True,      # +25
                "has_whatsapp_apply": True,    # +20
                "fraud_keyword_count": 4,      # +32 (min(4*8, 32))
            }
        }
        osint_res = {
            "phones": [{"reported_fraud": True}],  # +35
            "domain": {"skipped": "free_email"},   # +8
        }
        # Total bukti = 40 + 25 + 20 + 32 + 35 + 8 = 160. Base = 12. Total raw = 172.
        # Jika risk_score adalah 96:
        shap = explain_verification_shap(
            risk_score=96,
            verdict="BAHAYA",
            osint_results=osint_res,
            risk_factors=[],
            safe_factors=[],
            nlp_result=nlp_res,
        )

        contribs = {c["feature_key"]: c for c in shap["feature_contributions"]}

        # Pemotongan batas atas harus muncul
        assert "score_cap_clamping" in contribs
        clamping = contribs["score_cap_clamping"]
        assert clamping["feature"] == "Pemotongan Batas Atas Skor (Maks 100)"
        assert clamping["impact"] == "safe"
        assert clamping["delta"] == -72.0  # 172 - 100 = 72 pemotongan

        # Penyesuaian AI sekarang hanya selisih minor antara 100 dan 96 (-4)
        if "model_calibration" in contribs:
            ai_cal = contribs["model_calibration"]
            assert ai_cal["delta"] == -4.0

        # Rekonsiliasi matematis 100% konsisten:
        total_delta = sum(c["delta"] for c in shap["feature_contributions"])
        assert round(shap["base_value"] + total_delta) == 96

    def test_fallback_mode_labels_calibration_correctly(self):
        shap = explain_verification_shap(
            risk_score=60,
            verdict="WASPADA",
            osint_results={},
            risk_factors=[],
            safe_factors=[],
            model_used="Rule-Based Fallback (Ollama Unavailable)",
        )
        contribs = {c["feature_key"]: c for c in shap["feature_contributions"]}
        if "model_calibration" in contribs:
            assert contribs["model_calibration"]["feature"] == "Penyesuaian Aturan (Mode Fallback)"

    def test_unknown_search_safety_rule_marks_calibration_flag(self):
        parsed = {"verdict": "BAHAYA", "risk_score": 75, "summary": "Zero footprint"}
        osint_empty = {
            "web": {
                "searches": [{"status": "NO_RESULTS"}],
                "evidence_counts": {"relevant_results": 0},
            },
            "companies": [],
            "phones": [],
            "address_validations": [],
        }
        res = _calibrate_unknown_search_output(parsed, {}, osint_empty, {})
        assert res["verdict"] == "AMAN"
        assert res["risk_score"] == 28
        assert res.get("calibrated_unknown_search") is True


class TestMultiEmployerHeuristic:
    """Varian nama satu pemberi kerja tidak boleh dianggap multi-loker (regresi b76b83a)."""

    def test_name_variants_single_employer(self):
        from app.services.ner import count_distinct_employers, is_multi_employer
        assert count_distinct_employers(["PT Pertamina (Persero)", "Pertamina Group"]) == 1
        assert count_distinct_employers(["HOTEL NEW SAPHIR YOGYAKARTA", "New Saphir Hotel Yogyakarta"]) == 1
        t3 = {"companies": ["PT Pertamina (Persero)", "Pertamina Group"], "phones": ["+6282221333836"], "emails": []}
        assert not is_multi_employer(t3)
        t1 = {"companies": ["HOTEL NEW SAPHIR YOGYAKARTA", "New Saphir Hotel Yogyakarta"],
              "phones": ["+6282323863434"], "emails": ["hrm@newsaphirhotel.com"]}
        assert not is_multi_employer(t1)

    def test_parent_and_brand_without_extra_contacts(self):
        from app.services.ner import is_multi_employer
        t9 = {"companies": ["PT MEDELA POTENTIA TBK", "ANUGRAH ARGON MEDICA", "Anugrah Argon Medica (AAM)"],
              "phones": [], "emails": []}
        assert not is_multi_employer(t9)

    def test_two_postings_merged(self):
        from app.services.ner import is_multi_employer
        e2 = {"companies": ["PT KOMITRANDO EMPORIO", "PT Pertamina (Persero)"],
              "phones": ["+6288706405063", "+6282221333836"], "emails": ["komitrando@komitrando.com"]}
        assert is_multi_employer(e2)

    def test_parent_and_brand_with_phone_and_free_email(self):
        from app.services.ner import is_multi_employer
        morgans = {"companies": ["MORGANS", "PT TRINITY SUCCESS GROUP", "Morgans Kebab"],
                   "phones": ["+6285123871115"], "emails": ["recruitmentmorganskebab@gmail.com"]}
        assert not is_multi_employer(morgans)
