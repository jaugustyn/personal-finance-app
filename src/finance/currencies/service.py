"""Deterministic currency conversion for transaction amounts.

Transaction ``amount`` is always the original bank amount. Analytical totals use
``amount_base`` in the user's base currency. Foreign currencies without a known
rate raise ``MissingFxRate`` instead of silently falling back to ``1``.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from finance.currencies.providers import FxRateProvider, NbpFxRateProvider
from finance.domain.models import FxRate, Transaction, UserProfile

PROFILE_ID = 1
DEFAULT_BASE_CURRENCY = "PLN"
RATE_QUANT = Decimal("0.00000001")
AMOUNT_QUANT = Decimal("0.01")


class MissingFxRate(ValueError):
    """Raised when a non-base transaction cannot be converted."""

    def __init__(self, currency: str, base_currency: str, rate_date: date) -> None:
        self.currency = normalize_currency(currency)
        self.base_currency = normalize_currency(base_currency)
        self.rate_date = rate_date
        super().__init__(
            f"missing_fx_rate: {self.currency}/{self.base_currency} for {rate_date.isoformat()}"
        )


@dataclass(frozen=True)
class ConversionResult:
    amount_base: Decimal
    base_currency: str
    fx_rate: Decimal
    fx_rate_date: date
    fx_rate_source: str


def normalize_currency(value: str | None) -> str:
    code = (value or "").strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise ValueError(f"Invalid currency code: {value!r}")
    return code


def resolve_base_currency(session: Session) -> str:
    profile = session.get(UserProfile, PROFILE_ID)
    if profile is None:
        return DEFAULT_BASE_CURRENCY
    try:
        return normalize_currency(profile.base_currency)
    except ValueError:
        return DEFAULT_BASE_CURRENCY


def amount_base_expr() -> Any:
    """SQL expression for analytical amount in base currency.

    ``coalesce`` keeps old synthetic tests and manually inserted rows usable,
    while normal imports always populate ``amount_base``.
    """

    return func.coalesce(Transaction.amount_base, Transaction.amount)


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
    return session.execute(
        select(FxRate)
        .where(
            FxRate.currency == currency,
            FxRate.base_currency == base_currency,
            FxRate.rate_date <= rate_date,
        )
        .order_by(FxRate.rate_date.desc())
        .limit(1)
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
    base_currency: str | None = None,
    limit: int = 200,
) -> list[FxRate]:
    filters = []
    if currency:
        filters.append(FxRate.currency == normalize_currency(currency))
    if base_currency:
        filters.append(FxRate.base_currency == normalize_currency(base_currency))
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
    if base_currency != "PLN":
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
    base = normalize_currency(base_currency or resolve_base_currency(session))
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
        if _rate_on_or_before(
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
    base_currency = normalize_currency(base_currency or resolve_base_currency(session))
    if currency == base_currency:
        return ConversionResult(
            amount_base=_quant_amount(amount),
            base_currency=base_currency,
            fx_rate=Decimal("1.00000000"),
            fx_rate_date=rate_date,
            fx_rate_source="same_currency",
        )

    rate = _rate_on_or_before(
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
        .where(Transaction.currency != base_currency)
        .where((Transaction.amount_base.is_(None)) | (Transaction.fx_rate.is_(None)))
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
    base = normalize_currency(base_currency or resolve_base_currency(session))
    updated = 0
    missing = 0
    rows = session.execute(select(Transaction).order_by(Transaction.booking_date)).scalars()
    for tx in rows:
        try:
            converted = convert_amount(
                session,
                amount=Decimal(tx.amount),
                currency=str(tx.currency),
                rate_date=tx.booking_date,
                base_currency=base,
                allow_fetch=allow_fetch,
                provider=provider,
            )
        except MissingFxRate:
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
