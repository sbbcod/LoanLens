"""Write protection: every endpoint that changes data requires a key.

Reading is open so the public demo link works without signing in. Changing
anything (uploading, editing, approving) needs the X-API-Key header, so the
link can't be used by strangers to run up LLM costs.
"""

from __future__ import annotations

import secrets

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings, get_settings


def require_write_key(
    x_api_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    allowed = (settings.api_key, settings.demo_passcode)
    # compare_digest takes the same time whether the first or last character differs,
    # so the key can't be guessed one character at a time by timing responses.
    if not x_api_key or not any(secrets.compare_digest(x_api_key, k) for k in allowed):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "A valid X-API-Key header is required.")


def require_admin_key(
    x_api_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """For destructive actions: only the system key, never the shared demo passcode."""
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "The system API key is required.")


def require_decision_key(
    x_api_key: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """Who may record a credit decision.

    With the Teams flow connected, only the flow (holding the system key) can, so a
    reviewer with the demo passcode can't approve an application from the web page.
    Without it, the demo passcode may, so the review page can play the manager's part.
    """
    if settings.approval_flow_url:
        require_admin_key(x_api_key, settings)
    else:
        require_write_key(x_api_key, settings)


def current_user(x_user_name: str | None = Header(default=None)) -> str:
    """Who is acting, for the audit log. The demo has no user accounts, so the
    front end sends the name the reviewer typed. Real systems use sign-in."""
    name = (x_user_name or "").strip()[:60]
    return f"user:{name or 'analyst'}"
