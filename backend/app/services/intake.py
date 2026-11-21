"""Receiving a new application: store the PDF, create the record, log it."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Application, AuditLog, new_id


def next_reference(db: Session, year: int) -> str:
    prefix = f"APP-{year}-"
    count = db.scalar(select(func.count()).where(Application.reference.like(f"{prefix}%"))) or 0
    return f"{prefix}{count + 1:04d}"


def receive(db: Session, settings: Settings, pdf_bytes: bytes, *, source: str,
            filename: str | None = None, sender_email: str | None = None,
            subject: str | None = None) -> Application:
    app_id = new_id()
    application = Application(
        id=app_id,
        reference=next_reference(db, settings.assessment_date.year),
        source=source,
        sender_email=sender_email,
        subject=subject,
        pdf_filename=filename,
        pdf_data=pdf_bytes,
    )
    db.add(application)
    db.add(AuditLog(application_id=app_id, actor="system", action="received",
                    detail={"source": source, "bytes": len(pdf_bytes)}))
    db.commit()
    return application
