"""
Pydantic Schema untuk endpoint verifikasi lowongan kerja Verifin.
Mendefinisikan format request dan response secara ketat agar API konsisten.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


# ─────────────────────────────────────────────────────────────────────────────
# REQUEST SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class TextVerifyRequest(BaseModel):
    """Request body untuk endpoint POST /verify/text"""
    text: str = Field(
        ...,
        description="Teks lowongan kerja yang ingin diverifikasi (bisa berupa teks kasar atau yang sudah diformat).",
        min_length=10,
        max_length=10000,
        examples=["PT. Maju Sejahtera membuka lowongan untuk posisi Marketing. Kirim CV ke hrd@majusejahtera.com atau WA 081234567890. Alamat: Jl. Sudirman No. 5, Jakarta."]
    )
    include_raw_text: bool = Field(
        default=True,
        description="Jika True, teks asli akan ikut disertakan dalam prompt LLM sebagai konteks tambahan."
    )


# ─────────────────────────────────────────────────────────────────────────────
# RESPONSE SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class ExtractedEntities(BaseModel):
    """Entitas yang berhasil diekstrak dari teks/gambar."""
    companies: List[str] = Field(default=[], description="Nama perusahaan/instansi.")
    contacts: List[str] = Field(default=[], description="Nomor HP dalam format internasional (+62...).")
    emails: List[str] = Field(default=[], description="Alamat email.")
    urls: List[str] = Field(default=[], description="URL/website yang ditemukan.")
    addresses: List[str] = Field(default=[], description="Alamat fisik.")
    salaries: List[str] = Field(default=[], description="Informasi gaji jika ada.")


class VerifyResponse(BaseModel):
    """Response utama untuk semua endpoint verifikasi."""
    verdict: str = Field(
        description="Keputusan AI: AMAN, WASPADA, BAHAYA, atau ERROR.",
        examples=["WASPADA"]
    )
    risk_score: int = Field(
        description="Skor risiko penipuan dari 0 (sangat aman) hingga 100 (sangat berbahaya).",
        ge=0,
        le=100
    )
    summary: str = Field(
        description="Ringkasan singkat alasan mengapa verdict ini diberikan."
    )
    risk_factors: List[str] = Field(
        default=[],
        description="Daftar faktor risiko yang ditemukan AI."
    )
    safe_factors: List[str] = Field(
        default=[],
        description="Daftar faktor yang mendukung keabsahan lowongan."
    )
    recommendations: List[str] = Field(
        default=[],
        description="Saran tindakan untuk pencari kerja."
    )
    entities: Optional[ExtractedEntities] = Field(
        default=None,
        description="Entitas yang berhasil diekstrak dari input."
    )
    model_used: Optional[str] = Field(
        default=None,
        description="Model LLM yang digunakan untuk analisis."
    )


class OllamaStatusResponse(BaseModel):
    """Response untuk endpoint health check Ollama."""
    ollama_running: bool
    hermes_available: bool
    available_models: List[str]
    target_model: str
