"""Reset the database and load the ten sample applications through the real pipeline.

    .venv/bin/python scripts/seed_db.py

Each sample is received as if a broker had emailed it, then processed.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.db import Base, SessionLocal, engine, init_db  # noqa: E402
from app.models import AuditLog  # noqa: E402
from app.pipeline.run import process  # noqa: E402
from app.services.intake import receive  # noqa: E402

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"

# Demo timing only: spread the ten arrivals over the last two weeks (days ago, hour of day)
# so the dashboard looks like a normal intake queue rather than ten emails in one second.
ARRIVALS = [(12, 9), (11, 14), (9, 10), (8, 16), (6, 11), (5, 9), (3, 15), (2, 10), (1, 13), (0, 9)]


def main() -> None:
    settings = get_settings()
    print(f"Provider: {settings.llm_provider}  |  database: {settings.database_url}")

    Base.metadata.drop_all(engine)
    init_db()
    shutil.rmtree(settings.storage_dir, ignore_errors=True)

    truth = json.loads((SAMPLES / "ground_truth.json").read_text())
    today = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
    with SessionLocal() as db:
        for sample, (days_ago, hour) in zip(truth["samples"], ARRIVALS):
            application = receive(
                db, settings, (SAMPLES / f"{sample['id']}.pdf").read_bytes(),
                source="email", sender_email="applications@harbourline.example",
                subject=f"Loan Application - {sample['fields']['borrower_name']}",
            )
            process(db, application, settings)

            arrived = today.replace(hour=hour) - timedelta(days=days_ago)
            application.received_at = application.created_at = arrived
            for i, entry in enumerate(db.query(AuditLog).filter_by(application_id=application.id)
                                      .order_by(AuditLog.id)):
                entry.created_at = arrived + timedelta(seconds=20 * i)
            db.commit()
            flags = ", ".join(sorted({r.code for r in application.risks})) or "-"
            print(f"{application.reference}  {sample['id']}  {application.status:<13}  "
                  f"conf {application.overall_confidence}  {flags}")


if __name__ == "__main__":
    main()
