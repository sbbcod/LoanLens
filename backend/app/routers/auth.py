"""GET /api/auth/check — lets the web page confirm a passcode before it is saved."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.security import require_write_key

router = APIRouter(prefix="/api/auth", tags=["system"])


@router.get("/check", dependencies=[Depends(require_write_key)])
def check() -> dict[str, bool]:
    """200 if the X-API-Key header is the API key or the demo passcode, 401 otherwise.

    Without this, a mistyped passcode would be accepted silently and every edit
    would fail later with no obvious cause.
    """
    return {"ok": True}
