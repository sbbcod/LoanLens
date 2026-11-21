"""Reset the database to the ten sample applications.

Used by scripts/seed_db.py locally and by POST /api/admin/reset-demo on the
live site. Every sample goes through the real pipeline; with the Claude
provider, the recorded answers in data/recorded_llm are replayed, so a reset
costs nothing.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import Settings
from app.db import Base, engine, init_db
from app.models import Application, AuditLog
from app.pipeline.run import process
from app.services.intake import receive

SAMPLES = Path(__file__).resolve().parents[2] / "data" / "samples"

# Demo timing only: spread the ten arrivals over the last two weeks (days ago, hour)
# so the dashboard looks like a normal intake queue rather than ten emails in one second.
ARRIVALS = [(12, 9), (11, 14), (9, 10), (8, 16), (6, 11), (5, 9), (3, 15), (2, 10), (1, 13), (0, 9)]


def reset(db: Session, settings: Settings) -> list[Application]:
    db.close()
    Base.metadata.drop_all(engine)
    init_db()

    truth = json.loads((SAMPLES / "ground_truth.json").read_text())
    today = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    created = []
    for sample, (days_ago, hour) in zip(truth["samples"], ARRIVALS):
        application = receive(
            db, settings, (SAMPLES / f"{sample['id']}.pdf").read_bytes(),
            source="email", filename=f"{sample['id']}.pdf",
            sender_email="applications@harbourline.example",
            subject=f"Loan Application - {sample['fields']['borrower_name']}",
        )
        process(db, application, settings)

        arrived = today.replace(hour=hour) - timedelta(days=days_ago)
        application.received_at = application.created_at = arrived
        entries = db.query(AuditLog).filter_by(application_id=application.id).order_by(AuditLog.id)
        for i, entry in enumerate(entries):
            entry.created_at = arrived + timedelta(seconds=20 * i)
        db.commit()
        created.append(application)
    return created
