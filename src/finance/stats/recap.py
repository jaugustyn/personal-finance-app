"""Deterministic comparison of a financial period with the preceding window."""
from __future__ import annotations

import calendar
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from finance.analytics.filters import (
    category_candidate_type_filter,
    expense_category_candidate_filters,
    non_transfer_filters,
    period_filters,
)
from finance.currencies import amount_base_expr, resolve_base_currency
from finance.domain.enums import TransactionDirection, TransactionType
from finance.domain.models import Transaction
from finance.transactions.merchants import (
    MerchantIdentityResolver,
    load_merchant_identity_resolver,
    merchant_display_label,
)
from finance.transactions.type_decision import effective_transaction_type_expr

PERIOD_WEEK = "week"
PERIOD_MONTH = "month"
DEFAULT_PERIOD = PERIOD_MONTH
DEFAULT_TOP_MERCHANTS = 5
DEFAULT_TOP_CHANGES = 5


@dataclass(frozen=True)
class PeriodBounds:
    start: date
    end: date


@dataclass(frozen=True)
class CategoryChange:
    category: str
    current: Decimal
    previous: Decimal
    delta: Decimal
    current_count: int
    previous_count: int
    change_percent: float | None


@dataclass(frozen=True)
class MerchantChange:
    merchant: str
    merchant_display: str
    merchant_canonical_key: str
    current: Decimal
    previous: Decimal
    delta: Decimal
    current_count: int
    previous_count: int
    change_percent: float | None


def _period_bounds(period: str, today: date) -> tuple[PeriodBounds, PeriodBounds]:
    """Return calendar-aligned current and comparable previous windows.

    Week means current ISO week from Monday through today and the same elapsed
    span in the previous week. Month means current calendar month from day 1
    through today compared with the same number of days in the previous month.
    """
    if period == PERIOD_WEEK:
        current_start = today - timedelta(days=today.weekday())
        current_end = today
        length = (current_end - current_start).days
        previous_start = current_start - timedelta(days=7)
        previous_end = previous_start + timedelta(days=length)
    else:
        current_start = today.replace(day=1)
        current_end = today
        previous_year = today.year if today.month > 1 else today.year - 1
        previous_month = today.month - 1 if today.month > 1 else 12
        previous_start = date(previous_year, previous_month, 1)
        previous_last_day = calendar.monthrange(previous_year, previous_month)[1]
        previous_end = date(
            previous_year,
            previous_month,
            min(today.day, previous_last_day),
        )
    return (
        PeriodBounds(current_start, current_end),
        PeriodBounds(previous_start, previous_end),
    )


def _expense_by_category(
    session: Session,
    bounds: PeriodBounds,
) -> dict[str, tuple[Decimal, int]]:
    base_amount = amount_base_expr()
    amount = func.coalesce(
        func.sum(
            case(
                (
                    Transaction.direction == TransactionDirection.CREDIT.value,
                    -func.abs(base_amount),
                ),
                else_=func.abs(base_amount),
            )
        ),
        0,
    )
    count = func.count(base_amount)
    rows = session.execute(
        select(Transaction.category, amount, count)
        .where(
            *period_filters(bounds.start, bounds.end),
            *non_transfer_filters(),
            category_candidate_type_filter(),
            Transaction.category.is_not(None),
        )
        .group_by(Transaction.category)
    ).all()
    return {
        row[0]: (Decimal(row[1] or 0), int(row[2] or 0))
        for row in rows
    }


def _cashflow(
    session: Session,
    bounds: PeriodBounds,
) -> dict[str, Decimal]:
    tx_type = effective_transaction_type_expr()
    base_amount = amount_base_expr()

    def typed_sum(
        types: list[str], direction: TransactionDirection
    ) -> Any:
        return func.coalesce(
            func.sum(
                case(
                    (
                        (Transaction.direction == direction.value)
                        & tx_type.in_(types),
                        func.abs(base_amount),
                    ),
                    else_=0,
                )
            ),
            0,
        )

    income = func.coalesce(
        func.sum(
            case(
                (
                    (Transaction.direction == TransactionDirection.CREDIT.value)
                    & tx_type.in_([
                        TransactionType.SALARY.value,
                        TransactionType.INCOME.value,
                    ]),
                    func.abs(base_amount),
                ),
                else_=0,
            )
        ),
        0,
    )
    gross_expenses = typed_sum(
        [TransactionType.EXPENSE.value], TransactionDirection.DEBIT
    )
    refunds = typed_sum(
        [TransactionType.REFUND.value], TransactionDirection.CREDIT
    )
    debt_payments = typed_sum(
        [TransactionType.DEBT_PAYMENT.value], TransactionDirection.DEBIT
    )
    asset_allocations = typed_sum(
        [TransactionType.ASSET_ALLOCATION.value], TransactionDirection.DEBIT
    )
    row = session.execute(
        select(
            income.label("inc"),
            gross_expenses.label("gross_expenses"),
            refunds.label("refunds"),
            debt_payments.label("debt_payments"),
            asset_allocations.label("asset_allocations"),
        ).where(
            *period_filters(bounds.start, bounds.end),
            *non_transfer_filters(),
        )
    ).one()
    inc = Decimal(row.inc or 0)
    gross = Decimal(row.gross_expenses or 0)
    refund = Decimal(row.refunds or 0)
    expenses = gross - refund
    debt = Decimal(row.debt_payments or 0)
    allocations = Decimal(row.asset_allocations or 0)
    return {
        "income": inc,
        "gross_expenses": gross,
        "refunds": refund,
        "expenses": expenses,
        "debt_payments": debt,
        "asset_allocations": allocations,
        "net": inc - expenses - debt - allocations,
    }


def cashflow_totals(
    session: Session,
    *,
    date_from: date,
    date_to: date,
) -> dict[str, Decimal]:
    """Return the shared economic cash-flow contract for an explicit period."""

    return _cashflow(session, PeriodBounds(date_from, date_to))


def _merchant_totals(
    session: Session,
    bounds: PeriodBounds,
    *,
    resolver: MerchantIdentityResolver,
) -> dict[str, dict[str, Any]]:
    base_amount = amount_base_expr()
    rows = session.execute(
        select(
            Transaction.merchant,
            Transaction.title,
            Transaction.direction,
            func.sum(func.abs(base_amount)).label("amount"),
            func.count(Transaction.id).label("count"),
        )
        .where(
            *expense_category_candidate_filters(),
            *period_filters(bounds.start, bounds.end),
            *non_transfer_filters(),
            base_amount.is_not(None),
        )
        .group_by(Transaction.merchant, Transaction.title, Transaction.direction)
    ).all()
    groups: dict[str, dict[str, Any]] = {}
    for merchant, title, direction, amount, count in rows:
        identity = resolver.resolve(merchant, title)
        if not identity.canonical_key:
            continue
        group = groups.setdefault(
            identity.canonical_key,
            {
                "amount": Decimal(0),
                "count": 0,
                "labels": {},
                "raw_labels": {},
                "merchant_canonical_key": identity.canonical_key,
            },
        )
        value = Decimal(amount or 0)
        if direction == TransactionDirection.CREDIT.value:
            value = -value
        row_count = int(count or 0)
        group["amount"] += value
        group["count"] += row_count
        label = identity.display_label or merchant_display_label(merchant, title)
        labels = group["labels"]
        label_stats = labels.setdefault(label, {"count": 0, "amount": Decimal(0)})
        label_stats["count"] += row_count
        label_stats["amount"] += value
        raw_label = merchant_display_label(merchant, title)
        raw_labels = group["raw_labels"]
        raw_stats = raw_labels.setdefault(
            raw_label,
            {"count": 0, "amount": Decimal(0)},
        )
        raw_stats["count"] += row_count
        raw_stats["amount"] += value

    for group in groups.values():
        label = max(
            group["labels"].items(),
            key=lambda item: (item[1]["count"], item[1]["amount"], item[0]),
        )[0]
        raw_label = max(
            group["raw_labels"].items(),
            key=lambda item: (item[1]["count"], item[1]["amount"], item[0]),
        )[0]
        group["merchant"] = raw_label
        group["merchant_display"] = label
    return groups


def _merchant_changes(
    current: dict[str, dict[str, Any]],
    previous: dict[str, dict[str, Any]],
    *,
    limit: int,
) -> list[MerchantChange]:
    changes: list[MerchantChange] = []
    for key in set(current) | set(previous):
        current_row = current.get(key, {})
        previous_row = previous.get(key, {})
        current_amount = Decimal(current_row.get("amount", 0))
        previous_amount = Decimal(previous_row.get("amount", 0))
        delta = current_amount - previous_amount
        if delta == 0:
            continue
        display_label = str(
            current_row.get("merchant_display")
            or previous_row.get("merchant_display")
            or key
        )
        merchant = str(current_row.get("merchant") or previous_row.get("merchant") or key)
        changes.append(
            MerchantChange(
                merchant=merchant,
                merchant_display=display_label,
                merchant_canonical_key=key,
                current=current_amount,
                previous=previous_amount,
                delta=delta,
                current_count=int(current_row.get("count", 0)),
                previous_count=int(previous_row.get("count", 0)),
                change_percent=_change_percent(current_amount, previous_amount),
            )
        )
    changes.sort(key=lambda row: (abs(row.delta), row.current_count), reverse=True)
    return changes[:limit]


def _category_changes(
    current: dict[str, tuple[Decimal, int]],
    previous: dict[str, tuple[Decimal, int]],
    *,
    limit: int,
) -> list[CategoryChange]:
    categories = set(current) | set(previous)
    changes: list[CategoryChange] = []
    for category in categories:
        current_amount, current_count = current.get(category, (Decimal(0), 0))
        previous_amount, previous_count = previous.get(category, (Decimal(0), 0))
        changes.append(
            CategoryChange(
                category=category,
                current=current_amount,
                previous=previous_amount,
                delta=current_amount - previous_amount,
                current_count=current_count,
                previous_count=previous_count,
                change_percent=_change_percent(current_amount, previous_amount),
            )
        )
    changes.sort(key=lambda c: abs(c.delta), reverse=True)
    return [c for c in changes if c.delta != 0][:limit]


def _change_percent(current: Decimal, previous: Decimal) -> float | None:
    if previous == 0:
        return None
    return float((current - previous) / abs(previous) * 100)


def _unconverted_count(
    session: Session,
    bounds: PeriodBounds,
) -> int:
    tx_type = effective_transaction_type_expr()
    relevant_types = [
        TransactionType.SALARY.value,
        TransactionType.INCOME.value,
        TransactionType.EXPENSE.value,
        TransactionType.REFUND.value,
        TransactionType.DEBT_PAYMENT.value,
        TransactionType.ASSET_ALLOCATION.value,
    ]
    return int(
        session.scalar(
            select(func.count(Transaction.id)).where(
                *period_filters(bounds.start, bounds.end),
                *non_transfer_filters(),
                tx_type.in_(relevant_types),
                amount_base_expr().is_(None),
            )
        )
        or 0
    )


def _compute_recap(
    session: Session,
    period: str,
    current_bounds: PeriodBounds,
    previous_bounds: PeriodBounds,
    top_merchants: int,
    top_changes: int,
) -> dict[str, Any]:
    """Shared computation logic for both period-based and custom recap."""
    base_currency = resolve_base_currency(session)
    current_cashflow = _cashflow(session, current_bounds)
    previous_cashflow = _cashflow(session, previous_bounds)
    current_expense = _expense_by_category(session, current_bounds)
    previous_expense = _expense_by_category(session, previous_bounds)

    changes = _category_changes(current_expense, previous_expense, limit=top_changes)
    merchant_resolver = load_merchant_identity_resolver(session)
    current_merchants = _merchant_totals(
        session,
        current_bounds,
        resolver=merchant_resolver,
    )
    previous_merchants = _merchant_totals(
        session,
        previous_bounds,
        resolver=merchant_resolver,
    )
    merchant_changes = _merchant_changes(
        current_merchants,
        previous_merchants,
        limit=top_merchants,
    )

    return {
        "period": period,
        "base_currency": base_currency,
        "current_from": current_bounds.start,
        "current_to": current_bounds.end,
        "previous_from": previous_bounds.start,
        "previous_to": previous_bounds.end,
        "cashflow": {
            **current_cashflow,
            **{
                f"{key}_delta": current_cashflow[key] - previous_cashflow[key]
                for key in current_cashflow
            },
        },
        "category_changes": [asdict(c) for c in changes],
        "merchant_changes": [asdict(m) for m in merchant_changes],
        "unconverted_count": sum(
            _unconverted_count(session, bounds)
            for bounds in (current_bounds, previous_bounds)
        ),
    }


def period_recap(
    session: Session,
    *,
    period: str = DEFAULT_PERIOD,
    today: date | None = None,
    top_merchants: int = DEFAULT_TOP_MERCHANTS,
    top_changes: int = DEFAULT_TOP_CHANGES,
) -> dict[str, Any]:
    """Compute a deterministic recap for the current calendar week or month."""
    period = period if period in (PERIOD_WEEK, PERIOD_MONTH) else DEFAULT_PERIOD
    today = today or date.today()
    current_bounds, previous_bounds = _period_bounds(period, today)
    return _compute_recap(
        session, period, current_bounds, previous_bounds, top_merchants, top_changes
    )


def custom_recap(
    session: Session,
    *,
    date_from: date,
    date_to: date,
    top_merchants: int = DEFAULT_TOP_MERCHANTS,
    top_changes: int = DEFAULT_TOP_CHANGES,
) -> dict[str, Any]:
    """Recap for an explicit date range; previous period is an equal-length window before."""
    current_bounds = PeriodBounds(date_from, date_to)
    length = max((date_to - date_from).days, 0)
    prev_end = date_from - timedelta(days=1)
    prev_start = prev_end - timedelta(days=length)
    previous_bounds = PeriodBounds(prev_start, prev_end)
    return _compute_recap(
        session, "custom", current_bounds, previous_bounds, top_merchants, top_changes
    )
