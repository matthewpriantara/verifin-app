from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database.postgres_client import get_db

router = APIRouter()

@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    postgres_status = "healthy"
    details = {}
    
    try:
        # Execute a lightweight query to test the PostgreSQL connection
        db.execute(text("SELECT 1"))
        details["postgres"] = "connected"
    except Exception as e:
        postgres_status = "unhealthy"
        details["postgres"] = f"error: {str(e)}"
        
    return {
        "status": "healthy" if postgres_status == "healthy" else "degraded",
        "database": postgres_status,
        "details": details
    }
