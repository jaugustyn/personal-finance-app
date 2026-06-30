"""Aggregations used by dashboard stats endpoints."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from finance.analytics.filters import category_candidate_type_filter, non_transfer_filters
from finance.currencies import amount_base_expr, resolve_base_currency
from finance.domain.enums import TransactionDirection
from finance.domain.models import Transaction
from finance.stats.recap import custom_recap, period_recap
from finance.stats.types import (
    CashflowBucket,
    CategorySpend,
    CategoryTrendPoint,
    DistributionBucket,
    MerchantSpend,
    NetWorthPoint,
    Overview,
    SpendDistribution,
    month_bucket,
)
from finance.transactions.merchants import (
    load_merchant_alias_maps,
    merchant_display_label,
    merchant_identity,
)

__all__ = [
    "months_ago",
    "overview",
    "cashflow",
    "by_category",
    "networth",
    "top_merchants",
    "category_trend",
    "spend_distribution",
    "period_recap",
    "custom_recap",
    "month_bucket",
]

def months_ago(months: int) -> date:
    today = date.today()
    year = today.year
    month = today.month - months
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def _income_expr() -> Any:
    return func.coalesce(
        func.sum(
            case(
                (
                    Transaction.direction == TransactionDirection.CREDIT.value,
                    func.abs(amount_base_expr()),
                ),
                else_=0,
            )
        ),
        0,
    )


def _expense_expr() -> Any:
    return func.coalesce(
        func.sum(
            case(
                (
                    Transaction.direction == TransactionDirection.DEBIT.value,
                    func.abs(amount_base_expr()),
                ),
                else_=0,
            )
        ),
        0,
    )


def _abs_amount_sum() -> Any:
    return func.coalesce(func.sum(func.abs(amount_base_expr())), 0)


def _period_start(months: int | None) -> date | None:
    return months_ago(months - 1) if months is not None else None


def _base_filters(start: date | None, *, include_transfers: bool) -> list[Any]:
    filters = [*non_transfer_filters(include_transfers=include_transfers)]
    if start is not None:
        filters.append(Transaction.booking_date >= start)
    return filters


def _category_candidate_type_filter() -> Any:
    return category_candidate_type_filter()


def overview(
    session: Session,
    *,
    months: int | None,
    include_transfers: bool = False,
) -> Overview:
    start = _period_start(months)
    stmt = select(
        _income_expr().label("inc"),
        _expense_expr().label("exp"),
        func.count().label("cnt"),
        func.min(Transaction.booking_date).label("dmin"),
        func.max(Transaction.booking_date).label("dmax"),
    ).where(*_base_filters(start, include_transfers=include_transfers))
    row = session.execute(stmt).one()
    income = Decimal(row.inc or 0)
    expenses = Decimal(row.exp or 0)
    net = income - expenses
    savings = float(net / income) if income > 0 else 0.0
    return Overview(
        period_from=row.dmin,
        period_to=row.dmax,
        total_income=income,
        total_expenses=expenses,
        net_cashflow=net,
        savings_rate=max(min(savings, 1.0), -10.0),
        tx_count=int(row.cnt or 0),
        base_currency=resolve_base_currency(session),
    )


def cashflow(
    session: Session,
    *,
    months: int | None,
    include_transfers: bool = False,
) -> list[CashflowBucket]:
    start = _period_start(months)
    stmt = select(
        Transaction.booking_date,
        Transaction.direction,
        func.abs(amount_base_expr()).label("amount"),
    ).where(*_base_filters(start, include_transfers=include_transfers))
    rows = session.execute(stmt).all()
    sums: dict[str, dict[str, Decimal]] = {}
    for row in rows:
        month = month_bucket(row.booking_date)
        bucket = sums.setdefault(month, {"income": Decimal(0), "expenses": Decimal(0)})
        amount = Decimal(row.amount or 0)
        if row.direction == TransactionDirection.CREDIT.value:
            bucket["income"] += amount
        elif row.direction == TransactionDirection.DEBIT.value:
            bucket["expenses"] += amount
    return [
        CashflowBucket(
            month=month,
            income=values["income"],
            expenses=values["expenses"],
            net=values["income"] - values["expenses"],
        )
        for month, values in sorted(sums.items())
    ]


def by_category(
    session: Session,
    *,
    months: int | None,
    direction: str,
    limit: int,
    include_transfers: bool = False,
    include_predictions: bool = False,
) -> list[CategorySpend]:
    start = _period_start(months)
    category = (
        func.coalesce(Transaction.category, Transaction.category_predicted)
        if include_predictions
        else Transaction.category
    )
    amount = _abs_amount_sum().label("amount")
    count = func.count().label("cnt")
    filters = [
        *_base_filters(start, include_transfers=include_transfers),
        Transaction.direction == direction,
    ]
    if direction == TransactionDirection.DEBIT.value:
        filters.append(_category_candidate_type_filter())
    stmt = (
        select(category.label("category"), amount, count)
        .where(*filters)
        .group_by(category)
        .order_by(amount.desc())
        .limit(limit)
    )
    rows = session.execute(stmt).all()
    total = sum((Decimal(row.amount or 0) for row in rows), Decimal(0))
    out: list[CategorySpend] = []
    for row in rows:
        value = Decimal(row.amount or 0)
        out.append(
            CategorySpend(
                category=row.category,
                amount=value,
                share=float(value / total) if total > 0 else 0.0,
                count=int(row.cnt),
            )
        )
    return out


def networth(
    session: Session,
    *,
    months: int | None,
    include_transfers: bool = False,
) -> list[NetWorthPoint]:
    running = Decimal(0)
    out: list[NetWorthPoint] = []
    for row in cashflow(
        session,
        months=months,
        include_transfers=include_transfers,
    ):
        running += row.net
        out.append(NetWorthPoint(month=row.month, balance=running))
    return out


def top_merchants(
    session: Session,
    *,
    months: int | None,
    limit: int,
    direction: str,
    include_transfers: bool = False,
    sort: str = "amount",
) -> list[MerchantSpend]:
    start = _period_start(months)
    rows = session.execute(
        select(
            Transaction.merchant,
            Transaction.title,
            func.abs(amount_base_expr()).label("amount"),
            Transaction.category,
        )
        .where(*_base_filters(start, include_transfers=include_transfers))
        .where(Transaction.direction == direction)
    ).all()

    alias_map, label_map = load_merchant_alias_maps(session)
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        identity = merchant_identity(
            row.merchant,
            row.title,
            alias_map=alias_map,
            label_map=label_map,
        )
        key = identity.canonical_key
        if not key:
            continue
        label = identity.display_label or merchant_display_label(row.merchant, row.title)
        value = Decimal(row.amount or 0)
        group = groups.setdefault(
            key,
            {
                "amount": Decimal(0),
                "count": 0,
                "labels": {},
                "categories": {},
            },
        )
        group["amount"] += value
        group["count"] += 1
        labels = group["labels"]
        label_stats = labels.setdefault(label, {"count": 0, "amount": Decimal(0)})
        label_stats["count"] += 1
        label_stats["amount"] += value
        if row.category:
            categories = group["categories"]
            categories[row.category] = categories.get(row.category, Decimal(0)) + value

    order_key = (
        (lambda item: (item[1]["count"], item[1]["amount"]))
        if sort == "count"
        else (lambda item: (item[1]["amount"], item[1]["count"]))
    )
    sorted_groups = sorted(groups.items(), key=order_key, reverse=True)[:limit]

    out: list[MerchantSpend] = []
    for _key, group in sorted_groups:
        label = max(
            group["labels"].items(),
            key=lambda item: (item[1]["count"], item[1]["amount"], item[0]),
        )[0]
        dominant_category = None
        if group["categories"]:
            dominant_category = max(
                group["categories"].items(),
                key=lambda item: item[1],
            )[0]
        out.append(
            MerchantSpend(
                merchant=label,
                amount=group["amount"],
                count=int(group["count"]),
                category=dominant_category,
            )
        )
    return out


def category_trend(
    session: Session,
    *,
    months: int | None,
    direction: str,
    limit: int,
    include_transfers: bool = False,
) -> list[CategoryTrendPoint]:
    """Monthly spend per category for the top ``limit`` categories.

    Returns a flat, chronologically ordered list of ``{month, category,
    amount}`` rows covering only the categories with the highest total spend in
    the window. Uncategorised transactions (NULL category) are excluded so the
    series stay interpretable; the dashboard pivots these rows into a per-month
    multi-series chart.
    """
    start = _period_start(months)
    amount = _abs_amount_sum().label("amount")
    base = (
        *_base_filters(start, include_transfers=include_transfers),
        Transaction.direction == direction,
        Transaction.category.is_not(None),
    )
    if direction == TransactionDirection.DEBIT.value:
        base = (*base, _category_candidate_type_filter())

    totals = session.execute(
        select(Transaction.category.label("category"), amount)
        .where(*base)
        .group_by(Transaction.category)
        .order_by(amount.desc())
        .limit(limit)
    ).all()
    top_categories = [row.category for row in totals]
    if not top_categories:
        return []

    rows = session.execute(
        select(
            Transaction.booking_date,
            Transaction.category.label("category"),
            func.abs(amount_base_expr()).label("amount"),
        ).where(*base, Transaction.category.in_(top_categories))
    ).all()
    sums: dict[tuple[str, str], Decimal] = {}
    for row in rows:
        key = (month_bucket(row.booking_date), row.category)
        sums[key] = sums.get(key, Decimal(0)) + Decimal(row.amount or 0)
    return [
        CategoryTrendPoint(month=month, category=category, amount=value)
        for (month, category), value in sorted(sums.items())
    ]


def spend_distribution(
    session: Session,
    *,
    months: int | None,
    direction: str,
    bins: int = 12,
    include_transfers: bool = False,
) -> SpendDistribution:
    """Histogram and summary statistics of single-transaction amounts.

    Powers the dashboard distribution/outlier view: equal-width histogram
    buckets plus median, mean, the 95th percentile and the inter-quartile
    bounds used to flag outliers. Computation happens in Python over the
    in-window amounts, which is bounded for a personal-finance dataset.
    """
    start = _period_start(months)
    rows = session.execute(
        select(func.abs(amount_base_expr()))
        .where(
            *_base_filters(start, include_transfers=include_transfers),
            Transaction.direction == direction,
        )
    ).all()
    amounts = sorted(float(row[0]) for row in rows)
    if not amounts:
        return SpendDistribution(
            buckets=[],
            count=0,
            mean=0.0,
            median=0.0,
            p95=0.0,
            max=0.0,
            iqr_upper=0.0,
        )

    def _percentile(data: list[float], q: float) -> float:
        if len(data) == 1:
            return data[0]
        pos = q * (len(data) - 1)
        low = int(pos)
        high = min(low + 1, len(data) - 1)
        return data[low] + (data[high] - data[low]) * (pos - low)

    count = len(amounts)
    mean = sum(amounts) / count
    median = _percentile(amounts, 0.5)
    q1 = _percentile(amounts, 0.25)
    q3 = _percentile(amounts, 0.75)
    p95 = _percentile(amounts, 0.95)
    maximum = amounts[-1]
    iqr_upper = q3 + 1.5 * (q3 - q1)

    lo, hi = amounts[0], maximum
    width = (hi - lo) / bins if hi > lo else 1.0
    buckets: list[DistributionBucket] = []
    for i in range(bins):
        lower = lo + i * width
        upper = lo + (i + 1) * width if i < bins - 1 else hi
        in_bucket = sum(1 for a in amounts if lower <= a <= upper) if i == bins - 1 else sum(
            1 for a in amounts if lower <= a < upper
        )
        buckets.append(DistributionBucket(lower=lower, upper=upper, count=in_bucket))

    return SpendDistribution(
        buckets=buckets,
        count=count,
        mean=mean,
        median=median,
        p95=p95,
        max=maximum,
        iqr_upper=iqr_upper,
    )
