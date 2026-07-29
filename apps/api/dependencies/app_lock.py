"""FastAPI dependency enforcing the optional application lock."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from finance.db import get_session
from finance.profile.service import get_profile
from finance.security import app_lock


def require_app_unlock(
    request: Request,
    session: Session = Depends(get_session),
) -> None:
    _require_active_session(request, session, touch=False)


def register_app_activity(
    request: Request,
    session: Session = Depends(get_session),
) -> None:
    """Validate and extend the session only after explicit browser activity."""
    _require_active_session(request, session, touch=True)


def _require_active_session(
    request: Request,
    session: Session,
    *,
    touch: bool,
) -> None:
    profile = get_profile(session)
    if profile is None or profile.app_lock_secret_hash is None:
        return
    token = request.cookies.get(app_lock.APP_LOCK_COOKIE_NAME)
    if app_lock.session_is_active(
        token,
        profile.app_lock_timeout_minutes,
        touch=touch,
    ):
        return
    raise HTTPException(
        status_code=423,
        detail={
            "code": "app_locked",
            "message": "Application is locked.",
        },
    )
