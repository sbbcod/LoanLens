"""One application's status as a plain sentence, for the Copilot Studio agent.

The agent reads this answer out as it is. Building the wording here keeps it
deterministic and tested; the agent never has to work out a status itself.
"""

from __future__ import annotations

from app.models import Application
from app.schemas import ApplicationSummary

_STATUS = {
    "received": "has just arrived and is being read",
    "needs_review": "is waiting for an analyst to review it",
    "extracted": "has been read and is ready for an analyst to check",
    "reviewed": "has been reviewed by an analyst",
    "pending_approval": "is with the credit manager for approval",
    "approved": "has been approved",
    "declined": "has been declined",
    "error": "could not be processed and needs someone to look at it",
}


def _money(amount: float | None) -> str | None:
    if amount is None:
        return None
    return f"${amount / 1e6:.2f}m".replace(".00m", "m") if amount >= 1e6 else f"${amount:,.0f}"


def status_sentence(application: Application, summary: ApplicationSummary, review_url: str) -> str:
    what = ", ".join(p for p in (
        summary.borrower_name,
        " ".join(p for p in (_money(summary.loan_amount),
                             (summary.property_type or "").replace("_", " "),
                             (summary.loan_purpose or "").replace("_", " ")) if p),
    ) if p)
    parts = [f"{summary.reference}{f' ({what})' if what else ''} "
             f"{_STATUS.get(summary.status, summary.status.replace('_', ' '))}."]

    decided = next((a for a in reversed(application.approvals) if a.decision), None)
    if decided and summary.status in ("approved", "declined"):
        when = decided.decided_at.strftime("%-d %b %Y") if decided.decided_at else ""
        parts.append(f"Decided by {decided.approver}{f' on {when}' if when else ''}"
                     + (f": \"{decided.comment}\"." if decided.comment else "."))

    risks = summary.open_risks
    counts = [f"{n} {label}" for n, label in ((risks.critical, "critical"), (risks.warning, "warning"))
              if n]
    parts.append(f"Open risks: {', '.join(counts)}." if counts else "No open risks at warning level or above.")
    if summary.calculated_lvr is not None:
        parts.append(f"LVR {summary.calculated_lvr:.1f}%.")
    parts.append(f"Details: {review_url}")
    return " ".join(parts)
