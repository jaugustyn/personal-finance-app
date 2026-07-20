"""Tests for the deterministic period recap aggregations."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from finance.domain.enums import Category, TransactionDirection, TransactionType
from finance.domain.models import Transaction
from finance.stats import recap


def _tx(**kwargs) -> Transaction:
    defaults = dict(
        booking_date=date(2026, 1, 1),
        amount=Decimal("20.00"),
        currency="PLN",
        direction=TransactionDirection.DEBIT.value,
        merchant="Shop",
        title="",
        source="pekao",
        dedup_hash=f"r{_tx.counter}",
        transaction_type=TransactionType.EXPENSE.value,
        is_transfer=False,
    )
    if (
        kwargs.get("direction") == TransactionDirection.CREDIT.value
        and "transaction_type" not in kwargs
    ):
        defaults["transaction_type"] = TransactionType.INCOME.value
    _tx.counter += 1
    defaults.update(kwargs)
    return Transaction(**defaults)


_tx.counter = 0

TODAY = date(2026, 2, 15)
CURRENT_DAY = TODAY - timedelta(days=2)  # inside the current calendar month
PREVIOUS_DAY = date(2026, 1, 6)  # inside the comparable previous-month window


def test_recap_cashflow_and_category_delta(db_session: Session) -> None:
    db_session.add_all(
        [
            # current window: spend 100 food, 30 transport
            _tx(booking_date=CURRENT_DAY, category=Category.FOOD.value, amount=Decimal("-100.00")),
            _tx(booking_date=CURRENT_DAY, category=Category.TRANSPORT.value, amount=Decimal("-30.00")),
            _tx(
                booking_date=CURRENT_DAY,
                direction=TransactionDirection.CREDIT.value,
                amount=Decimal("500.00"),
            ),
            # previous comparable window: spend 40 food
            _tx(booking_date=PREVIOUS_DAY, category=Category.FOOD.value, amount=Decimal("-40.00")),
            # outside the comparable Jan 1-15 window
            _tx(
                booking_date=date(2026, 1, 25),
                direction=TransactionDirection.CREDIT.value,
                amount=Decimal("700.00"),
            ),
        ]
    )
    db_session.commit()

    result = recap.period_recap(db_session, period="month", today=TODAY)

    assert result["period"] == "month"
    assert result["current_from"] == date(2026, 2, 1)
    assert result["current_to"] == TODAY
    assert result["previous_from"] == date(2026, 1, 1)
    assert result["previous_to"] == date(2026, 1, 15)
    assert result["cashflow"]["income"] == Decimal("500.00")
    assert result["cashflow"]["income_delta"] == Decimal("500.00")
    assert result["cashflow"]["expenses"] == Decimal("130.00")
    assert result["cashflow"]["expenses_delta"] == Decimal("90.00")
    assert result["cashflow"]["net"] == Decimal("370.00")
    assert result["cashflow"]["net_delta"] == Decimal("410.00")
    # food rose from 40 -> 100 => delta 60, transport new => 30
    changes = {c["category"]: c["delta"] for c in result["category_changes"]}
    assert changes[Category.FOOD.value] == Decimal("60.00")
    assert changes[Category.TRANSPORT.value] == Decimal("30.00")
    # food is the largest mover
    assert result["category_changes"][0]["category"] == Category.FOOD.value
    assert result["category_changes"][0]["current_count"] == 1
    assert result["category_changes"][0]["previous_count"] == 1


def test_recap_uses_financial_type_semantics(db_session: Session) -> None:
    db_session.add_all(
        [
            _tx(booking_date=CURRENT_DAY, category=Category.FOOD.value, amount=Decimal("-120.00")),
            _tx(
                booking_date=CURRENT_DAY,
                direction=TransactionDirection.CREDIT.value,
                transaction_type=TransactionType.REFUND.value,
                category=Category.FOOD.value,
                amount=Decimal("20.00"),
            ),
            _tx(
                booking_date=CURRENT_DAY,
                transaction_type=TransactionType.DEBT_PAYMENT.value,
                amount=Decimal("-50.00"),
            ),
            _tx(
                booking_date=CURRENT_DAY,
                transaction_type=TransactionType.ASSET_ALLOCATION.value,
                amount=Decimal("-30.00"),
            ),
            _tx(
                booking_date=CURRENT_DAY,
                transaction_type=TransactionType.OWN_TRANSFER.value,
                is_transfer=True,
                amount=Decimal("-999.00"),
            ),
            _tx(
                booking_date=CURRENT_DAY,
                direction=TransactionDirection.CREDIT.value,
                amount=Decimal("400.00"),
            ),
        ]
    )
    db_session.commit()

    result = recap.period_recap(db_session, period="month", today=TODAY)

    assert result["cashflow"]["income"] == Decimal("400.00")
    assert result["cashflow"]["gross_expenses"] == Decimal("120.00")
    assert result["cashflow"]["refunds"] == Decimal("20.00")
    assert result["cashflow"]["expenses"] == Decimal("100.00")
    assert result["cashflow"]["debt_payments"] == Decimal("50.00")
    assert result["cashflow"]["asset_allocations"] == Decimal("30.00")
    assert result["cashflow"]["net"] == Decimal("220.00")
    food = next(
        row for row in result["category_changes"] if row["category"] == Category.FOOD.value
    )
    assert food["current"] == Decimal("100.00")
    assert food["current_count"] == 2


def test_recap_compares_merchant_net_spend(db_session: Session) -> None:
    db_session.add_all(
        [
            _tx(
                booking_date=PREVIOUS_DAY,
                merchant="Food Shop",
                category=Category.FOOD.value,
                amount=Decimal("-40.00"),
            ),
            _tx(
                booking_date=CURRENT_DAY,
                merchant="Food Shop",
                category=Category.FOOD.value,
                amount=Decimal("-100.00"),
            ),
            _tx(
                booking_date=CURRENT_DAY,
                merchant="Food Shop",
                category=Category.FOOD.value,
                direction=TransactionDirection.CREDIT.value,
                transaction_type=TransactionType.REFUND.value,
                amount=Decimal("20.00"),
            ),
        ]
    )
    db_session.commit()

    result = recap.period_recap(db_session, period="month", today=TODAY)

    merchant = result["merchant_changes"][0]
    assert merchant["current"] == Decimal("80.00")
    assert merchant["previous"] == Decimal("40.00")
    assert merchant["delta"] == Decimal("40.00")
    assert merchant["current_count"] == 2
    assert merchant["previous_count"] == 1


def test_recap_excludes_unconverted_foreign_amounts(db_session: Session) -> None:
    db_session.add_all(
        [
            _tx(
                booking_date=CURRENT_DAY,
                currency="USD",
                amount=Decimal("-100.00"),
                amount_base=None,
                category=Category.FOOD.value,
            ),
            _tx(
                booking_date=CURRENT_DAY,
                currency="EUR",
                amount=Decimal("-20.00"),
                amount_base=Decimal("-90.00"),
                base_currency="PLN",
                fx_rate=Decimal("4.50"),
                category=Category.TRANSPORT.value,
            ),
        ]
    )
    db_session.commit()

    result = recap.period_recap(db_session, period="month", today=TODAY)

    assert result["base_currency"] == "PLN"
    assert result["cashflow"]["expenses"] == Decimal("90.00")
    assert result["unconverted_count"] == 1
    categories = {row["category"] for row in result["category_changes"]}
    assert Category.FOOD.value not in categories
    assert Category.TRANSPORT.value in categories


def test_recap_week_window_excludes_old(db_session: Session) -> None:
    db_session.add_all(
        [
            _tx(booking_date=TODAY, category=Category.FOOD.value, amount=Decimal("-10.00")),
            # 20 days ago is outside both the current and previous 7-day windows
            _tx(
                booking_date=TODAY - timedelta(days=20),
                category=Category.FOOD.value,
                amount=Decimal("-99.00"),
            ),
        ]
    )
    db_session.commit()

    result = recap.period_recap(db_session, period="week", today=TODAY)

    assert result["current_from"] == date(2026, 2, 9)
    assert result["current_to"] == TODAY
    assert result["previous_from"] == date(2026, 2, 2)
    assert result["previous_to"] == date(2026, 2, 8)
    assert result["cashflow"]["expenses"] == Decimal("10.00")
