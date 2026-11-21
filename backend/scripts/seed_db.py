"""Reset the database and load the ten sample applications through the real pipeline.

    .venv/bin/python scripts/seed_db.py

Each sample is received as if a broker had emailed it, then processed.
On the live site, POST /api/admin/reset-demo does the same.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.services.demo import reset  # noqa: E402


def main() -> None:
    settings = get_settings()
    print(f"Provider: {settings.llm_provider}  |  database: {settings.database_url.split('@')[-1]}")
    with SessionLocal() as db:
        for a in reset(db, settings):
            flags = ", ".join(sorted({r.code for r in a.risks})) or "-"
            print(f"{a.reference}  {a.pdf_filename}  {a.status:<13}  conf {a.overall_confidence}  {flags}")


if __name__ == "__main__":
    main()
