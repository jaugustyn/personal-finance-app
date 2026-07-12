"""Tests for the deterministic period recap aggregations."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from finance.domain.enums import Category, TransactionDirection, TransactionType
from finance.domain.models import Transaction, UserProfile
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
            # previous window: spend 40 food
            _tx(booking_date=PREVIOUS_DAY, category=Category.FOOD.value, amount=Decimal("-40.00")),
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
    assert result["previous_to"] == date(2026, 1, 31)
    assert result["cashflow"]["income"] == Decimal("500.00")
    assert result["cashflow"]["income_delta"] == Decimal("-200.00")
    assert result["cashflow"]["expenses"] == Decimal("130.00")
    assert result["cashflow"]["expenses_delta"] == Decimal("90.00")
    assert result["cashflow"]["net"] == Decimal("370.00")
    assert result["cashflow"]["net_delta"] == Decimal("-290.00")
    # food rose from 40 -> 100 => delta 60, transport new => 30
    changes = {c["category"]: c["delta"] for c in result["category_changes"]}
    assert changes[Category.FOOD.value] == Decimal("60.00")
    assert changes[Category.TRANSPORT.value] == Decimal("30.00")
    # food is the largest mover
    assert result["category_changes"][0]["category"] == Category.FOOD.value


def test_recap_limit_breach_and_savings(db_session: Session) -> None:
    db_session.add(
        UserProfile(
            id=1,
            monthly_savings_goal=Decimal("200.00"),
            category_limits={Category.FOOD.value: 50.0},
        )
    )
    db_session.add_all(
        [
            _tx(booking_date=CURRENT_DAY, category=Category.FOOD.value, amount=Decimal("-120.00")),
            _tx(
                booking_date=CURRENT_DAY,
                direction=TransactionDirection.CREDIT.value,
                amount=Decimal("400.00"),
            ),
        ]
    )
    db_session.commit()

    result = recap.period_recap(db_session, period="month", today=TODAY)

    breaches = {b["category"]: b for b in result["limit_breaches"]}
    assert breaches[Category.FOOD.value]["overshoot"] == Decimal("70.00")
    assert result["savings_progress"] is not None
    assert result["savings_progress"]["met"] is True
    assert result["savings_progress"]["net"] == Decimal("280.00")


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
