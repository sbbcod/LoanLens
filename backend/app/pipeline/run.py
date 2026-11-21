"""Run the pipeline for a stored application and save everything it found.

Two entry points:
  process()      first run (or a re-run) of the full AI pipeline
  recheck()      after a human edits fields: re-run only the rules, no LLM
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.config import Settings
from app.llm import get_provider
from app.llm.anthropic_provider import LLMError
from app.models import (
    Application, ApplicationStatus, AuditLog, ExtractedField, LlmCall, RiskFlag,
)
from app.pipeline import rules, scoring
from app.pipeline.analyse import analyse, ungrounded_flags
from app.pipeline.pdf_text import NoTextError
from app.pipeline.redact import redact
from app.pipeline.rules import Flag
from app.pipeline.scoring import ScoredField

log = logging.getLogger("loanlens.pipeline")


def _fail(db: Session, application: Application, message: str) -> Application:
    application.status = ApplicationStatus.ERROR
    application.error_message = message
    db.add(AuditLog(application_id=application.id, actor="system", action="processing_failed",
                    detail={"error": message}))
    db.commit()
    log.warning("%s failed: %s", application.reference, redact(message))
    return application


def process(db: Session, application: Application, settings: Settings) -> Application:
    provider = get_provider(settings)
    try:
        result = analyse(application.pdf_data, provider, settings)
    except NoTextError as e:
        return _fail(db, application, str(e))
    except LLMError as e:
        return _fail(db, application, str(e))

    # Replace anything from a previous run.
    application.fields.clear()
    application.risks.clear()

    for f in result.fields.values():
        application.fields.append(ExtractedField(
            field_name=f.name, ai_value=f.value, ai_confidence=f.confidence,
            evidence=f.evidence, page=f.page, grounded=f.grounded, final_value=f.value,
        ))
    for flag in result.flags:
        application.risks.append(RiskFlag(
            source=flag.source, code=flag.code, severity=flag.severity,
            message=flag.message, policy_ref=flag.policy_ref,
        ))
    for call in result.calls:
        db.add(LlmCall(application_id=application.id, purpose=call.purpose, model=call.usage.model,
                       input_tokens=call.usage.input_tokens, output_tokens=call.usage.output_tokens,
                       latency_ms=call.usage.latency_ms, cost_usd=call.usage.cost_usd))

    application.raw_text_hash = result.text_hash
    application.summary = result.summary
    application.calculated_lvr = result.calculated_lvr
    application.overall_confidence = result.overall_confidence
    application.needs_review = result.needs_review
    application.error_message = None
    application.status = (ApplicationStatus.NEEDS_REVIEW if result.needs_review
                          else ApplicationStatus.EXTRACTED)

    db.add(AuditLog(application_id=application.id, actor="ai", action="ai_processed", detail={
        "provider": provider.name, "model": provider.model,
        "fields_found": sum(f.value is not None for f in result.fields.values()),
        "ungrounded": [f.name for f in result.fields.values() if not f.grounded],
        "flags": [f.code for f in result.flags],
        "llm_risks_rejected": [r.policy_ref for r in result.rejected_risks],
        "cache_hits": [c.purpose for c in result.calls if c.cached],
    }))
    db.commit()
    log.info("%s processed: %d flags, needs_review=%s",
             application.reference, len(result.flags), result.needs_review)
    return application


def _scored(application: Application) -> dict[str, ScoredField]:
    return {
        f.field_name: ScoredField(
            name=f.field_name, value=f.final_value, confidence=f.ai_confidence,
            evidence=f.evidence, page=f.page, grounded=f.grounded,
            grounding_note="Supporting quote not found in the document.",
            verified_by_human=f.edited_by is not None,
        )
        for f in application.fields
    }


def recheck(db: Session, application: Application, settings: Settings) -> Application:
    """Re-run the rules on the human-corrected values. LLM risks are kept as they were.

    A flag that is raised again keeps its acknowledgement; one that no longer
    applies disappears.
    """
    fields = _scored(application)
    result = rules.evaluate({n: f.value for n, f in fields.items()}, settings.assessment_date)
    new_flags: list[Flag] = result.flags + ungrounded_flags(fields)

    previous = {(r.code, r.message): r for r in application.risks if r.source in ("rule", "system")}
    kept_llm = [r for r in application.risks if r.source == "llm"]
    application.risks[:] = kept_llm
    for flag in new_flags:
        old = previous.get((flag.code, flag.message))
        application.risks.append(RiskFlag(
            source=flag.source, code=flag.code, severity=flag.severity, message=flag.message,
            policy_ref=flag.policy_ref,
            acknowledged=old.acknowledged if old else False,
            acknowledged_by=old.acknowledged_by if old else None,
        ))

    application.calculated_lvr = result.calculated_lvr
    application.needs_review = scoring.needs_review(
        fields, [(r.severity, r.acknowledged) for r in application.risks])
    application.updated_at = datetime.now(UTC)
    db.commit()
    return application
