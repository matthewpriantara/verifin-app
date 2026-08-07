"""
NLP Pre-Screening — Layer 1 (STUB, nonaktif).

Behavioral Feature Scoring rule-based terinspirasi paper22 (Neural Processing
Letters 2022). Dinonaktifkan karena dataset berlabel bahasa Indonesia belum
tersedia — roadmap: fine-tune IndoBERT setelah dataset terkumpul.

Pipeline tetap berjalan normal; metadata STUB diekspos jujur ke response agar
FE/audit tidak mengira layer ini aktif.
"""

from typing import Any

def classify_text(text: str) -> dict[str, Any]:
    """Stub — NLP Layer 1 nonaktif. Metadata jujur, pipeline tidak terpengaruh."""
    return {
        "enabled": False,
        "status": "STUB",
        "reason": "No labeled Indonesian dataset — roadmap: fine-tune IndoBERT",
        "behavioral_features": {},
    }
