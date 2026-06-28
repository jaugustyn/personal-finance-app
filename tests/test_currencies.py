from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from finance.currencies import (
    MissingFxRate,
    add_manual_rate,
    convert_amount,
    recompute_transactions,
)
from finance.domain.models import Transaction


def test_same_currency_converts_with_rate_one(db_session: Session) -> None:
    result = convert_amount(
        db_session,
        amount=Decimal("-12.34"),
        currency="PLN",
        base_currency="PLN",
        rate_date=date(2026, 1, 10),
    )

    assert result.amount_base == Decimal("-12.34")
    assert result.fx_rate == Decimal("1.00000000")
    assert result.fx_rate_source == "same_currency"


def test_manual_rate_converts_to_base_currency(db_session: Session) -> None:
    add_manual_rate(
        db_session,
        currency="USD",
        base_currency="PLN",
        rate_date=date(2026, 1, 10),
        rate=Decimal("4.0000"),
    )
    db_session.commit()

    result = convert_amount(
        db_session,
        amount=Decimal("-10.00"),
        currency="USD",
        base_currency="PLN",
        rate_date=date(2026, 1, 10),
        allow_fetch=False,
    )

    assert result.amount_base == Decimal("-40.00")
    assert result.fx_rate == Decimal("4.00000000")
    assert result.fx_rate_source == "manual"


def test_missing_foreign_rate_blocks_conversion(db_session: Session) -> None:
    with pytest.raises(MissingFxRate):
        convert_amount(
            db_session,
            amount=Decimal("10.00"),
            currency="USD",
            base_currency="PLN",
            rate_date=date(2026, 1, 10),
            allow_fetch=False,
        )


def test_recompute_transactions_updates_base_amounts(db_session: Session) -> None:
    add_manual_rate(
        db_session,
        currency="USD",
        base_currency="PLN",
        rate_date=date(2026, 1, 10),
        rate=Decimal("4.0000"),
    )
    db_session.add(
        Transaction(
            booking_date=date(2026, 1, 10),
            amount=Decimal("-10.00"),
            currency="USD",
            direction="debit",
            merchant="Foreign Shop",
            title="",
            category=None,
            category_predicted=None,
            source="unknown",
            dedup_hash="currency-recompute-usd",
            is_transfer=False,
        )
    )
    db_session.commit()

    result = recompute_transactions(
        db_session,
        base_currency="PLN",
        allow_fetch=False,
    )

    tx = db_session.query(Transaction).one()
    assert result == {"updated": 1, "missing": 0}
    assert tx.amount_base == Decimal("-40.00")
    assert tx.base_currency == "PLN"
    assert tx.fx_rate_source == "manual"
