"""The whole AI pipeline for one document, with no database involved.

    read PDF -> LLM extraction -> grounding -> rules -> LLM policy review -> scoring

Kept free of the database so the evaluation script can run exactly the same
code the live system runs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from app.config import Settings
from app.llm import cache
from app.llm.base import Extraction, LLMProvider, Review, ReviewRisk, Usage
from app.pipeline import grounding, policy_review, rules, scoring
from app.pipeline.fields import FIELDS, FieldSpec
from app.pipeline.pdf_text import Page, read_pages
from app.pipeline.rules import Flag
from app.pipeline.scoring import ScoredField


@dataclass
class LlmCallRecord:
    purpose: str
    usage: Usage
    cached: bool


@dataclass
class Analysis:
    text_hash: str
    fields: dict[str, ScoredField]
    summary: str
    calculated_lvr: float | None
    flags: list[Flag]
    overall_confidence: float
    needs_review: bool
    calls: list[LlmCallRecord] = field(default_factory=list)
    rejected_risks: list[ReviewRisk] = field(default_factory=list)


def clean_value(spec: FieldSpec, value: Any) -> Any:
    """Coerce the model's value into the type the rules expect. Bad values become None."""
    if value is None or value == "":
        return None
    try:
        if spec.kind == "money" or spec.kind == "percent":
            return float(str(value).replace(",", "").replace("$", "").replace("%", "").strip())
        if spec.kind == "integer":
            return int(float(str(value).replace(",", "").strip()))
        if spec.kind == "date":
            return date.fromisoformat(str(value)).isoformat()
        if spec.kind == "enum":
            return value if value in spec.options else None
        if spec.name == "abn":
            return str(value).replace(" ", "")
        return str(value).strip()
    except (TypeError, ValueError):
        return None


def flag_values(fields: dict[str, ScoredField]) -> dict[str, Any]:
    return {name: f.value for name, f in fields.items()}


def ungrounded_flags(fields: dict[str, ScoredField]) -> list[Flag]:
    return [
        Flag("UNGROUNDED_FIELD", "warning",
             f"{f.name.replace('_', ' ').capitalize()}: {f.grounding_note} Check it against the document.",
             None, source="system")
        for f in fields.values() if not f.grounded and not f.verified_by_human
    ]


def _extract(provider: LLMProvider, settings: Settings, pages: list[Page],
             text_hash: str) -> tuple[Extraction, bool]:
    k = cache.key("extract", provider.name, provider.model, settings.llm_effort, text_hash)
    if provider.name != "mock" and (hit := cache.load(settings.llm_cache_dir, k)):
        return cache.extraction_from(hit), True
    result = provider.extract(pages)
    if provider.name != "mock":
        cache.save(settings.llm_cache_dir, k, result)
    return result, False


def _review(provider: LLMProvider, settings: Settings, pages: list[Page], values: dict[str, Any],
            policy: str, text_hash: str) -> tuple[Review, bool]:
    inputs = json.dumps(values, sort_keys=True, default=str) + policy
    k = cache.key("review", provider.name, provider.model, settings.llm_effort, text_hash,
                  hashlib.sha256(inputs.encode()).hexdigest())
    if provider.name != "mock" and (hit := cache.load(settings.llm_cache_dir, k)):
        return cache.review_from(hit), True
    result = provider.review(pages, values, policy)
    if provider.name != "mock":
        cache.save(settings.llm_cache_dir, k, result)
    return result, False


def analyse(pdf: Path | bytes, provider: LLMProvider, settings: Settings) -> Analysis:
    # 1. Read the PDF (raises NoTextError for scans)
    pages = read_pages(pdf)
    text_hash = hashlib.sha256("\n".join(p.text for p in pages).encode()).hexdigest()

    # 2. LLM extraction
    extraction, cached = _extract(provider, settings, pages, text_hash)
    calls = [LlmCallRecord("extract", extraction.usage, cached)]

    # 3. Grounding: is each value backed by a quote that is really in the document?
    fields: dict[str, ScoredField] = {}
    for spec in FIELDS:
        reading = extraction.fields[spec.name]
        value = clean_value(spec, reading.value)
        g = grounding.check(spec, value, reading.evidence, reading.page, pages)
        fields[spec.name] = ScoredField(
            name=spec.name, value=value,
            confidence=scoring.cap_if_ungrounded(reading.confidence, g.grounded),
            evidence=reading.evidence if value is not None else None,
            page=g.page or reading.page if value is not None else None,
            grounded=g.grounded, grounding_note=g.reason,
        )

    # 4. Deterministic policy rules
    values = flag_values(fields)
    rule_result = rules.evaluate(values, settings.assessment_date)

    # 5. LLM judgement review, filtered by our own checks
    policy = policy_review.policy_text()
    review, cached = _review(provider, settings, pages, values, policy, text_hash)
    if review.usage:
        calls.append(LlmCallRecord("policy_review", review.usage, cached))
    llm_flags, rejected = policy_review.accept(review.risks, policy)

    # 6. Scoring
    flags = rule_result.flags + ungrounded_flags(fields) + llm_flags
    return Analysis(
        text_hash=text_hash,
        fields=fields,
        summary=extraction.summary,
        calculated_lvr=rule_result.calculated_lvr,
        flags=flags,
        overall_confidence=round(scoring.overall_confidence(fields), 2),
        needs_review=scoring.needs_review(fields, [(f.severity, False) for f in flags]),
        calls=calls,
        rejected_risks=rejected,
    )
