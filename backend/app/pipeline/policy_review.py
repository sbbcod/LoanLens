"""Step 5: keep only the LLM's judgement risks that pass our checks.

The LLM may raise a risk only if it cites a real clause of the policy, and
only a clause that is a matter of judgement. Clauses marked [System check]
belong to the deterministic rules. LLM risks can never be critical.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from app.llm.base import ReviewRisk
from app.pipeline.rules import Flag

POLICY_PATH = Path(__file__).resolve().parents[2] / "data" / "credit_policy.md"
_CLAUSE = re.compile(r"^§(\d+\.\d+)\s+(\*\*\[System check\]\*\*)?", re.MULTILINE)


@lru_cache
def policy_text() -> str:
    return POLICY_PATH.read_text()


def clauses(text: str) -> dict[str, bool]:
    """{'§4.2': True, '§7.2': False, ...} — True means it's a system check."""
    return {f"§{m.group(1)}": bool(m.group(2)) for m in _CLAUSE.finditer(text)}


def _normalise_ref(ref: str) -> str:
    ref = ref.strip().rstrip(".")
    return ref if ref.startswith("§") else f"§{ref}"


def accept(risks: list[ReviewRisk], policy: str) -> tuple[list[Flag], list[ReviewRisk]]:
    """Returns (accepted flags, rejected risks). Rejected ones are kept for the audit log."""
    known = clauses(policy)
    accepted: list[Flag] = []
    rejected: list[ReviewRisk] = []
    for risk in risks:
        ref = _normalise_ref(risk.policy_ref)
        if ref not in known or known[ref]:
            rejected.append(risk)  # made-up clause, or one the rules already cover
            continue
        severity = "warning" if risk.severity == "warning" else "info"  # never critical
        accepted.append(Flag("POLICY_REVIEW", severity, f"{risk.title}. {risk.message}",
                             ref, source="llm"))
    return accepted, rejected
