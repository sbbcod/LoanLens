"""Claude, via the official Anthropic SDK."""

from __future__ import annotations

import json
import time
from typing import Any

import anthropic

from app.llm.base import Extraction, FieldReading, Review, ReviewRisk, Usage, cost_usd
from app.llm.prompts import (
    EXTRACT_SYSTEM, REVIEW_SCHEMA, REVIEW_SYSTEM, extraction_schema, field_guide,
)
from app.pipeline.fields import FIELDS
from app.pipeline.pdf_text import Page, as_prompt_text

# If Claude's safety filter declines a request, the API re-runs it on a
# fallback model inside the same call instead of failing.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(Exception):
    """The model call failed or returned something unusable."""


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str, effort: str, api_key: str | None = None) -> None:
        self.model = model
        self.effort = effort
        # With api_key=None the SDK reads ANTHROPIC_API_KEY from the environment.
        self.client = anthropic.Anthropic(api_key=api_key, max_retries=3)

    def _call(self, system: str, user: str, schema: dict[str, Any]) -> tuple[dict[str, Any], Usage]:
        started = time.monotonic()
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                betas=[FALLBACK_BETA],
                fallbacks="default",
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={
                    "effort": self.effort,
                    "format": {"type": "json_schema", "schema": schema},
                },
            )
        except anthropic.APIError as e:
            raise LLMError(f"Model call failed: {e}") from e

        if response.stop_reason == "refusal":
            raise LLMError("The model declined to process this document.")
        if response.stop_reason == "max_tokens":
            raise LLMError("The model's answer was cut off.")

        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise LLMError("The model returned no answer.")

        served_by = response.model  # may be the fallback model
        usage = Usage(
            model=served_by,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=int((time.monotonic() - started) * 1000),
            cost_usd=cost_usd(served_by, response.usage.input_tokens, response.usage.output_tokens),
        )
        return json.loads(text), usage

    def extract(self, pages: list[Page]) -> Extraction:
        data, usage = self._call(
            EXTRACT_SYSTEM,
            f"Fields to extract:\n{field_guide()}\n\n"
            f"Loan application document:\n\n{as_prompt_text(pages)}",
            extraction_schema(),
        )
        readings = {}
        for item in data["fields"]:
            readings.setdefault(item["name"], item)  # first answer wins if repeated

        fields = {}
        for spec in FIELDS:
            raw = readings.get(spec.name)
            if raw is None:
                # The model skipped this field. Treat it as not found, with zero
                # confidence, so a required field forces human review.
                fields[spec.name] = FieldReading(None, 0.0, None, None)
                continue
            found = raw["found"] and raw["value"].strip() != ""
            fields[spec.name] = FieldReading(
                value=raw["value"] if found else None,   # converted by analyse.clean_value
                confidence=min(max(float(raw["confidence"]), 0.0), 1.0),
                evidence=raw["evidence"] or None,
                page=raw["page"] or None,
            )
        return Extraction(fields=fields, summary=data["summary"], usage=usage)

    def review(self, pages: list[Page], values: dict[str, Any], policy_text: str) -> Review:
        user = (
            f"<credit_policy>\n{policy_text}\n</credit_policy>\n\n"
            f"<application>\n{as_prompt_text(pages)}\n</application>\n\n"
            f"<extracted_details>\n{json.dumps(values, indent=2, default=str)}\n</extracted_details>"
        )
        data, usage = self._call(REVIEW_SYSTEM, user, REVIEW_SCHEMA)
        return Review(risks=[ReviewRisk(**r) for r in data["risks"]], usage=usage)
