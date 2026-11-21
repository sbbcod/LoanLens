"""POST /api/admin/reset-demo — put the live demo back to its ten sample applications."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, status

from app.config import get_settings
from app.db import SessionLocal
from app.security import require_admin_key
from app.services.demo import reset

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _reset() -> None:
    with SessionLocal() as db:
        reset(db, get_settings())


@router.post("/reset-demo", status_code=status.HTTP_202_ACCEPTED,
             dependencies=[Depends(require_admin_key)])
def reset_demo(background: BackgroundTasks) -> dict[str, str]:
    """Wipes all data and reloads the samples. Needs the system API key, not the demo passcode."""
    background.add_task(_reset)
    return {"status": "resetting"}
