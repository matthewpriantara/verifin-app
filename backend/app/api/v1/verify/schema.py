"""
Pydantic schema request dan response untuk endpoint verifikasi Verifin.
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import List, Optional, Dict, Any
from app.services.url_guard import validate_public_http_url


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


class UrlVerifyRequest(BaseModel):
    """Request body untuk endpoint POST /verify/url"""
    url: str = Field(
        ...,
        description="URL/Link postingan lowongan kerja (misal Instagram, Threads, LinkedIn, JobStreet, Facebook, atau website perusahaan).",
        examples=["https://www.threads.com/@sigit_gustian/post/Da7SVXVk85J"]
    )
    additional_text: Optional[str] = Field(
        default=None,
        description="Teks balasan/reply/komentar postingan atau caption tambahan jika lowongan memiliki detail di utas balasan.",
        examples=["Tugas lo ngapain aja? Handle trouble hardware... Daftar di link resmi ini: loker.staffinc.co/NEV7M"]
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return validate_public_http_url(value)


class ExtractedEntities(BaseModel):
    """Entitas yang berhasil diekstrak dari teks/gambar."""
    companies: List[str] = Field(default=[], description="Nama perusahaan/instansi.")
    contacts: List[str] = Field(default=[], description="Nomor HP dalam format internasional (+62...).")
    emails: List[str] = Field(default=[], description="Alamat email.")
    urls: List[str] = Field(default=[], description="URL/website yang ditemukan.")
    addresses: List[str] = Field(default=[], description="Alamat fisik.")
    location_candidates: List[str] = Field(
        default=[], description="Wilayah atau cabang yang disebutkan tanpa alamat fisik exact."
    )
    salaries: List[str] = Field(default=[], description="Informasi gaji jika ada.")


class VerifyResponse(BaseModel):
    """Response utama untuk semua endpoint verifikasi."""
    model_config = ConfigDict(protected_namespaces=())
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
    osint: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Bukti OSINT mentah (fakta scrape/API) untuk transparansi laporan."
    )
    shap_explanation: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Penjelasan SHAP value XAI untuk visualisasi dashboard."
    )


class LlmStatusResponse(BaseModel):
    """Response health check LLM (OpenAgentic)."""
    provider: str = "openagentic"
    configured: bool
    reachable: bool
    available_models: List[str] = []
    target_model: str
    detail: Optional[str] = None
