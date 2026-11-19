"""Database tables.

applications       one row per loan application
extracted_fields   one row per field the AI read, with the human's final value
risk_flags         policy breaches (from rules) and judgement risks (from the LLM)
approvals          approval requests and the credit manager's decision
audit_log          every action, by whom: system, ai, a user, or a flow
llm_calls          tokens, time and cost of each model call
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def new_id() -> str:
    return str(uuid.uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class ApplicationStatus:
    """Where an application is in its life. Stored as plain strings."""

    RECEIVED = "received"                  # PDF arrived, not processed yet
    NEEDS_REVIEW = "needs_review"          # processed; something needs a human look
    EXTRACTED = "extracted"                # processed; nothing flagged for review
    REVIEWED = "reviewed"                  # an analyst has checked it
    PENDING_APPROVAL = "pending_approval"  # sent to the credit manager
    APPROVED = "approved"
    DECLINED = "declined"
    ERROR = "error"                        # processing failed (e.g. scanned PDF)


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    reference: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # APP-2026-0001
    status: Mapped[str] = mapped_column(String(20), default=ApplicationStatus.RECEIVED, index=True)
    source: Mapped[str] = mapped_column(String(10))  # "email" or "upload"
    sender_email: Mapped[str | None] = mapped_column(String(255))
    subject: Mapped[str | None] = mapped_column(String(500))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    pdf_path: Mapped[str] = mapped_column(String(500))
    raw_text_hash: Mapped[str | None] = mapped_column(String(64))  # used to cache LLM results
    summary: Mapped[str | None] = mapped_column(Text)               # short AI summary for reviewers
    calculated_lvr: Mapped[float | None] = mapped_column(Float)     # loan / value, by code
    overall_confidence: Mapped[float | None] = mapped_column(Float) # lowest required-field confidence
    needs_review: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)

    fields: Mapped[list[ExtractedField]] = relationship(
        back_populates="application", cascade="all, delete-orphan")
    risks: Mapped[list[RiskFlag]] = relationship(
        back_populates="application", cascade="all, delete-orphan")
    approvals: Mapped[list[Approval]] = relationship(
        back_populates="application", cascade="all, delete-orphan")


class ExtractedField(Base):
    """One field read from the document.

    ai_value is what the model said and never changes. final_value starts
    equal to it and is what a human corrects, so both are always on record.
    """

    __tablename__ = "extracted_fields"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    field_name: Mapped[str] = mapped_column(String(50))

    ai_value: Mapped[Any] = mapped_column(JSON, nullable=True)
    ai_confidence: Mapped[float] = mapped_column(Float)
    evidence: Mapped[str | None] = mapped_column(Text)  # quote from the document
    page: Mapped[int | None] = mapped_column(Integer)
    grounded: Mapped[bool] = mapped_column(Boolean, default=False)  # quote found in the text?

    final_value: Mapped[Any] = mapped_column(JSON, nullable=True)
    edited_by: Mapped[str | None] = mapped_column(String(100))
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    application: Mapped[Application] = relationship(back_populates="fields")


class RiskFlag(Base):
    __tablename__ = "risk_flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    source: Mapped[str] = mapped_column(String(10))    # "rule" or "llm"
    code: Mapped[str] = mapped_column(String(50))      # e.g. LVR_OVER_LIMIT
    severity: Mapped[str] = mapped_column(String(10))  # info | warning | critical
    message: Mapped[str] = mapped_column(Text)
    policy_ref: Mapped[str | None] = mapped_column(String(20))  # e.g. "§4.2"
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_by: Mapped[str | None] = mapped_column(String(100))

    application: Mapped[Application] = relationship(back_populates="risks")


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str] = mapped_column(ForeignKey("applications.id"), index=True)
    requested_by: Mapped[str] = mapped_column(String(100))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    approver: Mapped[str | None] = mapped_column(String(100))
    decision: Mapped[str | None] = mapped_column(String(10))  # approved | declined
    comment: Mapped[str | None] = mapped_column(Text)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    flow_run_id: Mapped[str | None] = mapped_column(String(100))  # Power Automate run, for tracing

    application: Mapped[Application] = relationship(back_populates="approvals")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str | None] = mapped_column(ForeignKey("applications.id"), index=True)
    actor: Mapped[str] = mapped_column(String(100))  # system | ai | user:<name> | flow
    action: Mapped[str] = mapped_column(String(50))  # e.g. field_edited
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LlmCall(Base):
    __tablename__ = "llm_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[str | None] = mapped_column(ForeignKey("applications.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(20))  # extract | policy_review
    model: Mapped[str] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
