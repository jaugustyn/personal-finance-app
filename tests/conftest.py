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
os.environ["APP_LOCK_COOKIE_SECURE"] = "false"

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.main import app
from finance.categories import seed_system_categories
from finance.db import get_session
from finance.domain.enums import AccountKind, BankSource
from finance.domain.models import Account, Base, Import, Transaction

DEFAULT_TEST_ACCOUNT_ID = 1


def _assign_default_test_account(
    session: Session,
    _flush_context: object,
    _instances: object,
) -> None:
    """Keep direct ORM fixtures concise; API contracts still require account_id."""
    for row in session.new:
        if isinstance(row, (Import, Transaction)) and row.account_id is None:
            row.account_id = DEFAULT_TEST_ACCOUNT_ID


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
    with Session(engine) as session:
        session.add(
            Account(
                id=DEFAULT_TEST_ACCOUNT_ID,
                name="Test account",
                kind=AccountKind.BANK,
                source=BankSource.UNKNOWN,
                currency="PLN",
            )
        )
        seed_system_categories(session)
        session.commit()
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Iterator[Session]:
    SessionMaker = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)
    event.listen(SessionMaker, "before_flush", _assign_default_test_account)
    session = SessionMaker()
    try:
        yield session
    finally:
        session.close()
        event.remove(SessionMaker, "before_flush", _assign_default_test_account)


@pytest.fixture(scope="function")
def client(db_engine) -> Iterator[TestClient]:
    """TestClient with ``get_session`` pointing at the in-memory SQLite."""
    SessionMaker = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)
    event.listen(SessionMaker, "before_flush", _assign_default_test_account)

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
        event.remove(SessionMaker, "before_flush", _assign_default_test_account)
