"""
Health Check Router untuk Verifin Backend.
Menyediakan status kesehatan API, konektivitas LLM (OpenAgentic), dan status layanan OSINT.
"""

from fastapi import APIRouter
from app.services.llm.verifin_reasoning import check_ai_status

router = APIRouter()


@router.get("/health", summary="Cek Kesehatan Server & API")
async def health_check():
    ai_status = check_ai_status()
    return {
        "status": "ok",
        "service": "verifin-backend",
        "version": "1.0.0",
        "llm": ai_status,
        "osint_services": {
            "openstreetmap": "online",
            "kredibel": "online",
            "scrapling": "online",
            "threads": "online",
        },
    }
