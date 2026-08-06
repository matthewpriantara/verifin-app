import logging
import sys

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from app.api.v1.verify.router import router as verify_router
from app.api.v1.health.router import router as health_router
from app.api.v1.community.router import router as community_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Warm OCR model di startup agar request pertama tidak cold-load lama."""
    try:
        from app.services.ocr import get_ocr_model
        get_ocr_model()
        logger.info("PaddleOCR model warmed")
    except Exception as exc:
        logger.warning("OCR warmup skipped: %s", exc)
    yield


app = FastAPI(title="Verifin OSINT API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(verify_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")
app.include_router(community_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
