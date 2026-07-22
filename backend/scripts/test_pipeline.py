"""
Verifin Testing Script — Full Pipeline Test
Jalankan dengan: cd verifin-app/backend && PYTHONPATH=. .venv311/bin/python scripts/test_pipeline.py
"""
import asyncio
import json
import time
from datetime import datetime

from app.database.postgres_client import SessionLocal
from app.database.models import JobCase
from app.api.v1.verify.router import _run_osint_on_entities
from app.services.ner import extract_entities_from_text
from app.services.nlp.classifier import classify_text
from app.services.llm.verifin_reasoning import analyze_with_verifin
from app.services.xai.shap_explainer import explain_verification_shap

# ─── Test cases ───────────────────────────────────────────────────────────────
TEST_CASES = [
    {
        "id": "TC-01",
        "label": "LEGIT — Esthy Group (F&B established company)",
        "text": """Esthy Group membuka lowongan
Pramuniaga - Manager Operasional - HR Officer - Sosial Media Content Specialist - Helper Produksi
Esthy Group adalah perusahaan F&B yang menaungi usaha Restoran Waroeng Mbok Reneo dan 7 Outlet Cake & Bakery telah berdiri selama lebih dari 25 tahun.

Ringkasan
Pendidikan: SMA/SMK, D3, S1
Lokasi Kerja: Esthy Cake & Bakery 2 Jl. Raya Solo - Yogyakarta No.2 Bogem, Tamanmartani, Prambanan, Sleman, DIY

Kirim Lamaran
Email: hrr.esthygroup@gmail.com
No. Telepon: +6285117680972"""
    },
    {
        "id": "TC-02",
        "label": "SCAM — Minta biaya + kerja luar negeri + WA langsung",
        "text": """URGENT HIRING! Kerja dari rumah gaji 8-15 juta per bulan. Tidak perlu pengalaman.
Daftar sekarang bayar biaya administrasi Rp150.000 transfer ke rekening BCA 1234567890 an. ADMIN LOKER.
WA langsung ke 082134567890. Kerja di luar negeri Malaysia Singapore gaji dollar. Berangkat minggu ini!
Daftar via: bit.ly/daftarloker2026"""
    },
    {
        "id": "TC-03",
        "label": "BORDERLINE — Lowongan informal tanpa identitas perusahaan jelas",
        "text": """Dicari karyawan toko untuk posisi kasir dan pramuniaga.
Lokasi: Jl. Malioboro No. 45, Yogyakarta
Gaji: Rp2.500.000/bulan + bonus
Hubungi: 081234567890 (WA only)
Syarat: jujur, rajin, mau belajar. Perempuan/Laki-laki."""
    }
]


async def run_single_test(tc: dict) -> dict:
    """Jalankan satu test case melalui full pipeline."""
    text = tc["text"]
    t0 = time.time()

    entities = extract_entities_from_text(text)
    nlp_res = classify_text(text)
    osint_res = await _run_osint_on_entities(entities)
    analysis = await analyze_with_verifin(entities, osint_res, raw_text=text)
    shap_res = explain_verification_shap(
        risk_score=analysis["risk_score"],
        verdict=analysis["verdict"],
        osint_results=osint_res,
        risk_factors=analysis.get("risk_factors", []),
        safe_factors=analysis.get("safe_factors", []),
        nlp_result=nlp_res,
        network_context=osint_res.get("fraud_network", {}),
    )

    elapsed = round(time.time() - t0, 2)

    return {
        "test_id": tc["id"],
        "label": tc["label"],
        "elapsed_seconds": elapsed,
        "verdict": analysis["verdict"],
        "risk_score": analysis["risk_score"],
        "summary": analysis.get("summary", ""),
        "risk_factors": analysis.get("risk_factors", []),
        "safe_factors": analysis.get("safe_factors", []),
        "recommendations": analysis.get("recommendations", []),
        "entities": entities,
        "nlp_result": {
            "label": nlp_res.get("label"),
            "confidence": nlp_res.get("confidence"),
            "nlp_score": nlp_res.get("nlp_score"),
            "is_gray_zone": nlp_res.get("is_gray_zone"),
            "top_features": nlp_res.get("top_features", []),
        },
        "osint_summary": {
            "domain_age_years": (osint_res.get("domain") or {}).get("age_years"),
            "domain_is_new": (osint_res.get("domain") or {}).get("is_new"),
            "phones_checked": len(osint_res.get("phones") or []),
            "phones_fraud": sum(
                1 for p in (osint_res.get("phones") or []) if p.get("reported_fraud")
            ),
            "address_found": any(
                a.get("address_found") or a.get("found")
                for a in (osint_res.get("address_validations") or [])
            ),
            "web_risk_flags": (osint_res.get("web") or {}).get("risk_flags", []),
            "web_safe_flags": (osint_res.get("web") or {}).get("safe_flags", []),
            "social_found": (osint_res.get("threads") or {}).get("found", False),
            "social_platforms": (osint_res.get("threads") or {}).get("platform_hits", {}),
        },
        "shap_summary": {
            "model_type": shap_res.get("model_type"),
            "base_value": shap_res.get("base_value"),
            "final_risk_score": shap_res.get("final_risk_score"),
            "top_risk_features": shap_res.get("top_risk_features", []),
            "top_safe_features": shap_res.get("top_safe_features", []),
            "feature_count": len(shap_res.get("feature_contributions", [])),
            "summary": shap_res.get("summary"),
        },
        "model_used": analysis.get("model_used"),
    }


async def main():
    # Clear DB cache untuk fresh test
    db = SessionLocal()
    try:
        deleted = db.query(JobCase).delete()
        db.commit()
        print(f"[INFO] Cleared {deleted} cached cases from DB")
    finally:
        db.close()

    results = []
    print(f"\n{'='*60}")
    print(f"VERIFIN PIPELINE TEST — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    for tc in TEST_CASES:
        print(f"[TEST] {tc['id']} — {tc['label']}")
        try:
            result = await run_single_test(tc)
            results.append({"status": "PASS", **result})
            print(f"  Verdict:    {result['verdict']} ({result['risk_score']}/100)")
            print(f"  NLP Layer:  {result['nlp_result']['label']} (conf={result['nlp_result']['confidence']})")
            print(f"  Elapsed:    {result['elapsed_seconds']}s")
            print(f"  Addr found: {result['osint_summary']['address_found']}")
            print(f"  Social:     {result['osint_summary']['social_found']}")
            print()
        except Exception as e:
            print(f"  ERROR: {e}\n")
            results.append({"status": "ERROR", "test_id": tc["id"], "error": str(e)})

    # Print full JSON
    print("\n=== RAW JSON OUTPUT ===")
    print(json.dumps(results, ensure_ascii=False, indent=2))

    return results


if __name__ == "__main__":
    asyncio.run(main())
