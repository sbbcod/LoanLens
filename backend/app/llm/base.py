"""What every LLM provider must do, so the pipeline doesn't care which one runs.

Switching from Claude to another model (or to the mock) is a config change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.pipeline.pdf_text import Page

# USD per million tokens (input, output). Used to record cost per call.
PRICES: dict[str, tuple[float, float]] = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    price_in, price_out = PRICES.get(model, (0.0, 0.0))
    return (input_tokens * price_in + output_tokens * price_out) / 1_000_000


@dataclass
class Usage:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0


@dataclass
class FieldReading:
    """One field as the model read it."""

    value: Any
    confidence: float
    evidence: str | None
    page: int | None


@dataclass
class Extraction:
    fields: dict[str, FieldReading]
    summary: str
    usage: Usage


@dataclass
class ReviewRisk:
    """A judgement risk the model raised. It must cite a policy clause."""

    policy_ref: str
    title: str
    message: str
    severity: str = "warning"


@dataclass
class Review:
    risks: list[ReviewRisk] = field(default_factory=list)
    usage: Usage | None = None


class LLMProvider(Protocol):
    name: str
    model: str

    def extract(self, pages: list[Page]) -> Extraction:
        """Read the fixed field list out of the document."""
        ...

    def review(self, pages: list[Page], values: dict[str, Any], policy_text: str) -> Review:
        """Point out judgement risks against the credit policy."""
        ...
