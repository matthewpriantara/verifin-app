"""
NLP Pre-Screening — Layer 1 (nonaktif sementara).

Behavioral Feature Scoring rule-based terinspirasi paper22 (Neural Processing
Letters 2022). Dinonaktifkan karena dataset berlabel bahasa Indonesia belum
tersedia — roadmap: fine-tune IndoBERT setelah dataset terkumpul.

Pipeline tetap berjalan normal; nlp_result={} diterima gracefully oleh
SHAP explainer dan LLM reasoning.
"""

from typing import Any


def classify_text(text: str) -> dict[str, Any]:
    """Stub — NLP Layer 1 nonaktif. Return dict kosong, pipeline tidak terpengaruh."""
    return {}
