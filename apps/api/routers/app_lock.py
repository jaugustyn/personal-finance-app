"""Optional privacy lock for the local single-user application."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.dependencies.app_lock import require_app_unlock
from finance.config import get_settings
from finance.db import get_session
from finance.profile.service import get_or_create_profile
from finance.security import app_lock

router = APIRouter(prefix="/app-lock", tags=["app-lock"])
TimeoutMinutes = Literal[5, 15, 30, 60]


class AppLockStatus(BaseModel):
    enabled: bool
    locked: bool
    timeout_minutes: int


class AppLockSetup(BaseModel):
    code: str = Field(min_length=6, max_length=128)
    timeout_minutes: TimeoutMinutes = 15


class AppLockUnlock(BaseModel):
    code: str = Field(min_length=6, max_length=128)


class AppLockSettingsUpdate(BaseModel):
    enabled: bool
    current_code: str = Field(min_length=6, max_length=128)
    timeout_minutes: TimeoutMinutes = 15
    new_code: str | None = Field(default=None, min_length=6, max_length=128)


@router.get("/status", response_model=AppLockStatus)
def status(
    request: Request,
    session: Session = Depends(get_session),
) -> AppLockStatus:
    profile = get_or_create_profile(session)
    enabled = profile.app_lock_secret_hash is not None
    locked = enabled and not app_lock.session_is_active(
        request.cookies.get(app_lock.APP_LOCK_COOKIE_NAME),
        profile.app_lock_timeout_minutes,
        touch=True,
    )
    return _status(enabled, locked, profile.app_lock_timeout_minutes)


@router.post("/setup", response_model=AppLockStatus)
def setup(
    payload: AppLockSetup,
    response: Response,
    session: Session = Depends(get_session),
) -> AppLockStatus:
    profile = get_or_create_profile(session)
    if profile.app_lock_secret_hash is not None:
        raise HTTPException(
            status_code=409,
            detail={"code": "app_lock_already_enabled"},
        )
    try:
        profile.app_lock_secret_hash = app_lock.hash_code(payload.code)
        profile.app_lock_timeout_minutes = app_lock.validate_timeout(
            payload.timeout_minutes
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    app_lock.revoke_all_sessions()
    _set_session_cookie(response, app_lock.create_session())
    return _status(True, False, profile.app_lock_timeout_minutes)


@router.post("/unlock", response_model=AppLockStatus)
def unlock(
    payload: AppLockUnlock,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> AppLockStatus:
    profile = get_or_create_profile(session)
    if profile.app_lock_secret_hash is None:
        _delete_session_cookie(response)
        return _status(False, False, profile.app_lock_timeout_minutes)

    client_key = _client_key(request)
    retry_after = app_lock.unlock_retry_after(client_key)
    if retry_after is not None:
        raise _too_many_attempts(retry_after)
    if not app_lock.verify_code(payload.code, profile.app_lock_secret_hash):
        retry_after = app_lock.record_failed_unlock(client_key)
        if retry_after is not None:
            raise _too_many_attempts(retry_after)
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_lock_code", "message": "Invalid code."},
        )

    app_lock.clear_failed_unlocks(client_key)
    app_lock.revoke_session(request.cookies.get(app_lock.APP_LOCK_COOKIE_NAME))
    _set_session_cookie(response, app_lock.create_session())
    return _status(True, False, profile.app_lock_timeout_minutes)


@router.post(
    "/activity",
    status_code=204,
    dependencies=[Depends(require_app_unlock)],
)
def activity() -> Response:
    return Response(status_code=204)


@router.post("/lock", status_code=204)
def lock(request: Request, response: Response) -> Response:
    app_lock.revoke_session(request.cookies.get(app_lock.APP_LOCK_COOKIE_NAME))
    _delete_session_cookie(response)
    response.status_code = 204
    return response


@router.put(
    "/settings",
    response_model=AppLockStatus,
    dependencies=[Depends(require_app_unlock)],
)
def update_settings(
    payload: AppLockSettingsUpdate,
    request: Request,
    response: Response,
    session: Session = Depends(get_session),
) -> AppLockStatus:
    profile = get_or_create_profile(session)
    if not app_lock.verify_code(payload.current_code, profile.app_lock_secret_hash):
        raise HTTPException(
            status_code=401,
            detail={"code": "invalid_lock_code", "message": "Invalid code."},
        )

    try:
        profile.app_lock_timeout_minutes = app_lock.validate_timeout(
            payload.timeout_minutes
        )
        if payload.enabled and payload.new_code is not None:
            profile.app_lock_secret_hash = app_lock.hash_code(payload.new_code)
        elif not payload.enabled:
            profile.app_lock_secret_hash = None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    session.commit()
    if not payload.enabled:
        app_lock.revoke_all_sessions()
        _delete_session_cookie(response)
        return _status(False, False, profile.app_lock_timeout_minutes)
    if payload.new_code is not None:
        app_lock.revoke_all_sessions()
        _set_session_cookie(response, app_lock.create_session())
    else:
        # The dependency already touched the current process-local session.
        token = request.cookies.get(app_lock.APP_LOCK_COOKIE_NAME)
        if not app_lock.session_is_active(
            token, profile.app_lock_timeout_minutes, touch=True
        ):
            _set_session_cookie(response, app_lock.create_session())
    return _status(True, False, profile.app_lock_timeout_minutes)


def _status(enabled: bool, locked: bool, timeout_minutes: int) -> AppLockStatus:
    return AppLockStatus(
        enabled=enabled,
        locked=locked,
        timeout_minutes=timeout_minutes,
    )


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _too_many_attempts(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=429,
        detail={
            "code": "app_lock_rate_limited",
            "message": "Too many failed unlock attempts.",
        },
        headers={"Retry-After": str(retry_after)},
    )


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=app_lock.APP_LOCK_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=get_settings().app_lock_cookie_secure,
        samesite="strict",
        path="/",
    )


def _delete_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=app_lock.APP_LOCK_COOKIE_NAME,
        path="/",
        secure=get_settings().app_lock_cookie_secure,
        httponly=True,
        samesite="strict",
    )
