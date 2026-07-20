"""Deterministic currency conversion for transaction amounts.

Transaction ``amount`` is always the original bank amount. Analytical totals use
PLN and accept a foreign ``amount_base`` only with complete conversion metadata.
Foreign currencies without a known rate raise ``MissingFxRate`` instead of
silently falling back to ``1``.
"""
from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from finance.currencies.providers import (
    NBP_LOOKBACK_DAYS,
    FxRateProvider,
    NbpFxRateProvider,
)
from finance.currencies.types import ConversionResult, MissingFxRate
from finance.domain.models import FxRate, Transaction

BASE_CURRENCY = "PLN"
RATE_QUANT = Decimal("0.00000001")
AMOUNT_QUANT = Decimal("0.01")


def normalize_currency(value: str | None) -> str:
    code = (value or "").strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise ValueError(f"Invalid currency code: {value!r}")
    return code


def resolve_base_currency(session: Session | None = None) -> str:
    """Return the single analytical currency supported by the application.

    The optional session argument is retained for existing callers, but the
    runtime no longer reads the value from the user profile.
    """

    del session
    return BASE_CURRENCY


def amount_base_expr() -> Any:
    """Return a safe SQL amount in PLN, or NULL when conversion is invalid."""

    return amount_base_fields_expr(
        currency=Transaction.currency,
        amount=Transaction.amount,
        amount_base=Transaction.amount_base,
        base_currency=Transaction.base_currency,
        fx_rate=Transaction.fx_rate,
    )


def amount_base_fields_expr(
    *,
    currency: Any,
    amount: Any,
    amount_base: Any,
    base_currency: Any,
    fx_rate: Any,
) -> Any:
    """Build the safe PLN expression for table aliases and subqueries."""

    return case(
        (func.upper(currency) == BASE_CURRENCY, amount),
        (
            and_(
                func.upper(base_currency) == BASE_CURRENCY,
                amount_base.is_not(None),
                fx_rate.is_not(None),
                fx_rate > 0,
            ),
            amount_base,
        ),
        else_=None,
    )


def amount_base_value(transaction: Transaction) -> Decimal | None:
    """Return a safe in-memory amount in PLN using the SQL policy above."""

    currency = str(transaction.currency or "").strip().upper()
    if currency == BASE_CURRENCY:
        return Decimal(transaction.amount)
    base_currency = str(transaction.base_currency or "").strip().upper()
    if (
        base_currency != BASE_CURRENCY
        or transaction.amount_base is None
        or transaction.fx_rate is None
        or Decimal(transaction.fx_rate) <= 0
    ):
        return None
    return Decimal(transaction.amount_base)


def _quant_rate(value: Decimal) -> Decimal:
    return Decimal(value).quantize(RATE_QUANT, rounding=ROUND_HALF_UP)


def _quant_amount(value: Decimal) -> Decimal:
    return Decimal(value).quantize(AMOUNT_QUANT, rounding=ROUND_HALF_UP)


def _rate_on_or_before(
    session: Session,
    *,
    currency: str,
    base_currency: str,
    rate_date: date,
) -> FxRate | None:
    earliest_date = rate_date - timedelta(days=NBP_LOOKBACK_DAYS)
    return session.execute(
        select(FxRate)
        .where(
            FxRate.currency == currency,
            FxRate.base_currency == base_currency,
            FxRate.rate_date <= rate_date,
            FxRate.rate_date >= earliest_date,
        )
        .order_by(FxRate.rate_date.desc())
        .limit(1)
    ).scalar_one_or_none()


def _rate_on_date(
    session: Session,
    *,
    currency: str,
    base_currency: str,
    rate_date: date,
) -> FxRate | None:
    """Return a rate stored for the exact effective date."""
    return session.execute(
        select(FxRate).where(
            FxRate.currency == currency,
            FxRate.base_currency == base_currency,
            FxRate.rate_date == rate_date,
        )
    ).scalar_one_or_none()


def add_manual_rate(
    session: Session,
    *,
    currency: str,
    base_currency: str,
    rate_date: date,
    rate: Decimal,
    source: str = "manual",
) -> FxRate:
    currency = normalize_currency(currency)
    base_currency = normalize_currency(base_currency)
    if base_currency != BASE_CURRENCY:
        raise ValueError(f"Base currency must be {BASE_CURRENCY}.")
    if currency == BASE_CURRENCY:
        raise ValueError(f"A manual rate for {BASE_CURRENCY}/{BASE_CURRENCY} is not allowed.")
    rate = _quant_rate(rate)
    if rate <= 0:
        raise ValueError("FX rate must be positive.")
    existing = session.execute(
        select(FxRate).where(
            FxRate.currency == currency,
            FxRate.base_currency == base_currency,
            FxRate.rate_date == rate_date,
        )
    ).scalar_one_or_none()
    if existing is None:
        existing = FxRate(
            currency=currency,
            base_currency=base_currency,
            rate_date=rate_date,
            rate=rate,
            source=source,
        )
        session.add(existing)
    else:
        existing.rate = rate
        existing.source = source
    session.flush()
    return existing


def list_rates(
    session: Session,
    *,
    currency: str | None = None,
    limit: int = 200,
) -> list[FxRate]:
    filters = [FxRate.base_currency == BASE_CURRENCY]
    if currency:
        filters.append(FxRate.currency == normalize_currency(currency))
    return list(
        session.execute(
            select(FxRate)
            .where(*filters)
            .order_by(FxRate.rate_date.desc(), FxRate.currency)
            .limit(limit)
        ).scalars()
    )


def ensure_nbp_rate(
    session: Session,
    *,
    currency: str,
    base_currency: str,
    rate_date: date,
    provider: FxRateProvider | None = None,
) -> FxRate | None:
    currency = normalize_currency(currency)
    base_currency = normalize_currency(base_currency)
    if base_currency != BASE_CURRENCY:
        return None
    fetched = (provider or NbpFxRateProvider()).fetch_rate(currency, rate_date)
    if fetched is None:
        return None
    rate, effective_date = fetched
    return add_manual_rate(
        session,
        currency=currency,
        base_currency=base_currency,
        rate_date=effective_date,
        rate=rate,
        source="nbp",
    )


def prefetch_nbp_rates(
    session: Session,
    *,
    rate_requests: Iterable[tuple[str, date]],
    base_currency: str | None = None,
    provider: FxRateProvider | None = None,
) -> dict[str, int]:
    """Fetch missing NBP rates for unique currency/date requests without committing."""
    base = normalize_currency(base_currency or BASE_CURRENCY)
    if base != BASE_CURRENCY:
        raise ValueError(f"Base currency must be {BASE_CURRENCY}.")
    existing = 0
    fetched = 0
    missing = 0
    unique_requests = sorted(
        {
            (normalize_currency(currency), rate_date)
            for currency, rate_date in rate_requests
            if normalize_currency(currency) != base
        },
        key=lambda item: (item[1], item[0]),
    )
    for currency, rate_date in unique_requests:
        # A historical rate may be used as a weekend/holiday fallback, but it
        # must not suppress fetching a distinct rate requested for a later day.
        if _rate_on_date(
            session,
            currency=currency,
            base_currency=base,
            rate_date=rate_date,
        ):
            existing += 1
            continue
        rate = ensure_nbp_rate(
            session,
            currency=currency,
            base_currency=base,
            rate_date=rate_date,
            provider=provider,
        )
        if rate is None:
            missing += 1
        else:
            fetched += 1
    return {"existing": existing, "fetched": fetched, "missing": missing}


def convert_amount(
    session: Session,
    *,
    amount: Decimal,
    currency: str,
    rate_date: date,
    base_currency: str | None = None,
    allow_fetch: bool = True,
    provider: FxRateProvider | None = None,
) -> ConversionResult:
    currency = normalize_currency(currency)
    base_currency = normalize_currency(base_currency or BASE_CURRENCY)
    if base_currency != BASE_CURRENCY:
        raise ValueError(f"Base currency must be {BASE_CURRENCY}.")
    if currency == base_currency:
        return ConversionResult(
            amount_base=_quant_amount(amount),
            base_currency=base_currency,
            fx_rate=Decimal("1.00000000"),
            fx_rate_date=rate_date,
            fx_rate_source="same_currency",
        )

    rate = _rate_on_date(
        session,
        currency=currency,
        base_currency=base_currency,
        rate_date=rate_date,
    )
    if rate is None and allow_fetch:
        rate = ensure_nbp_rate(
            session,
            currency=currency,
            base_currency=base_currency,
            rate_date=rate_date,
            provider=provider,
        )
    if rate is None:
        # NBP has no table for weekends and holidays. Only after checking or
        # fetching the requested date do we fall back to the latest prior rate.
        rate = _rate_on_or_before(
            session,
            currency=currency,
            base_currency=base_currency,
            rate_date=rate_date,
        )
    if rate is None:
        raise MissingFxRate(currency, base_currency, rate_date)
    return ConversionResult(
        amount_base=_quant_amount(Decimal(amount) * Decimal(rate.rate)),
        base_currency=base_currency,
        fx_rate=_quant_rate(Decimal(rate.rate)),
        fx_rate_date=rate.rate_date,
        fx_rate_source=rate.source,
    )


def _missing_rate_rows(session: Session, base_currency: str) -> list[dict[str, Any]]:
    rows = session.execute(
        select(
            Transaction.currency,
            Transaction.booking_date,
            func.count().label("count"),
        )
        .where(func.upper(Transaction.currency) != base_currency)
        .where(
            or_(
                Transaction.amount_base.is_(None),
                Transaction.base_currency.is_(None),
                func.upper(Transaction.base_currency) != base_currency,
                Transaction.fx_rate.is_(None),
                Transaction.fx_rate <= 0,
            )
        )
        .group_by(Transaction.currency, Transaction.booking_date)
        .order_by(Transaction.booking_date.desc(), Transaction.currency)
    ).mappings().all()
    return [
        {
            "currency": row["currency"],
            "base_currency": base_currency,
            "rate_date": row["booking_date"],
            "count": int(row["count"] or 0),
        }
        for row in rows
    ]


def status(session: Session) -> dict[str, Any]:
    base_currency = resolve_base_currency(session)
    currency_rows = session.execute(
        select(
            Transaction.currency,
            func.count().label("count"),
            func.coalesce(
                func.sum(
                    case(
                        (Transaction.direction == "credit", func.abs(Transaction.amount)),
                        else_=0,
                    )
                ),
                0,
            ).label("income"),
            func.coalesce(
                func.sum(
                    case(
                        (Transaction.direction == "debit", func.abs(Transaction.amount)),
                        else_=0,
                    )
                ),
                0,
            ).label("expenses"),
        )
        .group_by(Transaction.currency)
        .order_by(Transaction.currency)
    ).mappings().all()
    currencies = [
        {
            "currency": row["currency"],
            "count": int(row["count"] or 0),
            "total_income": Decimal(row["income"] or 0),
            "total_expenses": Decimal(row["expenses"] or 0),
            "net": Decimal(row["income"] or 0) - Decimal(row["expenses"] or 0),
        }
        for row in currency_rows
    ]
    missing = _missing_rate_rows(session, base_currency)
    return {
        "base_currency": base_currency,
        "currencies": currencies,
        "missing_rates": missing,
        "missing_rate_count": sum(int(row["count"]) for row in missing),
    }


def recompute_transactions(
    session: Session,
    *,
    base_currency: str | None = None,
    allow_fetch: bool = True,
    provider: FxRateProvider | None = None,
) -> dict[str, int]:
    base = normalize_currency(base_currency or BASE_CURRENCY)
    if base != BASE_CURRENCY:
        raise ValueError(f"Base currency must be {BASE_CURRENCY}.")
    updated = 0
    missing = 0
    rows = list(
        session.execute(select(Transaction).order_by(Transaction.booking_date)).scalars()
    )
    if allow_fetch:
        prefetch_nbp_rates(
            session,
            rate_requests=[(str(tx.currency), tx.booking_date) for tx in rows],
            base_currency=base,
            provider=provider,
        )
    for tx in rows:
        try:
            converted = convert_amount(
                session,
                amount=Decimal(tx.amount),
                currency=str(tx.currency),
                rate_date=tx.booking_date,
                base_currency=base,
                allow_fetch=False,
            )
        except MissingFxRate:
            tx.amount_base = None
            tx.base_currency = None
            tx.fx_rate = None
            tx.fx_rate_date = None
            tx.fx_rate_source = None
            missing += 1
            continue
        tx.amount_base = converted.amount_base
        tx.base_currency = converted.base_currency
        tx.fx_rate = converted.fx_rate
        tx.fx_rate_date = converted.fx_rate_date
        tx.fx_rate_source = converted.fx_rate_source
        updated += 1
    session.commit()
    return {"updated": updated, "missing": missing}


def fetch_nbp_rates_for_missing_transactions(
    session: Session,
    *,
    provider: FxRateProvider | None = None,
) -> dict[str, int]:
    base = resolve_base_currency(session)
    fetched = 0
    missing = 0
    for row in _missing_rate_rows(session, base):
        rate = ensure_nbp_rate(
            session,
            currency=str(row["currency"]),
            base_currency=base,
            rate_date=row["rate_date"],
            provider=provider,
        )
        if rate is None:
            missing += 1
        else:
            fetched += 1
    session.commit()
    return {"fetched": fetched, "missing": missing}
