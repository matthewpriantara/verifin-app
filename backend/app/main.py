import logging
import sys

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


# Uvicorn's default logging config does not always lower the level of
# application loggers. Keep Verifin pipeline logs visible during local runs.
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    force=True,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("ppocr").setLevel(logging.WARNING)
logging.getLogger("app").setLevel(logging.DEBUG)
logging.getLogger("scrapling").propagate = False

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


app = FastAPI(
    title="Verifin API",
    version="1.0.0",
    description=(
        "API verifikasi lowongan kerja berbasis OSINT multi-layer.\n\n"
        "**Pipeline:** OCR → NER → LLM Entity Extraction → OSINT Paralel "
        "(Kaspersky, SERP, Address, Company, WHOIS, Social Media, Web Evidence) "
        "→ Fraud Network → SHAP XAI → Response\n\n"
        "**Sumber data:** Kaspersky Who Calls ID, Kredibel SERP, DDG/Yahoo/Bing, "
        "Nominatim/Overpass GIS, AHU/OSS SERP, WHOIS, Community Reports (DB)\n\n"
        "**LLM:** Kimi K3 via OpenAgentic"
    ),
    lifespan=lifespan,
)

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
