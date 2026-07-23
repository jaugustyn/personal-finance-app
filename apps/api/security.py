"""Optional HTTP Basic Auth dependency.

Auth is disabled when both AUTH_USERNAME and AUTH_PASSWORD are empty.
Partial configuration is rejected while loading application settings.
The /health endpoint is always public.
"""
from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from finance.config import get_settings

_security = HTTPBasic(auto_error=False)


def auth_enabled() -> bool:
    s = get_settings()
    return bool(s.auth_username and s.auth_password)


def require_auth(
    request: Request,
    credentials: HTTPBasicCredentials | None = Depends(_security),
) -> None:
    """Validate Basic credentials. No-op when auth is disabled.

    Health endpoints (/health, /chat/health) skip auth at the router level
    by not depending on this function.
    """
    s = get_settings()
    if not (s.auth_username and s.auth_password):
        return
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )
    user_ok = secrets.compare_digest(credentials.username, s.auth_username)
    pass_ok = secrets.compare_digest(credentials.password, s.auth_password)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
