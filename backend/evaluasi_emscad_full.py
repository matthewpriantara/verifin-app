"""
Evaluasi Layer-1 Fraud Classifier Verifin (classify_text) pada EMSCAD PENUH.

Dataset : EMSCAD (Employment Scam Aegean Dataset) — 17.880 loker
          (17.014 valid / 866 fraud), dipakai paper22 (Rustam et al. 2022).
Metode  : classify_text (rule-based behavioral, TANPA LLM) — cepat, bisa
          dievaluasi ke seluruh 17.880 baris dalam hitungan detik.
Label   : positif(1)=fraudulent, negatif(0)=valid.
Prediksi: 1 jika label classifier ∈ {BAHAYA, WASPADA}, else 0.
Metrik  : Precision, Recall, F1, ROC-AUC, confusion matrix, latency.

Catatan jujur: ini mengukur KINERJA LAYER-1 SAJA (pre-screening), bukan
pipeline penuh (yang menambah OSINT+LLM dan lebih akurat tapi lambat).
"""
from __future__ import annotations
import csv, json, time, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.services.nlp.classifier import classify_text

DATASET = "/Users/fizualstd/Documents/GitHub/_LOMBA/verifin-app/dataset/fake_job_postings.csv"
OUT = "/Users/fizualstd/Documents/GitHub/_LOMBA/gemastik19/test/hasil-test-raw/evaluasi-emscad.json"

def build_text(row: dict) -> str:
    parts = [
        row.get("title") or "",
        row.get("company_profile") or "",
        row.get("description") or "",
        row.get("requirements") or "",
        row.get("benefits") or "",
        row.get("salary_range") or "",
    ]
    return "\n".join(p for p in parts if p.strip())

def main():
    rows = []
    with open(DATASET, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            lab = (row.get("fraudulent") or "").strip()
            if lab not in ("0", "1"):
                continue
            txt = build_text(row)
            if not txt.strip():
                continue
            rows.append((txt, int(lab)))
    n = len(rows)
    print(f"Dataset dimuat: {n} baris (fraud={sum(l for _,l in rows)}, valid={n-sum(l for _,l in rows)})")

    y_true, y_pred, scores, lat = [], [], [], []
    t_start = time.perf_counter()
    for i, (txt, lab) in enumerate(rows):
        t0 = time.perf_counter()
        out = classify_text(txt)
        lat.append((time.perf_counter() - t0) * 1000)
        y_true.append(lab)
        # Fraud biner = label BAHAYA (threshold 45, dikalibrasi F1-optimal).
        # WASPADA diperlakukan sebagai 'perlu cek', bukan positif fraud.
        y_pred.append(1 if out["label"] == "BAHAYA" else 0)
        scores.append(out["nlp_score"])
        if (i + 1) % 3000 == 0:
            print(f"  ... {i+1}/{n}")
    total_sec = time.perf_counter() - t_start

    from sklearn.metrics import (precision_score, recall_score, f1_score,
                                 roc_auc_score, confusion_matrix, accuracy_score)
    cm = confusion_matrix(y_true, y_pred).tolist()
    res = {
        "dataset": "EMSCAD (fake_job_postings.csv) penuh",
        "n_samples": n,
        "positif_fraud": sum(y_true),
        "negatif_valid": n - sum(y_true),
        "komponen": "Layer-1 classify_text (rule-based behavioral, TANPA LLM/OSINT)",
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "precision": round(precision_score(y_true, y_pred, zero_division=0), 4),
        "recall": round(recall_score(y_true, y_pred, zero_division=0), 4),
        "f1": round(f1_score(y_true, y_pred, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(y_true, scores), 4),
        "confusion_matrix_[[tn,fp],[fn,tp]]": cm,
        "latency_ms_avg": round(sum(lat) / len(lat), 3),
        "latency_ms_max": round(max(lat), 3),
        "total_eval_sec": round(total_sec, 2),
        "catatan": ("Ini kinerja LAYER-1 saja (pre-screening rule-based). Pipeline penuh "
                    "menambah OSINT+LLM untuk menaikkan recall pada kasus gray-zone."),
    }
    print(json.dumps(res, ensure_ascii=False, indent=2))
    with open(OUT, "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print("\nDisimpan ke:", OUT)

if __name__ == "__main__":
    main()
