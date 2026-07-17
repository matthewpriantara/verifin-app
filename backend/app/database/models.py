import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.database.postgres_client import Base

class JobCase(Base):
    __tablename__ = "job_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_text_hash = Column(String(64), unique=True, nullable=False, index=True)
    embedding = Column(Vector(384), nullable=True)  # 384-dimension vector for semantic search
    verdict = Column(String(10), nullable=False)    # AMAN, WASPADA, BAHAYA
    risk_score = Column(Integer, nullable=False)    # 0 to 100
    llm_output = Column(JSONB, nullable=True)       # Store reasons, factors, recommendations, etc.
    osint_failed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<JobCase(id={self.id}, verdict={self.verdict}, risk_score={self.risk_score})>"


class AhuWhitelist(Base):
    __tablename__ = "ahu_whitelist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(255), nullable=False, index=True)
    legal_type = Column(String(10), nullable=False)  # PT or CV
    synced_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<AhuWhitelist(id={self.id}, company_name={self.company_name}, legal_type={self.legal_type})>"
