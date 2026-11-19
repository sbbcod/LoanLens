"""Calling the Power Automate approval flow.

The flow starts a Teams approval, waits for the credit manager, then calls
our /api/approvals/callback with the decision. When no flow URL is set, the
request is simulated: the application waits for the callback, which can be
called by hand (or from the docs page) to play the manager's part.
"""

from __future__ import annotations

import httpx

from app.config import Settings
from app.models import Application, RiskFlag
from app.schemas import ApplicationSummary


class FlowError(Exception):
    pass


def payload(settings: Settings, application: Application, summary: ApplicationSummary,
            risks: list[RiskFlag]) -> dict:
    """What the Teams approval card shows. Plain values, ready to drop into the card."""
    return {
        "application_id": application.id,
        "reference": application.reference,
        "borrower": summary.borrower_name,
        "amount": summary.loan_amount,
        "lvr": summary.calculated_lvr,
        "summary": application.summary,
        "risks": [
            {"severity": r.severity, "message": r.message, "policy_ref": r.policy_ref}
            for r in risks if r.severity in ("critical", "warning")
        ],
        "review_url": f"{settings.frontend_url.rstrip('/')}/applications/{application.id}",
    }


def request_approval(settings: Settings, application: Application, summary: ApplicationSummary,
                     risks: list[RiskFlag]) -> bool:
    """Returns True if the real flow was called, False if simulated."""
    if not settings.approval_flow_url:
        return False
    try:
        response = httpx.post(settings.approval_flow_url,
                              json=payload(settings, application, summary, risks), timeout=15)
        response.raise_for_status()
    except httpx.HTTPError as e:
        raise FlowError(f"Could not start the approval flow: {e}") from e
    return True
