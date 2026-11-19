"""Step 6: decide how much to trust the extraction and whether a human must look.

overall confidence = the LOWEST confidence among required fields, not the
average. One doubtful loan amount must not be hidden by eleven certain fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.pipeline.fields import REQUIRED_FIELDS

REVIEW_THRESHOLD = 0.75     # required field below this -> needs review
UNGROUNDED_CAP = 0.40       # confidence ceiling when the quote can't be found


@dataclass
class ScoredField:
    name: str
    value: Any
    confidence: float
    evidence: str | None
    page: int | None
    grounded: bool
    grounding_note: str | None = None
    verified_by_human: bool = False


def cap_if_ungrounded(confidence: float, grounded: bool) -> float:
    return confidence if grounded else min(confidence, UNGROUNDED_CAP)


def overall_confidence(fields: dict[str, ScoredField]) -> float:
    return min(fields[name].confidence for name in REQUIRED_FIELDS)


def needs_review(fields: dict[str, ScoredField], flag_severities: list[tuple[str, bool]]) -> bool:
    """flag_severities: (severity, acknowledged) for each open flag.

    A human-verified field no longer counts against the application.
    """
    for f in fields.values():
        if f.verified_by_human:
            continue
        if not f.grounded:
            return True
        if f.name in REQUIRED_FIELDS and f.confidence < REVIEW_THRESHOLD:
            return True
    return any(sev == "critical" and not ack for sev, ack in flag_severities)
