"""A stand-in for the LLM, for tests and for running without an API key.

It recognises the ten bundled samples by borrower name and answers from the
ground truth, finding a real quote in the PDF for each value, the way a
well-behaved model would. Any other document comes back empty.

It is a *perfect reader*: it shows the pipeline works end to end. It says
nothing about how well a real model reads. That's what evaluate.py with
LLM_PROVIDER=anthropic is for.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from app.llm.base import Extraction, FieldReading, Review, ReviewRisk, Usage
from app.pipeline.fields import FIELDS, FieldSpec
from app.pipeline.grounding import normalise
from app.pipeline.pdf_text import Page

GROUND_TRUTH = Path(__file__).resolve().parents[2] / "data" / "samples" / "ground_truth.json"

# Words that show an enum value in the text.
ENUM_CLUES: dict[str, tuple[str, ...]] = {
    "company": ("company", "pty ltd"), "trust": ("trust",), "smsf": ("superannuation fund",),
    "individual": ("individual",),
    "purchase": ("acquisition", "buying"), "refinance": ("refinance",),
    "construction": ("construction",), "equity_release": ("equity release",),
    "bridging": ("bridging",),
    "office": ("office",), "retail": ("retail",), "industrial": ("industrial", "warehouse"),
    "residential_dev": ("residential development",), "land": ("vacant land", "land"),
    "mixed_use": ("mixed use",),
}


def _variants(spec: FieldSpec, value: Any) -> list[str]:
    """Ways a value might be written in a document."""
    if spec.kind == "money":
        out = [f"${value:,.0f}"]
        millions = value / 1e6
        out += [f"${millions:g}m", f"{millions:g} mil"]
        return out
    if spec.kind == "percent":
        return [f"{value:.1f}%", f"{value:.0f}%"]
    if spec.kind == "integer":
        return [f"{value} months"]
    if spec.kind == "date":
        d = date.fromisoformat(value)
        return [f"{d.day} {d:%B %Y}"]
    if spec.kind == "enum":
        return list(ENUM_CLUES.get(value, (value,)))
    if spec.name == "abn":
        return [f"{value[:2]} {value[2:5]} {value[5:8]} {value[8:]}"]
    return [value]


def _find_quote(variants: list[str], pages: list[Page]) -> tuple[str, int] | None:
    """Quote the whole line when the value sits on one line; otherwise quote the
    value itself (it wraps across a line break in the PDF)."""
    for variant in variants:
        needle = normalise(variant)
        for page in pages:
            for line in page.text.splitlines():
                if needle in normalise(line):
                    return line.strip(), page.number
            if needle in normalise(page.text):
                return variant, page.number
    return None


class MockProvider:
    name = "mock"
    model = "mock"

    def __init__(self) -> None:
        self._samples = json.loads(GROUND_TRUTH.read_text())["samples"]

    def _match(self, pages: list[Page]) -> dict[str, Any] | None:
        text = normalise(" ".join(p.text for p in pages))
        return next((s for s in self._samples
                     if normalise(s["fields"]["borrower_name"]) in text), None)

    def extract(self, pages: list[Page]) -> Extraction:
        sample = self._match(pages)
        if sample is None:
            fields = {s.name: FieldReading(None, 0.0, None, None) for s in FIELDS}
            return Extraction(fields, "The mock provider only recognises the bundled sample "
                                      "applications. Set LLM_PROVIDER=anthropic to read this one.",
                              Usage(self.model))

        fields: dict[str, FieldReading] = {}
        for spec in FIELDS:
            value = sample["fields"][spec.name]
            if value is None:
                fields[spec.name] = FieldReading(None, 0.9, None, None)
                continue
            found = _find_quote(_variants(spec, value), pages)
            if found:
                fields[spec.name] = FieldReading(value, 0.95, found[0], found[1])
            else:
                fields[spec.name] = FieldReading(value, 0.6, None, None)

        f = sample["fields"]
        summary = (f"{f['borrower_name']} is seeking ${f['loan_amount']:,.0f} "
                   f"({f['loan_purpose'].replace('_', ' ')}) over {f['loan_term_months']} months, "
                   f"secured by {f['property_type'].replace('_', ' ')} property at "
                   f"{f['property_address']}.")
        return Extraction(fields, summary, Usage(self.model))

    def review(self, pages: list[Page], values: dict[str, Any], policy_text: str) -> Review:
        risks: list[ReviewRisk] = []
        exit_strategy = (values.get("exit_strategy") or "").lower()
        if values.get("borrower_type") == "smsf":
            risks.append(ReviewRisk("§2.4", "SMSF borrowing requirements",
                                    "Confirm the limited recourse borrowing arrangement, separate "
                                    "holding trust, independent advice and member guarantees.",
                                    "info"))
        if "rezoning" in exit_strategy or "approval" in exit_strategy:
            risks.append(ReviewRisk("§7.2", "Exit depends on a future event",
                                    "Repayment relies on a rezoning or approval that has not yet "
                                    "been granted."))
        if values.get("loan_purpose") == "construction":
            risks.append(ReviewRisk("§6.2", "Builder details not provided",
                                    "The application does not name the builder or confirm a "
                                    "fixed-price contract.", "info"))
        return Review(risks, Usage(self.model))
