"""Tests for CORS and rate-limit middleware."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from apps.api.middleware import RateLimitMiddleware


def _make_app(rate_limit: int = 0, origins: list[str] | None = None) -> FastAPI:
    app = FastAPI()
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    if rate_limit > 0:
        app.add_middleware(RateLimitMiddleware, max_per_minute=rate_limit)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ping")
    def ping() -> dict[str, str]:
        return {"pong": "ok"}

    return app


def test_rate_limit_blocks_excess_requests() -> None:
    app = _make_app(rate_limit=3)
    client = TestClient(app)
    for _ in range(3):
        assert client.get("/ping").status_code == 200
    r = client.get("/ping")
    assert r.status_code == 429
    assert r.headers.get("Retry-After")


def test_rate_limit_skips_health_endpoint() -> None:
    app = _make_app(rate_limit=2)
    client = TestClient(app)
    # /health is exempt — should never be limited
    for _ in range(10):
        assert client.get("/health").status_code == 200


def test_cors_allows_configured_origin() -> None:
    app = _make_app(origins=["http://example.com"])
    client = TestClient(app)
    r = client.options(
        "/ping",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code == 200
    assert r.headers.get("access-control-allow-origin") == "http://example.com"


def test_cors_blocks_unknown_origin() -> None:
    app = _make_app(origins=["http://example.com"])
    client = TestClient(app)
    r = client.options(
        "/ping",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    # Starlette returns 400 when origin not allowed
    assert r.headers.get("access-control-allow-origin") != "http://evil.com"
