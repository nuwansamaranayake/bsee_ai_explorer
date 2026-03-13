"""Phase 4 ORM models: regulatory tracking, ETL audit log.

Tables:
- alert_summaries: AI-digested BSEE Safety Alerts
- federal_register_digests: Federal Register rule change digests
- etl_refresh_log: Audit trail for all scheduled/manual ETL jobs
"""

from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, Index
)
from models.database import Base


class AlertSummary(Base):
    """AI-digested BSEE Safety Alert summaries."""
    __tablename__ = "alert_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_number = Column(String(20), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    published_date = Column(String(30), index=True)  # ISO 8601
    source_url = Column(String(1000))
    pdf_url = Column(String(1000))
    raw_text = Column(Text)  # Full extracted text from PDF
    ai_summary = Column(Text)  # Claude-generated plain-language digest
    ai_impact = Column(Text)  # Claude-generated operator impact analysis
    ai_action_items = Column(Text)  # JSON array of recommended actions
    status = Column(String(20), default="new", index=True)  # new, reviewed, dismissed
    created_at = Column(String(30))  # ISO 8601
    updated_at = Column(String(30))  # ISO 8601

    __table_args__ = (
        Index("ix_alert_status_date", "status", "published_date"),
    )


class FederalRegisterDigest(Base):
    """Federal Register rule change digests (future use)."""
    __tablename__ = "federal_register_digests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_number = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    published_date = Column(String(30), index=True)
    agency = Column(String(200))
    action_type = Column(String(100))  # Final Rule, Proposed Rule, Notice
    source_url = Column(String(1000))
    ai_summary = Column(Text)
    relevance_score = Column(Float)  # 0.0-1.0 relevance to GoM operations
    created_at = Column(String(30))


class ETLRefreshLog(Base):
    """Audit trail for all scheduled and manual ETL job executions."""
    __tablename__ = "etl_refresh_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_name = Column(String(100), nullable=False, index=True)
    started_at = Column(String(30), nullable=False)
    finished_at = Column(String(30))
    status = Column(String(20), nullable=False, index=True)  # running, success, failed
    records_processed = Column(Integer, default=0)
    error_message = Column(Text)

    __table_args__ = (
        Index("ix_etl_job_status", "job_name", "status"),
    )
