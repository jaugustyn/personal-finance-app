"""Shared pytest fixtures.

Provides a SQLite in-memory database with FastAPI's ``get_session`` dependency
overridden, so router tests don't need a running Postgres. Endpoints relying
on postgres-specific features (``ON CONFLICT``) are tested separately and
skipped when no real Postgres is reachable.
"""
from __future__ import annotations

import os

# Disable runtime-only behavior during tests (must be set before app import).
# Assign explicitly because Docker Compose provides production-like defaults.
os.environ["RATE_LIMIT_PER_MINUTE"] = "0"
os.environ["APP_ENV"] = "test"

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from finance.db import get_session
from finance.domain.models import Base


@pytest.fixture(scope="function")
def db_engine():
    """Fresh in-memory SQLite for every test (isolation)."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Iterator[Session]:
    SessionMaker = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)
    session = SessionMaker()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db_engine) -> Iterator[TestClient]:
    """TestClient with ``get_session`` pointing at the in-memory SQLite."""
    SessionMaker = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)

    def _override_session() -> Iterator[Session]:
        s = SessionMaker()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_session] = _override_session
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.dependency_overrides.pop(get_session, None)
