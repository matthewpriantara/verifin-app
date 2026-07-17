import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

from app.database.postgres_client import Base


class JobCase(Base):
    """
    Riwayat verifikasi lowongan — fondasi case memory (exact-match HP/email/PT).
    Vector/graph (pgvector, Neo4j) ditunda ke fase berikutnya.
    """

    __tablename__ = "job_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_text_hash = Column(String(64), unique=True, nullable=False, index=True)
    source = Column(String(16), nullable=True)  # text | image
    raw_text_preview = Column(Text, nullable=True)

    company_name = Column(String(255), nullable=True, index=True)
    companies = Column(JSONB, nullable=True)
    phones = Column(JSONB, nullable=True)
    emails = Column(JSONB, nullable=True)
    urls = Column(JSONB, nullable=True)
    addresses = Column(JSONB, nullable=True)
    salaries = Column(JSONB, nullable=True)
    entities = Column(JSONB, nullable=True)

    verdict = Column(String(10), nullable=False)
    risk_score = Column(Integer, nullable=False)
    llm_output = Column(JSONB, nullable=True)
    osint_summary = Column(JSONB, nullable=True)
    osint_failed = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<JobCase(id={self.id}, verdict={self.verdict}, risk_score={self.risk_score})>"


class AhuWhitelist(Base):
    __tablename__ = "ahu_whitelist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(255), nullable=False, index=True)
    legal_type = Column(String(10), nullable=False)
    synced_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self):
        return f"<AhuWhitelist(id={self.id}, company_name={self.company_name}, legal_type={self.legal_type})>"
