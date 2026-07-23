"""
Latih TF-IDF + LogisticRegression di EMSCAD — menjadikan klaim "TF-IDF (paper22)"
kenyataan (menggantikan rule-based murni sebagai sinyal utama Layer-1).

Output:
  - app/services/nlp/model/tfidf_vectorizer.pkl
  - app/services/nlp/model/lr_classifier.pkl
  - app/services/nlp/model/model_meta.json  (metrik holdout + info training)

Model ini dilatih pada teks loker bahasa Inggris (EMSCAD). Untuk loker Indonesia,
pipeline tetap memakai gabungan sinyal (model ML + rule-based Indonesia) — lihat
integrasi di classifier.py (ML sebagai sinyal kuat, rule-based sebagai pelengkap).
"""
from __future__ import annotations
import csv, json, os, time

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import (precision_score, recall_score, f1_score,
                             roc_auc_score, accuracy_score, confusion_matrix)
import joblib

DATASET = "/Users/fizualstd/Documents/GitHub/_LOMBA/verifin-app/dataset/fake_job_postings.csv"
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "services", "nlp", "model")
os.makedirs(MODEL_DIR, exist_ok=True)

def build_text(row: dict) -> str:
    parts = [row.get("title") or "", row.get("company_profile") or "",
             row.get("description") or "", row.get("requirements") or "",
             row.get("benefits") or "", row.get("salary_range") or ""]
    return "\n".join(p for p in parts if p.strip())

def main():
    X, y = [], []
    with open(DATASET, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            lab = (row.get("fraudulent") or "").strip()
            if lab not in ("0", "1"):
                continue
            txt = build_text(row)
            if txt.strip():
                X.append(txt); y.append(int(lab))
    print(f"Dataset: {len(X)} sampel (fraud={sum(y)}, valid={len(y)-sum(y)})")

    Xtr, Xte, ytr, yte = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)

    # TF-IDF (sesuai paper22) + LogisticRegression (cepat & terinterpretasi)
    vec = TfidfVectorizer(
        lowercase=True, stop_words="english",
        ngram_range=(1, 2), max_features=20000, min_df=2)
    t0 = time.perf_counter()
    Xtr_v = vec.fit_transform(Xtr)
    Xte_v = vec.transform(Xte)

    clf = LogisticRegression(
        max_iter=1000, class_weight="balanced",  # penting: data timpang 866 vs 17014
        C=1.0, solver="liblinear", random_state=42)
    clf.fit(Xtr_v, ytr)
    train_sec = time.perf_counter() - t0

    proba = clf.predict_proba(Xte_v)[:, 1]
    pred = (proba >= 0.5).astype(int)
    cm = confusion_matrix(yte, pred).tolist()
    metrics = {
        "n_train": len(Xtr), "n_test": len(Xte),
        "n_fraud_total": int(sum(y)), "n_valid_total": int(len(y) - sum(y)),
        "accuracy": round(accuracy_score(yte, pred), 4),
        "precision": round(precision_score(yte, pred, zero_division=0), 4),
        "recall": round(recall_score(yte, pred, zero_division=0), 4),
        "f1": round(f1_score(yte, pred, zero_division=0), 4),
        "roc_auc": round(roc_auc_score(yte, proba), 4),
        "confusion_matrix_[[tn,fp],[fn,tp]]": cm,
        "train_sec": round(train_sec, 2),
        "vectorizer": "TfidfVectorizer(1-2gram, max_features=20000, stop_words=english)",
        "classifier": "LogisticRegression(class_weight=balanced, C=1.0)",
        "dataset": "EMSCAD fake_job_postings.csv (17.880 baris)",
        "note": "Model Layer-1 untuk teks Inggris (EMSCAD). Digabung dgn rule-based Indonesia di classifier.py.",
    }
    print(json.dumps(metrics, indent=2))

    joblib.dump(vec, os.path.join(MODEL_DIR, "tfidf_vectorizer.pkl"))
    joblib.dump(clf, os.path.join(MODEL_DIR, "lr_classifier.pkl"))
    with open(os.path.join(MODEL_DIR, "model_meta.json"), "w") as f:
        json.dump(metrics, f, indent=2)
    print("\nModel tersimpan di:", MODEL_DIR)

if __name__ == "__main__":
    main()
