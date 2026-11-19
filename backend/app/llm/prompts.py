"""Prompts and output schemas for the two LLM calls.

The schemas are enforced by the API (structured output), so the reply is
always valid JSON in exactly this shape. What the JSON *says* is still
checked afterwards — by grounding and by the rules.
"""

from __future__ import annotations

from typing import Any

from app.pipeline.fields import FIELDS, FieldSpec

EXTRACT_SYSTEM = """\
You are a credit assistant at a commercial property lender. You read loan \
applications sent by brokers and copy specific details out of them.

Rules:
- Only report what the document says. If a detail is not in the document, \
return null for its value. Do not guess, infer from context, or calculate.
- For every non-null value, give evidence: a short quote (at most 30 words) \
copied word for word from the document, and the page number it is on. The \
quote must contain the value itself. Evidence is checked automatically \
against the document; a quote that is not found word for word is treated as \
unsupported.
- Confidence, from 0 to 1:
  - 0.9 or above: the value is written plainly and only once, or every \
mention agrees.
  - 0.6 to 0.8: the value needed interpretation (an informal amount, a \
category you had to choose).
  - 0.5 or below: the document gives conflicting values. Report the one \
from the most formal part of the document (a table over prose) and explain \
nothing; the low score is the signal.
  - For a null value, confidence is how sure you are the detail is absent.
- Amounts are plain AUD numbers: "$4.2m" is 4200000. Dates are YYYY-MM-DD.
- Copy identifiers such as ABNs exactly as written, even if they look wrong.

Also write a summary: two or three plain sentences a credit manager could \
read in ten seconds, covering who is borrowing, how much, for what, and \
against which property. Do not give an opinion on whether to lend."""

REVIEW_SYSTEM = """\
You assist credit officers at a commercial property lender. You will be \
given the lender's credit policy, a loan application, and the details \
already extracted from it.

Point out risks that call for credit judgement under the policy: for \
example an exit that depends on an event that has not happened, a borrower \
type with special requirements, missing information the policy expects. \
Use only the policy you are given.

Do not assess anything the policy marks [System check] — loan size, term, \
LVR, valuation age, presales, ABN, required fields. Those are checked by \
separate deterministic rules, and repeating them adds noise.

Each risk must cite the single policy clause it relies on, as it appears \
in the policy (for example "§7.2"). If no clause supports a concern, leave \
it out. Return an empty list when there is nothing to raise. Prefer two \
precise risks to five vague ones. Never recommend approving or declining."""


def _value_schema(spec: FieldSpec) -> dict[str, Any]:
    if spec.kind == "enum":
        return {"anyOf": [{"type": "string", "enum": list(spec.options)}, {"type": "null"}]}
    json_type = {
        "text": "string", "date": "string", "money": "number",
        "percent": "number", "integer": "integer",
    }[spec.kind]
    return {"anyOf": [{"type": json_type}, {"type": "null"}]}


def extraction_schema() -> dict[str, Any]:
    field_props = {
        spec.name: {
            "type": "object",
            "description": spec.description,
            "properties": {
                "value": _value_schema(spec),
                "confidence": {"type": "number"},
                "evidence": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                "page": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
            },
            "required": ["value", "confidence", "evidence", "page"],
            "additionalProperties": False,
        }
        for spec in FIELDS
    }
    return {
        "type": "object",
        "properties": {
            "fields": {
                "type": "object",
                "properties": field_props,
                "required": [s.name for s in FIELDS],
                "additionalProperties": False,
            },
            "summary": {"type": "string"},
        },
        "required": ["fields", "summary"],
        "additionalProperties": False,
    }


REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "risks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "policy_ref": {"type": "string"},
                    "title": {"type": "string"},
                    "message": {"type": "string"},
                    "severity": {"type": "string", "enum": ["info", "warning"]},
                },
                "required": ["policy_ref", "title", "message", "severity"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["risks"],
    "additionalProperties": False,
}
