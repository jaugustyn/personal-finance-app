"""Tests for security headers middleware and split health endpoints."""
from __future__ import annotations

from finance.db import engine


def test_security_headers_applied(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'self'" in r.headers["content-security-policy"]


def test_health_live_returns_ok(client) -> None:
    r = client.get("/health/live")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_ready_reports_db(client) -> None:
    r = client.get("/health/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] is True


def test_request_id_echoed_in_response(client) -> None:
    r = client.get("/health", headers={"X-Request-ID": "test-correlation-id"})
    assert r.headers.get("x-request-id") == "test-correlation-id"


def test_untrusted_host_is_rejected(client) -> None:
    response = client.get("/health", headers={"Host": "attacker.example"})

    assert response.status_code == 400


def test_database_engine_hides_bound_parameters() -> None:
    assert engine.hide_parameters is True
