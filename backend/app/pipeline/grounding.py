"""Step 3: check that every value the model gave is backed by the document.

The model must quote the text each value came from. Here we look for that
quote in the PDF text ourselves. A model's confidence score is its own opinion;
whether a quote is really in the document is a fact we can check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz

from app.pipeline.fields import FieldSpec
from app.pipeline.pdf_text import Page

MATCH_THRESHOLD = 90       # rapidfuzz partial_ratio, 0–100
MONEY_TOLERANCE = 0.005    # 0.5%


@dataclass(frozen=True)
class GroundingResult:
    grounded: bool
    page: int | None   # where the quote was actually found
    reason: str | None  # why it failed, for the reviewer


def normalise(text: str) -> str:
    """Make formatting differences irrelevant: case, spacing, quotes, dashes, $ and commas."""
    text = text.lower()
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"[‐-―]", "-", text)
    text = text.replace("$", "").replace(",", "")
    return re.sub(r"\s+", " ", text).strip()


_NUMBER = re.compile(r"(\d+(?:\.\d+)?)\s*(m\b|mil\b|million\b|k\b)?", re.IGNORECASE)
_MULTIPLIER = {"m": 1e6, "mil": 1e6, "million": 1e6, "k": 1e3}


def numbers_in(text: str) -> list[float]:
    """All numbers in a quote, with '$2.35m' -> 2350000 and '3.9 mil' -> 3900000."""
    found = []
    for digits, suffix in _NUMBER.findall(text.replace(",", "")):
        n = float(digits)
        if suffix:
            n *= _MULTIPLIER[suffix.lower()]
        found.append(n)
    return found


def value_matches_quote(spec: FieldSpec, value: Any, evidence: str) -> bool:
    """For numbers, the quote must contain the same number. Text fields pass."""
    if spec.kind == "money":
        return any(abs(n - value) <= value * MONEY_TOLERANCE for n in numbers_in(evidence))
    if spec.kind in ("percent", "integer"):
        return any(abs(n - float(value)) < 0.05 for n in numbers_in(evidence))
    return True


def check(spec: FieldSpec, value: Any, evidence: str | None, page: int | None,
          pages: list[Page]) -> GroundingResult:
    if value is None:
        return GroundingResult(True, None, None)  # nothing claimed, nothing to prove
    if not evidence or not evidence.strip():
        return GroundingResult(False, None, "No supporting quote was given.")

    quote = normalise(evidence)
    # Look on the page the model named first, then anywhere (it may get the page wrong).
    ordered = sorted(pages, key=lambda p: p.number != page)
    found_on = next(
        (p.number for p in ordered if fuzz.partial_ratio(quote, normalise(p.text)) >= MATCH_THRESHOLD),
        None,
    )
    if found_on is None:
        return GroundingResult(False, None, "The supporting quote does not appear in the document.")
    if not value_matches_quote(spec, value, evidence):
        return GroundingResult(False, found_on, "The quote does not contain the extracted value.")
    return GroundingResult(True, found_on, None)
