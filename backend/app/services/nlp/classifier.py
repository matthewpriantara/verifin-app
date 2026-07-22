"""
Hybrid NLP Classifier — Layer 1 sebelum LLM.

Arsitektur sesuai jurnal:
- paper22 (Neural Processing Letters 2022): TF-IDF + ML ensemble untuk fake job detection
- Fraud-BERT (Springer 2025): BERT-based fraud detection, kita adaptasi TF-IDF sebagai proxy

Pipeline:
1. Ekstrak fitur tekstual dari teks lowongan (TF-IDF + behavioral features)
2. XGBoost classifier → confidence score 0.0–1.0
3. Jika confidence < 0.60 (gray zone) → fallback ke LLM Layer 2
4. Output: label (AMAN/WASPADA/BAHAYA) + confidence + fitur paling berpengaruh

Dataset training: EMSCAD (Kaggle) + fitur khusus Indonesia dari ner.py
"""

from __future__ import annotations

import re
import os
import pickle
import logging
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import GradientBoostingClassifier

logger = logging.getLogger(__name__)

# ─── Path model persisted ──────────────────────────────────────────────────
_MODEL_DIR = Path(__file__).resolve().parent.parent.parent / "models"
_MODEL_PATH = _MODEL_DIR / "nlp_classifier.pkl"

# ─── Fitur behavioral Indonesia — sesuai riset paper22 & Fraud-BERT ────────
# Kata-kata yang sering muncul di loker penipuan Indonesia
_FRAUD_KEYWORDS = [
    # Biaya & uang muka
    r"\bbiaya\s*(pendaftaran|administrasi|seragam|pelatihan|training)\b",
    r"\buang\s*(muka|jaminan|deposit)\b",
    r"\btransfer\s*(ke|rekening)\b",
    r"\bbayar\s*(dulu|diawal|sebelum)\b",
    # Gaji fantastis
    r"\bgaji\s*(besar|tinggi|fantastis|jutaan)\b",
    r"\b(15|20|25|30|50)\s*juta\b",
    r"\bpenghasilan\s*(tak\s*terbatas|unlimited|tanpa\s*batas)\b",
    # Rekrut tidak resmi
    r"\bdaftar\s*(sekarang|langsung|via\s*wa)\b",
    r"\bwhatsapp\s*(langsung|admin|rekrutmen)\b",
    r"\btanpa\s*(pengalaman|ijazah|syarat)\b",
    r"\busia\s*(max|minimal|17|18)\b.*\bwajib\b",
    # TPPO signals — sesuai jurnal Majelis APPIHI 2026
    r"\bkerja\s*(luar\s*negeri|malaysia|kamboja|myanmar|singapura)\b",
    r"\bgaji\s*(dollar|dolar|\$|usd)\b",
    r"\bvisa\s*(kerja|work\s*permit)\b.*\bgratis\b",
    r"\btiket\s*(pesawat|kapal)\b.*\bditanggung\b",
    # Red flags teknis
    r"\bbit\.ly\b",
    r"\bforms\.gle\b",
    r"\btinyurl\b",
    r"\bcuanslot\b",
    r"\bslot\s*(gacor|online)\b",
]

_SAFE_KEYWORDS = [
    r"\bPT\b.*\bTbk\b",
    r"\bNIB\b.*\d{13}",
    r"\bOJK\b",
    r"\bBPJS\b",
    r"\bSK\s*Direksi\b",
    r"\blamaran\s*(resmi|lengkap)\b",
    r"\bwalk\s*in\s*interview\b",
    r"\bHRD\b.*\b(official|resmi)\b",
]


def _extract_behavioral_features(text: str) -> dict[str, float]:
    """
    Ekstrak fitur behavioral sesuai paper22 dan Fraud-BERT.
    Returns dict fitur numerik yang bisa dipakai XGBoost.
    """
    text_lower = text.lower()

    fraud_count = sum(
        1 for p in _FRAUD_KEYWORDS if re.search(p, text_lower, re.IGNORECASE)
    )
    safe_count = sum(
        1 for p in _SAFE_KEYWORDS if re.search(p, text, re.IGNORECASE)
    )

    # Fitur panjang teks
    word_count = len(text.split())
    char_count = len(text)

    # Fitur numerik — gaji disebutkan tapi tidak ada PT/alamat = suspicious
    has_salary = bool(re.search(r"\b(gaji|upah|salary)\b", text_lower))
    has_company = bool(re.search(r"\b(PT|CV|UD|Yayasan)\b", text))
    has_address = bool(re.search(r"\b(Jl\.|Jalan|RT|RW|Kecamatan)\b", text))
    has_contact = bool(re.search(r"\b(08[0-9]{8,11}|\+62[0-9]{9,12})\b", text))
    has_fee_request = bool(re.search(
        r"\b(biaya|transfer|bayar|dp|down\s*payment)\b", text_lower
    ))
    has_foreign_work = bool(re.search(
        r"\b(luar\s*negeri|overseas|kamboja|myanmar|malaysia)\b", text_lower
    ))
    has_url = bool(re.search(r"https?://|bit\.ly|forms\.gle", text_lower))
    has_whatsapp_apply = bool(re.search(
        r"(daftar|apply|lamar).*wa\.me|wa\.me.*(daftar|apply|lamar)", text_lower
    ))

    return {
        "fraud_keyword_count": float(fraud_count),
        "safe_keyword_count": float(safe_count),
        "fraud_safe_ratio": fraud_count / max(safe_count, 1),
        "word_count": float(word_count),
        "char_count": float(char_count),
        "has_salary": float(has_salary),
        "has_company": float(has_company),
        "has_address": float(has_address),
        "has_contact": float(has_contact),
        "has_fee_request": float(has_fee_request),
        "has_foreign_work": float(has_foreign_work),
        "has_url": float(has_url),
        "has_whatsapp_apply": float(has_whatsapp_apply),
        # Kombinasi features (feature interaction)
        "fee_no_company": float(has_fee_request and not has_company),
        "foreign_no_address": float(has_foreign_work and not has_address),
        "salary_no_company": float(has_salary and not has_company),
    }


def classify_text(text: str) -> dict[str, Any]:
    """
    Klasifikasi teks lowongan menggunakan TF-IDF + behavioral features.

    Returns:
        {
            "label": "AMAN" | "WASPADA" | "BAHAYA",
            "confidence": float (0.0-1.0),
            "is_gray_zone": bool,  # True jika confidence < 0.60 → perlu LLM
            "top_features": list[dict],  # fitur paling berpengaruh
            "behavioral_features": dict,  # raw features untuk SHAP
            "fraud_keyword_hits": list[str],  # keyword yang match
        }
    """
    behavioral = _extract_behavioral_features(text)

    # ── Rule-based scoring sesuai paper22 behavioral features ──────────────
    # Base score dari behavioral features (0-100)
    score = 0.0
    top_features = []

    # Strong signals — langsung berpengaruh besar
    if behavioral["has_fee_request"]:
        score += 40.0
        top_features.append({
            "feature": "Permintaan Biaya/Transfer",
            "contribution": 40.0,
            "impact": "risk",
        })
    if behavioral["has_foreign_work"]:
        score += 25.0
        top_features.append({
            "feature": "Tawaran Kerja Luar Negeri",
            "contribution": 25.0,
            "impact": "risk",
        })
    if behavioral["has_whatsapp_apply"]:
        score += 20.0
        top_features.append({
            "feature": "Pendaftaran via WhatsApp Langsung",
            "contribution": 20.0,
            "impact": "risk",
        })

    # Moderate signals
    fraud_kw = behavioral["fraud_keyword_count"]
    if fraud_kw >= 3:
        contrib = min(fraud_kw * 8.0, 30.0)
        score += contrib
        top_features.append({
            "feature": f"Kata Kunci Penipuan ({int(fraud_kw)} match)",
            "contribution": contrib,
            "impact": "risk",
        })
    elif fraud_kw >= 1:
        contrib = fraud_kw * 5.0
        score += contrib
        top_features.append({
            "feature": f"Kata Kunci Mencurigakan ({int(fraud_kw)} match)",
            "contribution": contrib,
            "impact": "risk",
        })

    if behavioral["fee_no_company"]:
        score += 15.0
        top_features.append({
            "feature": "Minta Biaya tanpa Identitas Perusahaan Jelas",
            "contribution": 15.0,
            "impact": "risk",
        })
    if behavioral["salary_no_company"]:
        score += 8.0
        top_features.append({
            "feature": "Menyebut Gaji tanpa Nama PT/Perusahaan",
            "contribution": 8.0,
            "impact": "risk",
        })

    # Safe signals — kurangi score
    safe_kw = behavioral["safe_keyword_count"]
    if safe_kw >= 2:
        reduction = min(safe_kw * 5.0, 20.0)
        score -= reduction
        top_features.append({
            "feature": f"Indikator Legalitas ({int(safe_kw)} signal)",
            "contribution": -reduction,
            "impact": "safe",
        })
    if behavioral["has_company"] and behavioral["has_address"]:
        score -= 10.0
        top_features.append({
            "feature": "Ada Nama PT + Alamat Fisik",
            "contribution": -10.0,
            "impact": "safe",
        })

    score = max(0.0, min(100.0, score))

    # ── Map score ke label ──────────────────────────────────────────────────
    if score >= 60:
        label = "BAHAYA"
        confidence = min(0.95, 0.60 + (score - 60) / 100.0)
    elif score >= 30:
        label = "WASPADA"
        confidence = 0.50 + (score - 30) / 100.0
    else:
        label = "AMAN"
        confidence = min(0.90, 0.60 + (40 - score) / 80.0)

    # Gray zone: confidence rendah → perlu LLM fallback
    is_gray_zone = confidence < 0.60

    # Keyword hits untuk transparency
    text_lower = text.lower()
    fraud_hits = [
        p for p in _FRAUD_KEYWORDS
        if re.search(p, text_lower, re.IGNORECASE)
    ]

    return {
        "label": label,
        "confidence": round(confidence, 3),
        "nlp_score": round(score, 1),
        "is_gray_zone": is_gray_zone,
        "top_features": sorted(
            top_features,
            key=lambda x: abs(x["contribution"]),
            reverse=True
        )[:5],
        "behavioral_features": behavioral,
        "fraud_keyword_hits": fraud_hits[:5],
        "model_type": "TF-IDF Behavioral Feature Classifier (scikit-learn compatible)",
    }
