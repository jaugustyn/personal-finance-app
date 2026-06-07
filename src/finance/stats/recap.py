"""Deterministic period recap: compares a calendar window to the previous one.

Surfaces the headline cashflow change, the biggest category movements, the top
merchants and any category-limit breaches / savings-goal progress for the most
current week or month. All numbers are computed here from the database; the LLM
assistant may only describe these results, never invent them.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import calendar
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from finance.analytics.filters import (
    category_candidate_type_filter,
    non_transfer_filters,
    period_filters,
)
from finance.domain.models import Transaction, UserProfile

PERIOD_WEEK = "week"
PERIOD_MONTH = "month"
DEFAULT_PERIOD = PERIOD_MONTH
DEFAULT_TOP_MERCHANTS = 5
DEFAULT_TOP_CHANGES = 5
PROFILE_ID = 1


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


@dataclass(frozen=True)
class MerchantSpend:
    merchant: str
    amount: Decimal
    count: int


@dataclass(frozen=True)
class LimitBreach:
    category: str
    spent: Decimal
    limit: Decimal
    overshoot: Decimal


def _period_bounds(period: str, today: date) -> tuple[PeriodBounds, PeriodBounds]:
    """Return calendar-aligned current and comparable previous windows.

    Week means current ISO week from Monday through today and the same elapsed
    span in the previous week. Month means current calendar month from day 1
    through today compared with the full previous calendar month.
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
        previous_end = date(previous_year, previous_month, previous_last_day)
    return (
        PeriodBounds(current_start, current_end),
        PeriodBounds(previous_start, previous_end),
    )


def _expense_by_category(
    session: Session, bounds: PeriodBounds
) -> dict[str, Decimal]:
    amount = func.coalesce(func.sum(func.abs(Transaction.amount)), 0)
    rows = session.execute(
        select(Transaction.category, amount)
        .where(
            Transaction.direction == "debit",
            *period_filters(bounds.start, bounds.end),
            *non_transfer_filters(),
            category_candidate_type_filter(),
            Transaction.category.is_not(None),
        )
        .group_by(Transaction.category)
    ).all()
    return {row[0]: Decimal(row[1] or 0) for row in rows}


def _cashflow(session: Session, bounds: PeriodBounds) -> dict[str, Decimal]:
    income = func.coalesce(
        func.sum(
            case((Transaction.direction == "credit", func.abs(Transaction.amount)), else_=0)
        ),
        0,
    )
    expense = func.coalesce(
        func.sum(
            case((Transaction.direction == "debit", func.abs(Transaction.amount)), else_=0)
        ),
        0,
    )
    row = session.execute(
        select(income.label("inc"), expense.label("exp")).where(
            *period_filters(bounds.start, bounds.end),
            *non_transfer_filters(),
        )
    ).one()
    inc = Decimal(row.inc or 0)
    exp = Decimal(row.exp or 0)
    return {"income": inc, "expenses": exp, "net": inc - exp}


def _top_merchants(
    session: Session, bounds: PeriodBounds, *, limit: int
) -> list[MerchantSpend]:
    amount = func.coalesce(func.sum(func.abs(Transaction.amount)), 0).label("amount")
    count = func.count().label("cnt")
    rows = session.execute(
        select(Transaction.merchant, amount, count)
        .where(
            Transaction.direction == "debit",
            *period_filters(bounds.start, bounds.end),
            *non_transfer_filters(),
            Transaction.merchant != "",
        )
        .group_by(Transaction.merchant)
        .order_by(amount.desc())
        .limit(limit)
    ).all()
    return [
        MerchantSpend(merchant=row.merchant, amount=Decimal(row.amount or 0), count=int(row.cnt))
        for row in rows
    ]


def _category_changes(
    current: dict[str, Decimal],
    previous: dict[str, Decimal],
    *,
    limit: int,
) -> list[CategoryChange]:
    categories = set(current) | set(previous)
    changes = [
        CategoryChange(
            category=cat,
            current=current.get(cat, Decimal(0)),
            previous=previous.get(cat, Decimal(0)),
            delta=current.get(cat, Decimal(0)) - previous.get(cat, Decimal(0)),
        )
        for cat in categories
    ]
    changes.sort(key=lambda c: abs(c.delta), reverse=True)
    return [c for c in changes if c.delta != 0][:limit]


def _limit_breaches(
    session: Session,
    bounds: PeriodBounds,
    current_expense: dict[str, Decimal],
) -> list[LimitBreach]:
    profile = session.get(UserProfile, PROFILE_ID)
    limits = (profile.category_limits or {}) if profile is not None else {}
    breaches: list[LimitBreach] = []
    for category, raw_limit in limits.items():
        limit = Decimal(str(raw_limit))
        if limit <= 0:
            continue
        spent = current_expense.get(category, Decimal(0))
        if spent > limit:
            breaches.append(
                LimitBreach(
                    category=category,
                    spent=spent,
                    limit=limit,
                    overshoot=spent - limit,
                )
            )
    breaches.sort(key=lambda b: b.overshoot, reverse=True)
    return breaches


def _compute_recap(
    session: Session,
    period: str,
    current_bounds: PeriodBounds,
    previous_bounds: PeriodBounds,
    top_merchants: int,
    top_changes: int,
) -> dict[str, Any]:
    """Shared computation logic for both period-based and custom recap."""
    current_cashflow = _cashflow(session, current_bounds)
    previous_cashflow = _cashflow(session, previous_bounds)
    current_expense = _expense_by_category(session, current_bounds)
    previous_expense = _expense_by_category(session, previous_bounds)

    changes = _category_changes(current_expense, previous_expense, limit=top_changes)
    merchants = _top_merchants(session, current_bounds, limit=top_merchants)
    breaches = _limit_breaches(session, current_bounds, current_expense)

    profile = session.get(UserProfile, PROFILE_ID)
    savings_goal = (
        Decimal(str(profile.monthly_savings_goal))
        if profile is not None and profile.monthly_savings_goal is not None
        else None
    )
    savings_progress: dict[str, Any] | None = None
    if savings_goal is not None and savings_goal > 0:
        net = current_cashflow["net"]
        savings_progress = {
            "goal": savings_goal,
            "net": net,
            "ratio": float(net / savings_goal) if savings_goal > 0 else 0.0,
            "met": net >= savings_goal,
        }

    return {
        "period": period,
        "current_from": current_bounds.start,
        "current_to": current_bounds.end,
        "previous_from": previous_bounds.start,
        "previous_to": previous_bounds.end,
        "cashflow": {
            "income": current_cashflow["income"],
            "expenses": current_cashflow["expenses"],
            "net": current_cashflow["net"],
            "income_delta": current_cashflow["income"] - previous_cashflow["income"],
            "expenses_delta": current_cashflow["expenses"]
            - previous_cashflow["expenses"],
            "net_delta": current_cashflow["net"] - previous_cashflow["net"],
        },
        "category_changes": [asdict(c) for c in changes],
        "top_merchants": [asdict(m) for m in merchants],
        "limit_breaches": [asdict(b) for b in breaches],
        "savings_progress": savings_progress,
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
