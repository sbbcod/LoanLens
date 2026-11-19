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

Return one entry in "fields" for each of the fields listed in the user message, \
exactly once each.

Rules:
- Only report what the document says. If a detail is not in the document, \
set found to false, value and evidence to "", and page to 0. Do not guess, \
infer from context, or calculate.
- For every value found, give evidence: a short quote (at most 30 words) \
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
  - For a detail not found, confidence is how sure you are it is absent.
- Write values in the format each field asks for: "$4.2m" is 4200000.
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

Only raise something this particular application gives a reason for. Do \
not list routine checks that apply to every application (for example \
confirming the valuer is on the panel, or that standard documents will be \
provided) unless the document itself suggests a problem. A credit officer \
already knows the routine; what they need from you is what is unusual here.

Each risk must cite the single policy clause it relies on, as it appears \
in the policy (for example "§7.2"). If no clause supports a concern, leave \
it out. Return an empty list when there is nothing to raise. Prefer two \
precise risks to five vague ones. Never recommend approving or declining."""


_FORMAT = {
    "text": "Text as written.",
    "money": "Digits only, in AUD (4200000).",
    "percent": "A number (55.0 for 55%).",
    "integer": "Whole number of months (24).",
    "date": "YYYY-MM-DD.",
}


def _field_description(spec: FieldSpec) -> str:
    fmt = (f"One of: {', '.join(spec.options)}." if spec.kind == "enum" else _FORMAT[spec.kind])
    return f"{spec.description} Value format: {fmt}"


def field_guide() -> str:
    """The field list, with what each means and how to write it, for the prompt."""
    return "\n".join(f"- {spec.name}: {_field_description(spec)}" for spec in FIELDS)


def extraction_schema() -> dict[str, Any]:
    # Kept deliberately small. The API compiles the schema into a grammar and limits
    # its size, so instead of one object per field (16 x 5 properties) the answer is
    # a list of identical "readings", each naming its field. Values are plain strings,
    # converted and checked by our own code (analyse.clean_value); nothing is nullable.
    # The anthropic provider checks every field came back exactly once.
    return {
        "type": "object",
        "properties": {
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "enum": [s.name for s in FIELDS]},
                        "found": {"type": "boolean"},
                        "value": {"type": "string"},
                        "confidence": {"type": "number"},
                        "evidence": {"type": "string"},
                        "page": {"type": "integer"},
                    },
                    "required": ["name", "found", "value", "confidence", "evidence", "page"],
                    "additionalProperties": False,
                },
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
