"""Deterministic currency conversion for transaction amounts.

Transaction ``amount`` is always the original bank amount. Analytical totals use
``amount_base`` in the user's base currency. Foreign currencies without a known
rate raise ``MissingFxRate`` instead of silently falling back to ``1``.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from finance.domain.models import FxRate, Transaction, UserProfile

PROFILE_ID = 1
DEFAULT_BASE_CURRENCY = "PLN"
RATE_QUANT = Decimal("0.00000001")
AMOUNT_QUANT = Decimal("0.01")
NBP_LOOKBACK_DAYS = 7


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


def _fetch_nbp_rate(currency: str, rate_date: date) -> tuple[Decimal, date] | None:
    if currency == "PLN":
        return Decimal("1"), rate_date
    for table in ("a", "b"):
        for offset in range(NBP_LOOKBACK_DAYS + 1):
            day = rate_date - timedelta(days=offset)
            url = (
                "https://api.nbp.pl/api/exchangerates/rates/"
                f"{table}/{currency}/{day.isoformat()}/?format=json"
            )
            try:
                with urllib.request.urlopen(url, timeout=5) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    continue
                return None
            except Exception:  # noqa: BLE001
                return None
            rates = payload.get("rates") if isinstance(payload, dict) else None
            if not rates:
                continue
            rate = Decimal(str(rates[0]["mid"]))
            effective_date = date.fromisoformat(str(rates[0]["effectiveDate"]))
            return rate, effective_date
    return None


def ensure_nbp_rate(
    session: Session,
    *,
    currency: str,
    base_currency: str,
    rate_date: date,
) -> FxRate | None:
    currency = normalize_currency(currency)
    base_currency = normalize_currency(base_currency)
    if base_currency != "PLN":
        return None
    fetched = _fetch_nbp_rate(currency, rate_date)
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


def convert_amount(
    session: Session,
    *,
    amount: Decimal,
    currency: str,
    rate_date: date,
    base_currency: str | None = None,
    allow_fetch: bool = True,
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
    ).all()
    return [
        {
            "currency": row.currency,
            "base_currency": base_currency,
            "rate_date": row.booking_date,
            "count": int(row.count or 0),
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
    ).all()
    currencies = [
        {
            "currency": row.currency,
            "count": int(row.count or 0),
            "total_income": Decimal(row.income or 0),
            "total_expenses": Decimal(row.expenses or 0),
            "net": Decimal(row.income or 0) - Decimal(row.expenses or 0),
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


def fetch_nbp_rates_for_missing_transactions(session: Session) -> dict[str, int]:
    base = resolve_base_currency(session)
    fetched = 0
    missing = 0
    for row in _missing_rate_rows(session, base):
        rate = ensure_nbp_rate(
            session,
            currency=str(row["currency"]),
            base_currency=base,
            rate_date=row["rate_date"],
        )
        if rate is None:
            missing += 1
        else:
            fetched += 1
    session.commit()
    return {"fetched": fetched, "missing": missing}
