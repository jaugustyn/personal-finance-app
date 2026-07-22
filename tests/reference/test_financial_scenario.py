"""Fast cross-module contract for the synthetic financial scenario."""
from __future__ import annotations

import pytest

from tests.reference_scenario import (
    assert_assistant_contract,
    assert_category_and_merchant_contract,
    assert_currency_contract,
    assert_export_contract,
    assert_recap_contract,
    assert_stats_contract,
    assert_transaction_contract,
    finalize_reference_scenario,
    seed_sqlite_reference_scenario,
)


@pytest.fixture()
def reference_scenario(db_session, client):
    seed_sqlite_reference_scenario(db_session)
    ids = finalize_reference_scenario(db_session, client)
    db_session.expire_all()
    return ids


def test_reference_transactions_and_provenance(
    db_session,
    client,
    reference_scenario,
) -> None:
    assert_transaction_contract(db_session, client, reference_scenario)


def test_reference_financial_stats(client, reference_scenario) -> None:
    assert_stats_contract(client)


def test_reference_recap(client, reference_scenario) -> None:
    assert_recap_contract(client)


def test_reference_categories_and_merchants(client, reference_scenario) -> None:
    assert_category_and_merchant_contract(client)


def test_reference_currencies(client, reference_scenario) -> None:
    assert_currency_contract(client)


def test_reference_export(client, reference_scenario) -> None:
    assert_export_contract(client)


def test_reference_deterministic_assistant(
    db_session,
    client,
    reference_scenario,
) -> None:
    db_session.expire_all()
    assert_assistant_contract(db_session, client)
