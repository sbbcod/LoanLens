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


def _label(value: str | None) -> str:
    return value.replace("_", " ").capitalize() if value else "Unknown"


def card_details(application: Application, summary: ApplicationSummary,
                 risks: list[RiskFlag]) -> str:
    """The approval card body as Markdown, built here so the flow only has to drop it in.

    Formatting money and listing risks in Power Automate expressions is fiddly and
    can't be unit tested; in Python it is one function with a test.
    """
    amount = f"${summary.loan_amount:,.0f}" if summary.loan_amount is not None else "Unknown"
    lvr = f"{summary.calculated_lvr:.1f}%" if summary.calculated_lvr is not None else "Unknown"
    approval = application.approvals[-1] if application.approvals else None
    lines = [
        f"**Loan:** {amount} · {_label(summary.loan_purpose)} · {_label(summary.property_type)}",
        f"**LVR:** {lvr}",
    ]
    if approval:
        who = approval.requested_by.replace("user:", "")
        lines.append(f"**Submitted by:** {who}" + (f" — {approval.comment}" if approval.comment else ""))
    if application.summary:
        lines.append(f"**Summary:** {application.summary}")

    shown = [r for r in risks if r.severity in ("critical", "warning")]
    if shown:
        items = []
        for r in shown:
            ref = f" (Policy {r.policy_ref})" if r.policy_ref else ""
            seen = f", acknowledged by {r.acknowledged_by.replace('user:', '')}" if r.acknowledged_by else ""
            items.append(f"- {r.severity.capitalize()}: {r.message}{ref}{seen}")
        lines.append("**Risks:**\n" + "\n".join(items))
    else:
        lines.append("**Risks:** none at warning level or above.")
    # Approvals render Markdown; a blank line keeps each item on its own line.
    return "\n\n".join(lines)


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
        "details": card_details(application, summary, risks),
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
