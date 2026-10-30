"""Cashflow and overview must use the same direction/type accounting rules."""

from datetime import date
from decimal import Decimal

import pytest

from finance.domain.models import Transaction
from finance.stats.service import cashflow, overview
from finance.transactions.type_service import TransactionTypeService


@pytest.mark.parametrize("include_transfers", [False, True])
def test_cashflow_matches_overview_even_with_explicit_direction_overrides(
    db_session,
    include_transfers,
) -> None:
    for month in (1, 2):
        for tx_type in (
            "salary",
            "income",
            "expense",
            "refund",
            "debt_payment",
            "asset_allocation",
        ):
            for direction in ("credit", "debit"):
                tx = Transaction(
                    booking_date=date(2026, month, 5),
                    amount=Decimal("100") if direction == "credit" else Decimal("-100"),
                    currency="PLN",
                    direction=direction,
                    source="manual",
                    merchant="Synthetic store",
                    title="Accounting test",
                    dedup_hash=f"cashflow-{month}-{tx_type}-{direction}",
                )
                db_session.add(tx)
                TransactionTypeService(db_session).apply_manual_type(
                    tx,
                    tx_type,
                    allow_direction_mismatch=True,
                )
        for name, currency, transfer in (("transfer", "PLN", True), ("no-fx", "EUR", False)):
            db_session.add(
                Transaction(
                    booking_date=date(2026, month, 5),
                    amount=Decimal("-999"),
                    currency=currency,
                    direction="debit",
                    source="manual",
                    transaction_type="expense",
                    is_transfer=transfer,
                    dedup_hash=f"cashflow-{month}-{name}",
                )
            )
    db_session.commit()

    totals = overview(db_session, months=None, include_transfers=include_transfers)
    buckets = cashflow(db_session, months=None, include_transfers=include_transfers)

    assert [bucket.month for bucket in buckets] == ["2026-01", "2026-02"]
    assert totals.total_income == Decimal("400")
    assert totals.unconverted_count == 2
    for bucket in buckets:
        assert bucket.income == Decimal("200")
        assert bucket.refunds == Decimal("100")
        assert bucket.debt_payments == Decimal("100")
        assert bucket.asset_allocations == Decimal("100")
    for bucket_field, total_field in (
        ("income", "total_income"),
        ("expenses", "total_expenses"),
        ("refunds", "total_refunds"),
        ("debt_payments", "total_debt_payments"),
        ("asset_allocations", "total_asset_allocations"),
        ("net", "net_cashflow"),
    ):
        assert sum(getattr(bucket, bucket_field) for bucket in buckets) == getattr(
            totals, total_field
        )
