from app.api.v1.verify.pipeline import _keep_proven_contacts
from app.services.precheck import VISION_MARKER, apply_forced, assess_input, split_postings

JOB = (
    "Lowongan kerja Admin Toko di PT Maju Jaya, Sleman. Kualifikasi minimal SMA, "
    "pengalaman 1 tahun. Kirim CV ke hrd@majujaya.co.id atau WA 0812-3456-7890."
)

NEWS = (
    "Harga cabai rawit di Pasar Beringharjo naik menjadi Rp80.000 per kilogram, kata pedagang "
    "kepada wartawan, Selasa (27/10). Dinas Perdagangan menyebut pasokan dari Magelang berkurang."
)

TWO_JOBS = (
    "HOTEL NEW SAPHIR membuka lowongan Chef de Partie. Kirim CV ke hrm@newsaphirhotel.com "
    "atau WA 0823-1111-3434. Minimal pengalaman 2 tahun di dapur hotel.\n\n"
    "PT Komitrando Emporio mencari HR Generalist. Lamaran ke komitrando@komitrando.com "
    "atau WA 0887-2222-5063. Pendidikan minimal S1 Psikologi."
)


def _ents(**kw):
    base = {"companies": [], "phones": [], "emails": [], "_content": {}}
    base.update(kw)
    return base


def test_news_stops_as_not_job_when_llm_agrees():
    r = assess_input(NEWS, _ents(_content={"is_job_posting": False, "postings": []}))
    assert r["not_job"] is True
    assert r["issue"]["id"] == "I-01"


def test_llm_job_overrides_weak_rule():
    r = assess_input(JOB, _ents(_content={"is_job_posting": True, "postings": [{"employer": "PT Maju Jaya"}]}))
    assert r["issue"] is None and r["not_job"] is False


def test_too_short_text_asks_for_more():
    r = assess_input("loker admin wa 0812", _ents(_content={"is_job_posting": True, "postings": []}))
    assert r["issue"]["id"] == "I-03"


def test_two_employers_with_own_contacts_split_into_segments():
    ents = _ents(
        companies=["HOTEL NEW SAPHIR", "PT Komitrando Emporio"],
        phones=["+6282311113434", "+6288722225063"],
        emails=["hrm@newsaphirhotel.com", "komitrando@komitrando.com"],
        _content={
            "is_job_posting": True,
            "postings": [
                {"employer": "HOTEL NEW SAPHIR", "position": "Chef de Partie", "first_words": "HOTEL NEW SAPHIR membuka lowongan Chef"},
                {"employer": "PT Komitrando Emporio", "position": "HR Generalist", "first_words": "PT Komitrando Emporio mencari HR"},
            ],
        },
    )
    r = assess_input(TWO_JOBS, ents)
    issue = r["issue"]
    assert issue["id"] == "I-04"
    segs = issue["segments"]
    assert [s["employer"] for s in segs] == ["HOTEL NEW SAPHIR", "PT Komitrando Emporio"]
    assert "Komitrando" not in segs[0]["text"]
    assert segs[1]["text"].startswith("PT Komitrando")
    assert segs[0]["contacts"][0] == "0823-xxxx-3434"


def test_brand_and_parent_are_one_posting():
    ents = _ents(
        companies=["Morgans Kebab", "PT Trinity Success Group"],
        phones=["+6285123871115"],
        emails=["recruitmentmorganskebab@gmail.com"],
        _content={"is_job_posting": True, "postings": [
            {"employer": "Morgans Kebab", "position": "Crew"},
            {"employer": "PT Trinity Success Group", "position": "Crew"},
        ]},
    )
    text = "PT Trinity Success Group (Morgans Kebab) membuka lowongan Crew Outlet di Sleman. Kirim CV ke recruitmentmorganskebab@gmail.com atau WA 0851-2387-1115."
    assert assess_input(text, ents)["issue"] is None


def test_segment_without_anchor_has_no_text():
    segs = split_postings("Teks tanpa nama apa pun yang cocok untuk dipotong menjadi lowongan.", [{"employer": "PT Tidak Ada"}])
    assert segs[0]["text"] is None


def test_contact_seen_only_by_vision_is_dropped():
    merged = {"phones": ["+6281234567890", "+6289999999999"], "emails": ["a@b.co.id"], "urls": []}
    ocr = "Hubungi 0812-3456-7890, email a@b.co.id"
    ai_only = _keep_proven_contacts(merged, ocr)
    assert merged["phones"] == ["+6281234567890"]
    assert ai_only == ["+6289999999999"]


def test_vision_block_is_ignored_by_rule_classifier():
    text = f"{JOB}\n\n{VISION_MARKER}\nberita harga cabai naik kata wartawan"
    r = assess_input(text, _ents(_content={"is_job_posting": True, "postings": [{"employer": "PT Maju Jaya"}]}))
    assert r["issue"] is None


def test_forced_input_is_kept_out_of_graph():
    ents = {}
    apply_forced(ents, "not_job")
    assert ents["input_quality"] == "forced"
    assert ents["is_mixed_input"] and ents["not_a_job_posting"]


def test_vision_name_replaces_ocr_misread():
    from app.api.v1.verify.pipeline import _drop_ocr_misreads
    vision = "WE ARE HIRING\nROEMAH BOENGA\nFLORIST & GIFT"
    assert _drop_ocr_misreads(["SBOENGA", "ROEMAH BOENGA"], vision) == ["ROEMAH BOENGA"]
    assert _drop_ocr_misreads(["PT Maju Jaya"], vision) == ["PT Maju Jaya"]


def test_dead_application_domain_is_not_aman():
    from app.services.llm.verifin_reasoning import _floor_dead_application_domain
    osint = {"web": {"websites": [{"url": "https://roemahboenga.store", "website_status": "NOT_FOUND"}]}}
    out = _floor_dead_application_domain({"verdict": "AMAN", "risk_score": 28, "risk_factors": []}, osint)
    assert (out["verdict"], out["risk_score"]) == ("WASPADA", 45)
    alive = {"web": {"websites": [{"website_status": "NOT_FOUND"}, {"website_status": "AVAILABLE"}]}}
    assert _floor_dead_application_domain({"verdict": "AMAN", "risk_score": 20}, alive)["risk_score"] == 20


def test_guard_rule_labels_residual():
    from app.services.xai.shap_explainer import explain_verification_shap
    sh = explain_verification_shap(45, "WASPADA", {}, [], [], guard_rule="dead_domain")
    labels = [c["feature"] for c in sh["feature_contributions"]]
    assert "Aturan Pengaman: Domain Lamaran Tanpa DNS" in labels
    assert "Penyesuaian Penalaran AI" not in labels
