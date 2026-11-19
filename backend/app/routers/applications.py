"""Reading, correcting and sending applications for approval."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.db import get_db
from app.models import (
    Application, ApplicationStatus, Approval, AuditLog, LlmCall,
)
from app.pipeline import policy_review
from app.pipeline.analyse import clean_value
from app.pipeline.fields import FIELDS_BY_NAME
from app.pipeline.run import recheck
from app.routers.ingest import _process_in_background
from app.schemas import (
    AcknowledgeRequest, ApplicationDetail, ApplicationSummary, FieldEdits, SubmitRequest,
)
from app.security import current_user, require_write_key
from app.services import power_automate, views

router = APIRouter(prefix="/api", tags=["applications"])

# Once it's with the credit manager (or decided), nothing about it can change.
LOCKED = {ApplicationStatus.PENDING_APPROVAL, ApplicationStatus.APPROVED, ApplicationStatus.DECLINED}


def _load(db: Session, application_id: str) -> Application:
    application = db.scalar(
        select(Application).where(Application.id == application_id).options(
            selectinload(Application.fields), selectinload(Application.risks),
            selectinload(Application.approvals)))
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found.")
    return application


def _detail(db: Session, application: Application) -> ApplicationDetail:
    audit = db.scalars(select(AuditLog).where(AuditLog.application_id == application.id)
                       .order_by(AuditLog.created_at, AuditLog.id)).all()
    cost = db.scalar(select(func.coalesce(func.sum(LlmCall.cost_usd), 0.0))
                     .where(LlmCall.application_id == application.id)) or 0.0
    return views.detail(application, list(audit), cost)


def _unlocked(application: Application) -> None:
    if application.status in LOCKED:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Application is {application.status.replace('_', ' ')} and can't be changed.")


# --- Read --------------------------------------------------------------------


@router.get("/applications", response_model=list[ApplicationSummary])
def list_applications(
    status_: str | None = Query(None, alias="status"),
    needs_review: bool | None = None,
    q: str | None = Query(None, description="Search reference or borrower name"),
    db: Session = Depends(get_db),
) -> list[ApplicationSummary]:
    stmt = (select(Application).options(selectinload(Application.fields),
                                        selectinload(Application.risks))
            .order_by(Application.received_at.desc()))
    if status_:
        stmt = stmt.where(Application.status == status_)
    if needs_review is not None:
        stmt = stmt.where(Application.needs_review == needs_review)
    items = [views.summary(a) for a in db.scalars(stmt).all()]
    if q:
        # Borrower name lives in a JSON column, which databases search differently,
        # so filter here. Fine at demo scale; a real system would index a borrower column.
        needle = q.lower()
        items = [i for i in items
                 if needle in i.reference.lower() or needle in (i.borrower_name or "").lower()]
    return items


@router.get("/applications/{application_id}", response_model=ApplicationDetail)
def get_application(application_id: str, db: Session = Depends(get_db)) -> ApplicationDetail:
    return _detail(db, _load(db, application_id))


@router.get("/applications/{application_id}/pdf", response_class=FileResponse)
def get_pdf(application_id: str, db: Session = Depends(get_db)) -> FileResponse:
    application = _load(db, application_id)
    path = Path(application.pdf_path)
    if not path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PDF file is missing.")
    return FileResponse(path, media_type="application/pdf",
                        headers={"Content-Disposition": f'inline; filename="{application.reference}.pdf"'})


@router.get("/policy", response_class=PlainTextResponse, tags=["system"])
def get_policy() -> str:
    """The credit policy, so the UI can show the clause behind a flag."""
    return policy_review.policy_text()


# --- Change ------------------------------------------------------------------


@router.patch("/applications/{application_id}/fields", response_model=ApplicationDetail,
              dependencies=[Depends(require_write_key)])
def edit_fields(application_id: str, body: FieldEdits, db: Session = Depends(get_db),
                settings: Settings = Depends(get_settings),
                user: str = Depends(current_user)) -> ApplicationDetail:
    """Correct extracted values. The AI's original stays on record; rules re-run immediately."""
    application = _load(db, application_id)
    _unlocked(application)
    by_name = {f.field_name: f for f in application.fields}
    now = datetime.now(UTC)

    for name, raw in body.changes.items():
        spec = FIELDS_BY_NAME.get(name)
        if spec is None or name not in by_name:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Unknown field: {name}")
        value = clean_value(spec, raw)
        if raw not in (None, "") and value is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                f"{spec.label}: {raw!r} is not a valid {spec.kind}.")
        f = by_name[name]
        db.add(AuditLog(application_id=application.id, actor=user, action="field_edited",
                        detail={"field": name, "from": f.final_value, "to": value,
                                "ai_value": f.ai_value}))
        f.final_value, f.edited_by, f.edited_at = value, user, now

    recheck(db, application, settings)
    db.refresh(application)
    return _detail(db, application)


@router.post("/applications/{application_id}/acknowledge-risk", response_model=ApplicationDetail,
             dependencies=[Depends(require_write_key)])
def acknowledge_risk(application_id: str, body: AcknowledgeRequest, db: Session = Depends(get_db),
                     settings: Settings = Depends(get_settings),
                     user: str = Depends(current_user)) -> ApplicationDetail:
    """Record that a person has seen a risk. It stays on the application; it isn't dismissed."""
    application = _load(db, application_id)
    _unlocked(application)
    risk = next((r for r in application.risks if r.id == body.risk_id), None)
    if risk is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Risk not found on this application.")
    risk.acknowledged = body.acknowledged
    risk.acknowledged_by = user if body.acknowledged else None
    db.add(AuditLog(application_id=application.id, actor=user,
                    action="risk_acknowledged" if body.acknowledged else "risk_unacknowledged",
                    detail={"code": risk.code, "policy_ref": risk.policy_ref}))
    recheck(db, application, settings)
    db.refresh(application)
    return _detail(db, application)


@router.post("/applications/{application_id}/submit-for-approval", response_model=ApplicationDetail,
             dependencies=[Depends(require_write_key)])
def submit_for_approval(application_id: str, body: SubmitRequest, db: Session = Depends(get_db),
                        settings: Settings = Depends(get_settings),
                        user: str = Depends(current_user)) -> ApplicationDetail:
    """Send to a credit manager. Blocked while any critical risk is unacknowledged (§9.2)."""
    application = _load(db, application_id)
    _unlocked(application)
    if application.status in (ApplicationStatus.RECEIVED, ApplicationStatus.ERROR):
        raise HTTPException(status.HTTP_409_CONFLICT, "Application hasn't been processed.")
    open_critical = [r.code for r in application.risks if r.severity == "critical" and not r.acknowledged]
    if open_critical:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Acknowledge critical risks first: {', '.join(open_critical)}.")

    approval = Approval(application_id=application.id, requested_by=user, comment=body.comment)
    application.approvals.append(approval)
    application.status = ApplicationStatus.PENDING_APPROVAL
    db.add(AuditLog(application_id=application.id, actor=user, action="submitted_for_approval",
                    detail={"comment": body.comment}))
    db.flush()

    try:
        sent = power_automate.request_approval(settings, application, views.summary(application),
                                               [r for r in application.risks])
    except power_automate.FlowError as e:
        db.rollback()
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(e)) from e
    db.add(AuditLog(application_id=application.id, actor="system", action="approval_requested",
                    detail={"channel": "power_automate" if sent else "simulated"}))
    db.commit()
    db.refresh(application)
    return _detail(db, application)


@router.post("/applications/{application_id}/reprocess", response_model=ApplicationDetail,
             dependencies=[Depends(require_write_key)])
def reprocess(application_id: str, background: BackgroundTasks, db: Session = Depends(get_db),
              user: str = Depends(current_user)) -> ApplicationDetail:
    """Run the AI pipeline again. Human edits are discarded (they are kept in the audit log)."""
    application = _load(db, application_id)
    _unlocked(application)
    application.status = ApplicationStatus.RECEIVED
    db.add(AuditLog(application_id=application.id, actor=user, action="reprocess_requested"))
    db.commit()
    background.add_task(_process_in_background, application.id)
    return _detail(db, application)
