"""POST /api/approvals/callback — Power Automate reports the credit manager's decision."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Application, ApplicationStatus, AuditLog
from app.schemas import ApprovalCallback, ApprovalOut
from app.security import require_decision_key

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


@router.post("/callback", response_model=ApprovalOut, dependencies=[Depends(require_decision_key)])
def approval_callback(body: ApprovalCallback, db: Session = Depends(get_db)) -> ApprovalOut:
    application = db.scalar(select(Application).where(Application.id == body.application_id)
                            .options(selectinload(Application.approvals)))
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found.")
    pending = next((a for a in reversed(application.approvals) if a.decision is None), None)
    if pending is None or application.status != ApplicationStatus.PENDING_APPROVAL:
        # Flows retry on failure, so the same decision can arrive twice. Say so clearly.
        raise HTTPException(status.HTTP_409_CONFLICT, "No approval is waiting for this application.")

    pending.decision = body.decision
    pending.approver = body.approver
    pending.comment = body.comment or pending.comment
    pending.decided_at = datetime.now(UTC)
    pending.flow_run_id = body.flow_run_id
    application.status = (ApplicationStatus.APPROVED if body.decision == "approved"
                          else ApplicationStatus.DECLINED)
    db.add(AuditLog(application_id=application.id, actor="flow", action=f"approval_{body.decision}",
                    detail={"approver": body.approver, "comment": body.comment,
                            "flow_run_id": body.flow_run_id}))
    db.commit()
    return ApprovalOut.model_validate(pending, from_attributes=True)
