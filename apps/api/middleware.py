"""Structlog request logging middleware."""
from __future__ import annotations

import time
import uuid
from collections import deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from structlog.contextvars import bind_contextvars, clear_contextvars

from finance.observability import get_logger

logger = get_logger("api.request")


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        bind_contextvars(request_id=request_id, path=request.url.path, method=request.method)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            logger.exception("request_failed", duration_ms=round(duration_ms, 2))
            clear_contextvars()
            raise
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["x-request-id"] = request_id
        logger.info(
            "request",
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        clear_contextvars()
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory sliding-window rate limiter (per client IP).

    Not for distributed deployments. Skips ``/health``.
    """

    def __init__(self, app, max_per_minute: int = 120) -> None:
        super().__init__(app)
        self.max = max(1, int(max_per_minute))
        self.window_s = 60.0
        self._hits: dict[str, deque[float]] = {}

    async def dispatch(self, request: Request, call_next) -> Response:
        public_paths = {
            "/health",
            "/health/live",
            "/health/ready",
            "/docs",
            "/openapi.json",
            "/redoc",
        }
        if request.url.path in public_paths:
            return await call_next(request)
        client = request.client.host if request.client else "anon"
        now = time.monotonic()
        bucket = self._hits.setdefault(client, deque())
        cutoff = now - self.window_s
        while bucket and bucket[0] < cutoff:
            bucket.popleft()
        if len(bucket) >= self.max:
            retry_after = max(1, int(self.window_s - (now - bucket[0])))
            return JSONResponse(
                {"detail": "rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds baseline hardening headers.

    Conservative CSP — the API only serves JSON/CSV plus Swagger UI on
    ``/docs``; ``frame-ancestors 'none'`` blocks clickjacking. ``HSTS`` is
    skipped because the app is typically self-hosted on plain HTTP behind a
    reverse proxy (the proxy should set HSTS).
    """

    _HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Content-Security-Policy": (
            "default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline'; "
            "frame-ancestors 'none'"
        ),
    }

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for k, v in self._HEADERS.items():
            response.headers.setdefault(k, v)
        return response

