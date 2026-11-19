"""Turn database rows into API responses."""

from __future__ import annotations

from typing import Any

from app.models import Application, AuditLog
from app.pipeline.fields import FIELDS_BY_NAME
from app.pipeline.rules import lvr_limit
from app.schemas import (
    ApplicationDetail, ApplicationSummary, ApprovalOut, AuditOut, FieldOut, RiskCounts, RiskOut,
)


def _value(application: Application, name: str) -> Any:
    return next((f.final_value for f in application.fields if f.field_name == name), None)


def open_risks(application: Application) -> RiskCounts:
    counts = RiskCounts()
    for r in application.risks:
        if not r.acknowledged:
            setattr(counts, r.severity, getattr(counts, r.severity) + 1)
    return counts


def summary(application: Application) -> ApplicationSummary:
    return ApplicationSummary(
        id=application.id, reference=application.reference, status=application.status,
        source=application.source,
        borrower_name=_value(application, "borrower_name"),
        loan_amount=_value(application, "loan_amount"),
        loan_purpose=_value(application, "loan_purpose"),
        property_type=_value(application, "property_type"),
        calculated_lvr=application.calculated_lvr,
        overall_confidence=application.overall_confidence,
        needs_review=application.needs_review,
        open_risks=open_risks(application),
        received_at=application.received_at,
    )


_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def detail(application: Application, audit: list[AuditLog], ai_cost: float) -> ApplicationDetail:
    fields = []
    for f in application.fields:
        spec = FIELDS_BY_NAME[f.field_name]
        fields.append(FieldOut(
            name=f.field_name, label=spec.label, kind=spec.kind, required=spec.required,
            value=f.final_value, ai_value=f.ai_value, confidence=f.ai_confidence,
            evidence=f.evidence, page=f.page, grounded=f.grounded,
            edited=f.edited_by is not None, edited_by=f.edited_by, edited_at=f.edited_at,
        ))
    risks = sorted(application.risks, key=lambda r: (r.acknowledged, _SEVERITY_ORDER[r.severity]))
    limit = None
    if application.fields:
        limit = lvr_limit(_value(application, "property_type"), _value(application, "loan_purpose"))[0]
    return ApplicationDetail(
        **summary(application).model_dump(),
        sender_email=application.sender_email, subject=application.subject,
        summary=application.summary, error_message=application.error_message,
        lvr_limit=limit,
        ai_cost_usd=round(ai_cost, 4),
        fields=fields,
        risks=[RiskOut.model_validate(r, from_attributes=True) for r in risks],
        approvals=[ApprovalOut.model_validate(a, from_attributes=True) for a in application.approvals],
        audit=[AuditOut.model_validate(a, from_attributes=True) for a in audit],
    )
