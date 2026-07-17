import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.database.postgres_client import Base


class JobCase(Base):
    """
    Riwayat verifikasi lowongan — fondasi case memory.
    embedding (pgvector) disiapkan untuk semantic search nanti; belum diisi.
    """

    __tablename__ = "job_cases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_text_hash = Column(String(64), unique=True, nullable=False, index=True)
    source = Column(String(16), nullable=True)  # text | image
    raw_text_preview = Column(Text, nullable=True)  # potongan teks (max ~2k)

    # Entities untuk exact-match memory (HP/email/PT)
    company_name = Column(String(255), nullable=True, index=True)
    companies = Column(JSONB, nullable=True)  # list[str]
    phones = Column(JSONB, nullable=True)  # list[str] E.164
    emails = Column(JSONB, nullable=True)  # list[str]
    urls = Column(JSONB, nullable=True)
    addresses = Column(JSONB, nullable=True)
    salaries = Column(JSONB, nullable=True)
    entities = Column(JSONB, nullable=True)  # full NER dump

    # Hasil analisis
    verdict = Column(String(10), nullable=False)  # AMAN, WASPADA, BAHAYA, ERROR
    risk_score = Column(Integer, nullable=False)  # 0-100
    llm_output = Column(JSONB, nullable=True)
    osint_summary = Column(JSONB, nullable=True)  # snapshot ringan, bukan full dump
    osint_failed = Column(Boolean, default=False, nullable=False)

    # Siap semantic search (belum diisi pipeline)
    embedding = Column(Vector(384), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<JobCase(id={self.id}, verdict={self.verdict}, risk_score={self.risk_score})>"


class AhuWhitelist(Base):
    __tablename__ = "ahu_whitelist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    company_name = Column(String(255), nullable=False, index=True)
    legal_type = Column(String(10), nullable=False)  # PT or CV
    synced_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self):
        return f"<AhuWhitelist(id={self.id}, company_name={self.company_name}, legal_type={self.legal_type})>"
