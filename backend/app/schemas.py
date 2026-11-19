"""Shapes of what the API accepts and returns.

Kept separate from the database models so the API can change shape (or hide
columns) without touching the tables.
"""

from __future__ import annotations

from datetime import UTC
from datetime import datetime as _datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, Field

# All times are stored in UTC, but SQLite forgets the time zone on the way back.
# Re-attach it so clients always receive e.g. "2026-11-19T00:06:45Z", never an ambiguous time.
datetime = Annotated[_datetime, AfterValidator(lambda d: d if d.tzinfo else d.replace(tzinfo=UTC))]


class FieldOut(BaseModel):
    name: str
    label: str
    kind: str
    required: bool
    value: Any                  # current value (human-corrected if edited)
    ai_value: Any               # what the model read; never changes
    confidence: float
    evidence: str | None
    page: int | None
    grounded: bool
    edited: bool
    edited_by: str | None
    edited_at: datetime | None


class RiskOut(BaseModel):
    id: int
    source: str
    code: str
    severity: str
    message: str
    policy_ref: str | None
    acknowledged: bool
    acknowledged_by: str | None


class ApprovalOut(BaseModel):
    id: int
    requested_by: str
    requested_at: datetime
    approver: str | None
    decision: str | None
    comment: str | None
    decided_at: datetime | None


class AuditOut(BaseModel):
    id: int
    actor: str
    action: str
    detail: dict[str, Any] | None
    created_at: datetime


class RiskCounts(BaseModel):
    critical: int = 0
    warning: int = 0
    info: int = 0


class ApplicationSummary(BaseModel):
    id: str
    reference: str
    status: str
    source: str
    borrower_name: str | None
    loan_amount: float | None
    loan_purpose: str | None
    property_type: str | None
    calculated_lvr: float | None
    overall_confidence: float | None
    needs_review: bool
    open_risks: RiskCounts
    received_at: datetime


class ApplicationDetail(ApplicationSummary):
    sender_email: str | None
    subject: str | None
    summary: str | None
    error_message: str | None
    lvr_limit: float | None
    ai_cost_usd: float
    fields: list[FieldOut]
    risks: list[RiskOut]
    approvals: list[ApprovalOut]
    audit: list[AuditOut]


class IngestResponse(BaseModel):
    id: str
    reference: str
    status: str


class FieldEdits(BaseModel):
    changes: dict[str, Any] = Field(description="field name -> corrected value (null to clear)")


class AcknowledgeRequest(BaseModel):
    risk_id: int
    acknowledged: bool = True


class SubmitRequest(BaseModel):
    comment: str | None = None


class ApprovalCallback(BaseModel):
    application_id: str
    decision: Literal["approved", "declined"]
    approver: str
    comment: str | None = None
    flow_run_id: str | None = None


class DailyCount(BaseModel):
    date: str
    count: int


class Metrics(BaseModel):
    total: int
    by_status: dict[str, int]
    awaiting_review: int
    pending_approval: int
    approved_last_7_days: int
    average_confidence: float | None
    human_edit_rate: float | None       # share of AI values a person changed
    average_cost_usd: float | None      # LLM cost per processed application
    average_latency_s: float | None
    daily: list[DailyCount]
    llm_provider: str
    llm_model: str
