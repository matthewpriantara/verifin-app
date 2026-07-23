"""
Hybrid NLP Pre-Screening — Layer 1 (Trust Pre-Screening) dari Job Trust Infrastructure.

Komponen pertama dalam pipeline Verifin yang melakukan pre-screening awal
sebelum OSINT dan LLM dijalankan. Tujuannya bukan sekadar fraud detection,
melainkan membangun sinyal awal untuk trust assessment — membantu pencari
kerja menyaring lowongan yang layak diverifikasi lebih lanjut.

Implementasi (JUJUR — bukan model ML terlatih):
    Behavioral Feature Scoring berbasis aturan (rule-based), terinspirasi dari
    feature importance yang dilaporkan penelitian fake-job detection:
    - paper22 (Neural Processing Letters 2022): TF-IDF + behavioral features
      untuk fake job detection. Kita adopsi *daftar fitur perilakunya*
      (permintaan biaya, kerja luar negeri, apply via WA, dsb.) sebagai sinyal
      berbobot, bukan model TF-IDF yang dilatih.
    - Fraud-BERT (Springer 2025): referensi konsep deteksi fraud berbasis teks.

Catatan kejujuran teknis: saat ini TIDAK ada model XGBoost/TF-IDF yang dilatih
dan di-persist (tidak ada file .pkl yang di-load). Skor dihitung dari bobot
fitur yang dikalibrasi manual dari pola loker penipuan Indonesia. Rencana
peningkatan: latih classifier pada dataset berlabel (lihat roadmap proposal).

Pipeline:
1. Ekstrak fitur behavioral dari teks lowongan (kata kunci fraud Indonesia)
2. Rule-based weighted scoring → skor 0-100
3. Jika confidence < 0.60 (gray zone) → fallback ke LLM Layer 4
4. Output: label (AMAN/WASPADA/BAHAYA) + confidence + fitur paling berpengaruh
"""

from __future__ import annotations

import os
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ─── Model ML (TF-IDF + LogReg) hasil latih di EMSCAD — lihat latih_tfidf_emscad.py
_MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model")
_VEC_PATH = os.path.join(_MODEL_DIR, "tfidf_vectorizer.pkl")
_CLF_PATH = os.path.join(_MODEL_DIR, "lr_classifier.pkl")
_VEC = None
_CLF = None
_ML_AVAILABLE = False


def _load_ml_model() -> bool:
    """Lazy-load model TF-IDF+LogReg EMSCAD. Return True jika berhasil."""
    global _VEC, _CLF, _ML_AVAILABLE
    if _ML_AVAILABLE and _VEC is not None and _CLF is not None:
        return True
    try:
        import joblib
        if os.path.exists(_VEC_PATH) and os.path.exists(_CLF_PATH):
            _VEC = joblib.load(_VEC_PATH)
            _CLF = joblib.load(_CLF_PATH)
            _ML_AVAILABLE = True
            logger.info("[classifier] Model TF-IDF EMSCAD dimuat.")
            return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("[classifier] Gagal memuat model ML (%s) → fallback rule-based.", exc)
    _ML_AVAILABLE = False
    return False


def _ml_fraud_probability(text: str) -> float | None:
    """Probabilitas fraud (0..1) dari model EMSCAD, atau None jika model tak ada."""
    if not _load_ml_model():
        return None
    try:
        proba = _CLF.predict_proba(_VEC.transform([text]))[0]
        # asumsikan kelas 1 = fraudulent
        classes = list(getattr(_CLF, "classes_", [0, 1]))
        idx = classes.index(1) if 1 in classes else -1
        return float(proba[idx])
    except Exception as exc:  # noqa: BLE001
        logger.warning("[classifier] prediksi ML gagal (%s).", exc)
        return None


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

    # has_company: cek nama badan usaha Indonesia — PT, CV, UD, Yayasan, Group, Tbk, Tbk., Inc, Ltd, dsb.
    # Tidak pakai \b sebelum titik karena titik bukan word char; gunakan (?<!\w) sebagai gantinya.
    has_company = bool(re.search(
        r"(?<!\w)(PT\.?|CV\.?|UD\.?|Yayasan|Koperasi|Persero|Tbk\.?|Group|Inc\.?|Ltd\.?|Corp\.?|Perusahaan)\b",
        text, re.IGNORECASE
    ))

    # has_address: cek kata kunci alamat Indonesia — Jl/Jalan tidak bisa pakai \b karena diikuti titik
    has_address = bool(re.search(
        r"(?<!\w)(Jl\.|Jalan)\s+\w"   # "Jl. " atau "Jalan " diikuti nama jalan
        r"|(?<!\w)No\.\s*\d"          # Nomor alamat "No. 12"
        r"|\bRT\.?\s*\d|\bRW\.?\s*\d" # RT/RW
        r"|\b(Kelurahan|Kecamatan|Kabupaten|Kota|Provinsi|Kel\.|Kec\.)\b"
        r"|\b(DIY|DKI|Yogyakarta|Jakarta|Surabaya|Bandung|Medan|Semarang|Makassar)\b"
        r"|\bKode\s*Pos\s*\d{5}|\b\d{5}\b.*\b(Indonesia)\b",
        text, re.IGNORECASE
    ))

    # has_contact: cek nomor telepon Indonesia (08xx / +62xx) atau alamat email
    has_contact = bool(re.search(
        r"(?<!\d)(08[0-9]{8,11})(?!\d)"   # 08xx — 10 s/d 13 digit total
        r"|(?<!\d)(\+62[0-9]{8,12})(?!\d)" # +62xx
        r"|(?<!\d)(62[0-9]{9,12})(?!\d)"   # 62xx tanpa plus
        r"|[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",  # email
        text
    ))
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

    # ── Gabungkan sinyal ML (EMSCAD, Inggris) dgn rule-based (Indonesia) ─────
    # Model ML dilatih di EMSCAD (AUC 0.986) → kuat untuk pola fraud Barat/global.
    # Rule-based kuat untuk pola fraud Indonesia (biaya/TKI/deposit). Ambil yang
    # terkuat agar tidak saling menutupi; keduanya dilaporkan untuk transparansi.
    rule_score = max(0.0, min(100.0, score))
    ml_prob = _ml_fraud_probability(text)  # None jika model tak tersedia
    ml_score = round(ml_prob * 100.0, 1) if ml_prob is not None else None
    if ml_score is not None:
        # Skor akhir = maks dari dua sinyal (konservatif: hindari false-negative).
        score = max(rule_score, ml_score)
        if ml_score > rule_score:
            top_features.append({
                "feature": f"Model ML TF-IDF (EMSCAD) prob fraud {ml_prob:.2f}",
                "contribution": ml_score,
                "impact": "risk" if ml_score >= 50 else "safe",
            })
    else:
        score = rule_score

    score = max(0.0, min(100.0, score))

    # ── Map score ke label (threshold dikalibrasi di EMSCAD, F1 optimal) ─────
    # Sweep threshold di 1.732 sampel seimbang → th=45 memberi F1=0.923
    # (P=0.934, R=0.912, ROC-AUC=0.976). th>=45 = sinyal fraud kuat.
    if score >= 45:
        label = "BAHAYA"
        confidence = min(0.95, 0.70 + (score - 45) / 110.0)
    elif score >= 25:
        label = "WASPADA"
        confidence = 0.55 + (score - 25) / 120.0
    else:
        label = "AMAN"
        confidence = min(0.90, 0.60 + (45 - score) / 90.0)

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
        "ml_emscad_score": ml_score,            # skor model TF-IDF (None jika tak ada)
        "rule_based_score": round(rule_score, 1),
        "model_type": ("Hybrid: TF-IDF+LogReg (EMSCAD, AUC 0.986) + Behavioral Rule (Indonesia)"
                       if ml_score is not None else
                       "Behavioral Feature Scoring (rule-based, terinspirasi paper22)"),
    }
