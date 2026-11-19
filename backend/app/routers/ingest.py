"""POST /api/ingest — where every application enters, from Power Automate or the upload button."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import SessionLocal, get_db
from app.models import Application
from app.pipeline.run import process
from app.schemas import IngestResponse
from app.security import require_write_key
from app.services.intake import receive

router = APIRouter(prefix="/api", tags=["intake"])


def _process_in_background(application_id: str) -> None:
    """Runs after the response is sent, with its own database session."""
    with SessionLocal() as db:
        application = db.get(Application, application_id)
        if application:
            process(db, application, get_settings())


@router.post("/ingest", response_model=IngestResponse, status_code=status.HTTP_202_ACCEPTED,
             dependencies=[Depends(require_write_key)])
async def ingest(
    background: BackgroundTasks,
    file: UploadFile = File(..., description="The application PDF"),
    sender_email: str | None = Form(None),
    subject: str | None = Form(None),
    source: Literal["email", "upload"] = Form("upload"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> IngestResponse:
    """Accept a PDF and return straight away; the AI pipeline runs in the background.

    Returning quickly matters for Power Automate: its HTTP action would time out
    waiting for two LLM calls. The caller gets a reference and can poll the record.
    """
    data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            f"PDF is larger than {settings.max_upload_mb} MB.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only PDF files are accepted.")

    application = receive(db, settings, data, source=source,
                          sender_email=sender_email, subject=subject)
    background.add_task(_process_in_background, application.id)
    return IngestResponse(id=application.id, reference=application.reference,
                          status=application.status)
