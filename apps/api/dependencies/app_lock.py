"""FastAPI dependency enforcing the optional application lock."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from finance.db import get_session
from finance.profile.service import get_or_create_profile
from finance.security import app_lock


def require_app_unlock(
    request: Request,
    session: Session = Depends(get_session),
) -> None:
    profile = get_or_create_profile(session)
    if profile.app_lock_secret_hash is None:
        return
    token = request.cookies.get(app_lock.APP_LOCK_COOKIE_NAME)
    if app_lock.session_is_active(
        token,
        profile.app_lock_timeout_minutes,
        touch=True,
    ):
        return
    raise HTTPException(
        status_code=423,
        detail={
            "code": "app_locked",
            "message": "Application is locked.",
        },
    )

