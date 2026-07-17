from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.verify.router import router as verify_router
from app.api.v1.health.router import router as health_router

app = FastAPI(title="Verifin OSINT API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Hubungkan router
app.include_router(verify_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
