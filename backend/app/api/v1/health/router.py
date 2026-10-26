from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.config import APP_VERSION, BUILD_TIME, GIT_COMMIT
from app.database.postgres_client import get_db
from app.services.llm.verifin_reasoning import check_ai_status
from app.services.osint.searxng_client import is_searxng_available

router = APIRouter()


@router.get("/health", summary="Cek Kesehatan Server & API")
async def health_check(db: Session = Depends(get_db)):
    postgres_status = "healthy"
    postgres_details = "connected"

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        postgres_status = "unhealthy"
        postgres_details = "tidak terhubung"

    try:
        ai_status = await check_ai_status()
    except Exception:
        ai_status = {"status": "error", "detail": "tidak dapat dicek"}

    overall_status = "ok"
    if postgres_status == "unhealthy":
        overall_status = "degraded"

    return {
        "status": overall_status,
        "service": "verifin-backend",
        "version": APP_VERSION,
        "git_commit": GIT_COMMIT,
        "build_time": BUILD_TIME,
        "database": {
            "postgres": postgres_status,
            "details": postgres_details
        },
        "llm": ai_status,
        # Hanya mesin pencari yang benar-benar dicek di sini; sumber lain (OSM, Kaspersky,
        # situs perusahaan) dicek per verifikasi dan statusnya tercatat di laporan kasus.
        "osint_services": {
            "searxng": "online" if is_searxng_available() else "offline",
        }
    }
