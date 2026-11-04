"""ORM models (tables): FactCheck, Analysis, Source, Feedback."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class FactCheck(Base):
    __tablename__ = "fact_checks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # = claim_id from the dataset
    claim_text: Mapped[str] = mapped_column(Text)
    claim_source: Mapped[Optional[str]] = mapped_column(String(20))
    title: Mapped[Optional[str]] = mapped_column(Text)
    verdict: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    verdict_raw: Mapped[Optional[str]] = mapped_column(String(200))
    verdict_rule: Mapped[Optional[str]] = mapped_column(String(40))
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    source_name: Mapped[str] = mapped_column(String(100), index=True)
    original_url: Mapped[str] = mapped_column(String(600), unique=True)
    category: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    category_source: Mapped[Optional[str]] = mapped_column(String(30))
    language: Mapped[Optional[str]] = mapped_column(String(12), index=True)
    publication_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    collection_date: Mapped[Optional[str]] = mapped_column(String(40))
    group_id: Mapped[Optional[int]] = mapped_column(Integer)

    __table_args__ = (Index("ix_fc_lang_verdict", "language", "verdict"),)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(40))  # "fact_checker" | "news_outlet"
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    available_fact_checks: Mapped[int] = mapped_column(Integer, default=0)
    evidence_summary: Mapped[Optional[dict]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    submitted_text: Mapped[Optional[str]] = mapped_column(Text)  # NULL unless the user opted in
    submitted_url: Mapped[Optional[str]] = mapped_column(String(600))
    text_preview: Mapped[Optional[str]] = mapped_column(String(160))  # NULL unless opted in
    stored_with_consent: Mapped[bool] = mapped_column(default=False)
    detected_language: Mapped[Optional[str]] = mapped_column(String(12))
    predicted_class: Mapped[Optional[str]] = mapped_column(String(32))
    confidence: Mapped[Optional[float]] = mapped_column(Float)
    risk_level: Mapped[Optional[str]] = mapped_column(String(40), index=True)
    risk_score: Mapped[Optional[float]] = mapped_column(Float)
    evidence_strength: Mapped[Optional[float]] = mapped_column(Float)
    top_match_id: Mapped[Optional[str]] = mapped_column(String(64))
    top_match_similarity: Mapped[Optional[float]] = mapped_column(Float)
    processing_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)

    feedback: Mapped[list["Feedback"]] = relationship(back_populates="analysis", cascade="all, delete-orphan")


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"), index=True)
    feedback_type: Mapped[str] = mapped_column(String(40))
    comments: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    analysis: Mapped[Analysis] = relationship(back_populates="feedback")
