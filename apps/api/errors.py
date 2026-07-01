"""Small helpers for consistent API error responses."""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def api_error(
    status_code: int,
    detail: Any,
    *,
    headers: dict[str, str] | None = None,
) -> HTTPException:
    return HTTPException(status_code=status_code, detail=detail, headers=headers)


def validation_error(detail: Any) -> HTTPException:
    return api_error(422, detail)


def bad_request(detail: Any) -> HTTPException:
    return api_error(400, detail)


def not_found(detail: Any) -> HTTPException:
    return api_error(404, detail)


def conflict(detail: Any) -> HTTPException:
    return api_error(409, detail)


def unsupported_media_type(detail: Any) -> HTTPException:
    return api_error(415, detail)


def payload_too_large(detail: Any) -> HTTPException:
    return api_error(413, detail)


def not_implemented(detail: Any) -> HTTPException:
    return api_error(501, detail)


def service_unavailable(detail: Any) -> HTTPException:
    return api_error(503, detail)
