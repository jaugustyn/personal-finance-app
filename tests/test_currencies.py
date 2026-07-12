from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from finance.currencies import (
    MissingFxRate,
    add_manual_rate,
    convert_amount,
    prefetch_nbp_rates,
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


class _StaticRateProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[str, date]] = []

    def fetch_rate(self, currency: str, rate_date: date):
        self.calls.append((currency, rate_date))
        return Decimal("4.2500"), rate_date


class _DailyRateProvider:
    def __init__(self, rates: dict[date, Decimal]) -> None:
        self.rates = rates
        self.calls: list[tuple[str, date]] = []

    def fetch_rate(self, currency: str, rate_date: date):
        self.calls.append((currency, rate_date))
        rate = self.rates.get(rate_date)
        return (rate, rate_date) if rate is not None else None


class _PreviousBusinessDayProvider:
    def __init__(self, rate: Decimal, effective_date: date) -> None:
        self.rate = rate
        self.effective_date = effective_date
        self.calls: list[tuple[str, date]] = []

    def fetch_rate(self, currency: str, rate_date: date):
        self.calls.append((currency, rate_date))
        return self.rate, self.effective_date


def test_prefetch_uses_injected_provider_without_conversion_fetch(
    db_session: Session,
) -> None:
    provider = _StaticRateProvider()

    result = prefetch_nbp_rates(
        db_session,
        rate_requests=[("USD", date(2026, 1, 10)), ("USD", date(2026, 1, 10))],
        base_currency="PLN",
        provider=provider,
    )

    converted = convert_amount(
        db_session,
        amount=Decimal("-10.00"),
        currency="USD",
        base_currency="PLN",
        rate_date=date(2026, 1, 10),
        allow_fetch=False,
    )
    assert result == {"existing": 0, "fetched": 1, "missing": 0}
    assert provider.calls == [("USD", date(2026, 1, 10))]
    assert converted.amount_base == Decimal("-42.50")
    assert converted.fx_rate_source == "nbp"


def test_prefetch_fetches_each_requested_day_even_when_older_rate_exists(
    db_session: Session,
) -> None:
    first_day = date(2026, 1, 8)
    second_day = date(2026, 1, 9)
    provider = _DailyRateProvider(
        {
            first_day: Decimal("4.0000"),
            second_day: Decimal("4.2000"),
        }
    )

    result = prefetch_nbp_rates(
        db_session,
        rate_requests=[("USD", first_day), ("USD", second_day)],
        base_currency="PLN",
        provider=provider,
    )

    first = convert_amount(
        db_session,
        amount=Decimal("-10"),
        currency="USD",
        base_currency="PLN",
        rate_date=first_day,
        allow_fetch=False,
    )
    second = convert_amount(
        db_session,
        amount=Decimal("-10"),
        currency="USD",
        base_currency="PLN",
        rate_date=second_day,
        allow_fetch=False,
    )
    assert result == {"existing": 0, "fetched": 2, "missing": 0}
    assert provider.calls == [("USD", first_day), ("USD", second_day)]
    assert first.amount_base == Decimal("-40.00")
    assert second.amount_base == Decimal("-42.00")
    assert first.fx_rate_date == first_day
    assert second.fx_rate_date == second_day


def test_conversion_fetches_requested_day_before_using_older_fallback(
    db_session: Session,
) -> None:
    first_day = date(2026, 1, 8)
    second_day = date(2026, 1, 9)
    add_manual_rate(
        db_session,
        currency="USD",
        base_currency="PLN",
        rate_date=first_day,
        rate=Decimal("4.0000"),
    )
    provider = _DailyRateProvider({second_day: Decimal("4.2000")})

    converted = convert_amount(
        db_session,
        amount=Decimal("-10"),
        currency="USD",
        base_currency="PLN",
        rate_date=second_day,
        provider=provider,
    )

    assert provider.calls == [("USD", second_day)]
    assert converted.amount_base == Decimal("-42.00")
    assert converted.fx_rate_date == second_day
    assert converted.fx_rate_source == "nbp"


def test_conversion_uses_recent_effective_date_for_weekend(
    db_session: Session,
) -> None:
    friday = date(2026, 1, 9)
    sunday = date(2026, 1, 11)
    provider = _PreviousBusinessDayProvider(Decimal("4.1000"), friday)

    converted = convert_amount(
        db_session,
        amount=Decimal("-10"),
        currency="USD",
        base_currency="PLN",
        rate_date=sunday,
        provider=provider,
    )

    assert provider.calls == [("USD", sunday)]
    assert converted.amount_base == Decimal("-41.00")
    assert converted.fx_rate_date == friday
    assert converted.fx_rate_source == "nbp"


def test_conversion_does_not_use_stale_rate_as_date_fallback(
    db_session: Session,
) -> None:
    add_manual_rate(
        db_session,
        currency="USD",
        base_currency="PLN",
        rate_date=date(2026, 1, 1),
        rate=Decimal("4.0000"),
    )

    with pytest.raises(MissingFxRate):
        convert_amount(
            db_session,
            amount=Decimal("-10"),
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


def test_recompute_fetches_distinct_rates_for_distinct_booking_dates(
    db_session: Session,
) -> None:
    first_day = date(2026, 1, 8)
    second_day = date(2026, 1, 9)
    provider = _DailyRateProvider(
        {
            first_day: Decimal("4.0000"),
            second_day: Decimal("4.2000"),
        }
    )
    for index, booking_date in enumerate((first_day, second_day), start=1):
        db_session.add(
            Transaction(
                booking_date=booking_date,
                amount=Decimal("-10.00"),
                currency="USD",
                direction="debit",
                merchant=f"Foreign Shop {index}",
                title="",
                source="unknown",
                dedup_hash=f"currency-recompute-daily-{index}",
                is_transfer=False,
            )
        )
    db_session.commit()

    result = recompute_transactions(
        db_session,
        base_currency="PLN",
        provider=provider,
    )

    rows = db_session.query(Transaction).order_by(Transaction.booking_date).all()
    assert result == {"updated": 2, "missing": 0}
    assert provider.calls == [("USD", first_day), ("USD", second_day)]
    assert [row.amount_base for row in rows] == [Decimal("-40.00"), Decimal("-42.00")]
    assert [row.fx_rate_date for row in rows] == [first_day, second_day]
