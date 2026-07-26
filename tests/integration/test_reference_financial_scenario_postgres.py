"""PostgreSQL import and deduplication path for the reference scenario."""
from __future__ import annotations

import json
import os
from collections.abc import Iterator

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from apps.api.main import app
from finance.categories import seed_system_categories
from finance.config import get_settings
from finance.db import get_session
from finance.domain.models import Base, Transaction
from tests.reference_scenario import (
    EUR_RATE_DATE,
    GENERIC_COLUMN_MAP,
    REFERENCE_SCENARIO,
    assert_assistant_contract,
    assert_category_and_merchant_contract,
    assert_currency_contract,
    assert_export_contract,
    assert_recap_contract,
    assert_stats_contract,
    assert_transaction_contract,
    finalize_reference_scenario,
    generic_csv_bytes,
    revolut_csv_bytes,
)

pytestmark = pytest.mark.postgres_integration


def _test_database_url() -> str:
    value = os.getenv("TEST_DATABASE_URL", "").strip()
    if not value:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    database = make_url(value).database or ""
    if not database.lower().endswith("_test"):
        pytest.fail("Refusing to clean a database whose name does not end with '_test'")
    return value


@pytest.fixture()
def postgres_reference(monkeypatch) -> Iterator[tuple[Session, TestClient]]:
    database_url = _test_database_url()
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")

    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(delete(table))

    def override_session() -> Iterator[Session]:
        with session_factory() as request_session:
            yield request_session

    from apps.api.routers import imports as imports_router
    from finance.ingestion import service as ingestion_service
    from finance.llm import client as llm_client

    monkeypatch.setattr(imports_router, "_suggest_import_categories", lambda _id: None)
    monkeypatch.setattr(llm_client, "is_available", lambda: False)
    monkeypatch.setattr(
        ingestion_service,
        "prefetch_nbp_rates",
        lambda _session, **_kwargs: None,
    )
    app.dependency_overrides[get_session] = override_session
    session = session_factory()
    seed_system_categories(session)
    session.commit()
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield session, client
    finally:
        session.close()
        app.dependency_overrides.pop(get_session, None)
        with engine.begin() as connection:
            for table in reversed(Base.metadata.sorted_tables):
                connection.execute(delete(table))
        engine.dispose()
        get_settings.cache_clear()


def _upload_generic(client: TestClient, account_id: int) -> dict:
    response = client.post(
        "/imports",
        files={"file": ("reference-generic.csv", generic_csv_bytes(), "text/csv")},
        data={
            "source": "generic",
            "column_map": json.dumps(GENERIC_COLUMN_MAP),
            "fx_mode": "prefetch_missing",
            "account_id": str(account_id),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _upload_revolut(client: TestClient, account_id: int) -> dict:
    response = client.post(
        "/imports",
        files={"file": ("reference-revolut.csv", revolut_csv_bytes(), "text/csv")},
        data={
            "source": "revolut",
            "fx_mode": "prefetch_missing",
            "account_id": str(account_id),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _assert_import_summary(
    summary: dict,
    *,
    source: str,
    total_rows: int,
    inserted: int,
    duplicates: int,
) -> None:
    assert isinstance(summary.get("import_id"), int)
    assert summary["source"] == source
    assert summary["total_rows"] == total_rows
    assert summary["inserted"] == inserted
    assert summary["duplicates"] == duplicates


def test_reference_scenario_through_real_import(postgres_reference) -> None:
    session, client = postgres_reference
    generic_count = sum(
        transaction.source == "generic"
        for transaction in REFERENCE_SCENARIO.transactions
    )
    revolut_count = sum(
        transaction.source == "revolut"
        for transaction in REFERENCE_SCENARIO.transactions
    )
    rate = client.post(
        "/currencies/rates",
        json={
            "currency": "EUR",
            "rate_date": EUR_RATE_DATE.isoformat(),
            "rate": "4.50",
        },
    )
    assert rate.status_code == 201, rate.text
    main_account = client.post(
        "/accounts",
        json={"name": "Rachunek główny", "kind": "bank"},
    )
    revolut_account = client.post(
        "/accounts",
        json={"name": "Revolut", "kind": "bank"},
    )
    assert main_account.status_code == 201, main_account.text
    assert revolut_account.status_code == 201, revolut_account.text
    main_account_id = main_account.json()["id"]
    revolut_account_id = revolut_account.json()["id"]

    _assert_import_summary(
        _upload_generic(client, main_account_id),
        source="unknown",
        total_rows=generic_count,
        inserted=generic_count,
        duplicates=0,
    )
    _assert_import_summary(
        _upload_revolut(client, revolut_account_id),
        source="revolut",
        total_rows=revolut_count,
        inserted=revolut_count,
        duplicates=0,
    )
    _assert_import_summary(
        _upload_generic(client, main_account_id),
        source="unknown",
        total_rows=generic_count,
        inserted=0,
        duplicates=generic_count,
    )
    _assert_import_summary(
        _upload_revolut(client, revolut_account_id),
        source="revolut",
        total_rows=revolut_count,
        inserted=0,
        duplicates=revolut_count,
    )
    assert session.scalar(select(func.count(Transaction.id))) == (
        REFERENCE_SCENARIO.expected.transaction_count
    )

    ids = finalize_reference_scenario(session, client)
    session.expire_all()
    assert_transaction_contract(session, client, ids)
    assert_stats_contract(client)
    assert_recap_contract(client)
    assert_category_and_merchant_contract(client)
    assert_currency_contract(client)
    assert_export_contract(client)
    assert_assistant_contract(session, client)
