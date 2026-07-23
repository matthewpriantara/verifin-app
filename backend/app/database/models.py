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


class CommunityReport(Base):
    """
    Laporan komunitas — pengguna melaporkan lowongan yang terbukti menipu.

    Mendukung Fraud Network (Layer 5): entitas yang berulang kali dilaporkan
    menjadi sinyal risiko kuat lintas kasus, melengkapi case-memory JobCase.
    Satu entitas (HP/email/PT/URL) bisa dilaporkan banyak pengguna → agregasi
    menunjukkan seberapa luas jaringan penipuan.
    """

    __tablename__ = "community_reports"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Entitas yang dilaporkan — salah satu biasanya terisi
    company_name = Column(String(255), nullable=True, index=True)
    phone = Column(String(32), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    url = Column(String(512), nullable=True, index=True)

    report_type = Column(String(24), nullable=False, default="penipuan")  # penipuan | biaya_ilegal | tppo | lainnya
    description = Column(Text, nullable=True)
    reporter_contact = Column(String(255), nullable=True)  # opsional, untuk follow-up

    # Agregasi sederhana: berapa kali entitas serupa dilaporkan
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        target = self.company_name or self.phone or self.email or self.url
        return f"<CommunityReport(id={self.id}, type={self.report_type}, target={target})>"
