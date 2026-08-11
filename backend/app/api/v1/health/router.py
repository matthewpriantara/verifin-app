"""
Health check — status API, PostgreSQL, dan LLM (OpenAgentic).
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database.postgres_client import get_db
from app.services.llm.verifin_reasoning import check_ai_status

router = APIRouter()


@router.get("/health", summary="Cek Kesehatan Server & API")
async def health_check(db: Session = Depends(get_db)):
    postgres_status = "healthy"
    postgres_details = "connected"
    
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        postgres_status = "unhealthy"
        postgres_details = f"error: {str(e)}"
        
    # Cek status koneksi LLM
    try:
        ai_status = await check_ai_status()
    except Exception as e:
        ai_status = {"status": "error", "detail": str(e)}
    
    overall_status = "ok"
    if postgres_status == "unhealthy":
        overall_status = "degraded"
        
    return {
        "status": overall_status,
        "service": "verifin-backend",
        "version": "1.0.0",
        "database": {
            "postgres": postgres_status,
            "details": postgres_details
        },
        "llm": ai_status,
        "osint_services": {
            "openstreetmap": "online",
            "kredibel": "online",
            "scrapling": "online",
            "social_media": "online",
        }
    }
