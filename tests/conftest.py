"""Shared pytest fixtures.

Provides an isolated SQLite database for requests and background tasks.
PostgreSQL-specific behavior is covered by the separate integration suite.
"""
from __future__ import annotations

import os

# Disable runtime-only behavior during tests (must be set before app import).
# Assign explicitly because Docker Compose provides production-like defaults.
os.environ["RATE_LIMIT_PER_MINUTE"] = "0"
os.environ["APP_ENV"] = "test"
os.environ["APP_LOCK_COOKIE_SECURE"] = "false"
os.environ["API_TRUSTED_HOSTS"] = "testserver,localhost,127.0.0.1,api"
os.environ["API_DOCS_ENABLED"] = "true"
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from collections.abc import Iterator
from datetime import date

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


@pytest.fixture
def freeze_date(monkeypatch):
    """Freeze date.today only in the explicitly supplied domain modules."""
    def freeze(value: date, *modules) -> None:
        class FrozenDate(date):
            @classmethod
            def today(cls) -> date:
                return value

        for module in modules:
            monkeypatch.setattr(module, "date", FrozenDate)

    return freeze


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


@pytest.fixture
def session_factory(db_engine):
    factory = sessionmaker(bind=db_engine, autoflush=False)
    event.listen(factory, "before_flush", _assign_default_test_account)
    try:
        yield factory
    finally:
        event.remove(factory, "before_flush", _assign_default_test_account)


@pytest.fixture
def db_session(session_factory) -> Iterator[Session]:
    with session_factory() as session:
        yield session


@pytest.fixture
def client(session_factory, monkeypatch) -> Iterator[TestClient]:
    """Keep request sessions and background jobs in the same test database."""
    from apps.api.routers import imports, ml

    monkeypatch.setattr(imports, "SessionLocal", session_factory)
    monkeypatch.setattr(ml, "SessionLocal", session_factory)

    def _override_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override_session
    try:
        with TestClient(app, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)
