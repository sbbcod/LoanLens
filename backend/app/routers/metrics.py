"""GET /api/metrics — how the tool is doing: volume, trust, cost."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.models import Application, ApplicationStatus, Approval, ExtractedField, LlmCall
from app.schemas import DailyCount, Metrics

router = APIRouter(prefix="/api", tags=["metrics"])


@router.get("/metrics", response_model=Metrics)
def metrics(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> Metrics:
    apps = db.scalars(select(Application)).all()
    by_status = Counter(a.status for a in apps)

    confidences = [a.overall_confidence for a in apps if a.overall_confidence is not None]

    # Human edit rate: of the fields the AI filled in, how many did a person change?
    filled = db.scalar(select(func.count()).select_from(ExtractedField)
                       .where(ExtractedField.ai_value.is_not(None))) or 0
    edited = db.scalar(select(func.count()).select_from(ExtractedField)
                       .where(ExtractedField.edited_by.is_not(None))) or 0

    # LLM cost and time per processed application.
    per_app = db.execute(select(LlmCall.application_id, func.sum(LlmCall.cost_usd),
                                func.sum(LlmCall.latency_ms)).group_by(LlmCall.application_id)).all()
    costs = [c for _, c, _ in per_app]
    latencies = [ms / 1000 for _, _, ms in per_app]

    week_ago = datetime.now(UTC) - timedelta(days=7)
    approved_recently = db.scalar(select(func.count()).select_from(Approval).where(
        Approval.decision == "approved", Approval.decided_at >= week_ago)) or 0

    # Applications received per day, last 14 days (zero-filled so the chart has no gaps).
    today = date.today()
    received = Counter(a.received_at.date() for a in apps)
    daily = [DailyCount(date=(d := today - timedelta(days=i)).isoformat(), count=received.get(d, 0))
             for i in range(13, -1, -1)]

    return Metrics(
        total=len(apps),
        by_status=dict(by_status),
        awaiting_review=sum(1 for a in apps if a.needs_review and a.status in
                            (ApplicationStatus.NEEDS_REVIEW, ApplicationStatus.EXTRACTED)),
        pending_approval=by_status.get(ApplicationStatus.PENDING_APPROVAL, 0),
        approved_last_7_days=approved_recently,
        average_confidence=round(sum(confidences) / len(confidences), 3) if confidences else None,
        human_edit_rate=round(edited / filled, 3) if filled else None,
        average_cost_usd=round(sum(costs) / len(costs), 4) if costs else None,
        average_latency_s=round(sum(latencies) / len(latencies), 1) if latencies else None,
        daily=daily,
        llm_provider=settings.llm_provider,
        llm_model=settings.llm_model if settings.llm_provider != "mock" else "mock",
    )
