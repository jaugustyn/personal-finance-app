"""Aggregations used by dashboard stats endpoints."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Integer, and_, case, cast, func, select
from sqlalchemy.orm import Session

from finance.analytics.filters import category_candidate_type_filter, non_transfer_filters
from finance.currencies import amount_base_expr, resolve_base_currency
from finance.domain.enums import TransactionDirection, TransactionType
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
    load_merchant_identity_resolver,
    merchant_display_label,
)
from finance.transactions.type_decision import (
    TYPE_GOLD_METHODS,
    effective_transaction_type_expr,
)

__all__ = [
    "months_ago",
    "overview",
    "cashflow",
    "by_category",
    "by_transaction_type",
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
    tx_type = effective_transaction_type_expr()
    return func.coalesce(
        func.sum(
            case(
                (
                    (Transaction.direction == TransactionDirection.CREDIT.value)
                    & tx_type.in_([
                        TransactionType.SALARY.value,
                        TransactionType.INCOME.value,
                    ]),
                    func.abs(amount_base_expr()),
                ),
                else_=0,
            )
        ),
        0,
    )


def _expense_expr() -> Any:
    tx_type = effective_transaction_type_expr()
    return func.coalesce(
        func.sum(
            case(
                (
                    (Transaction.direction == TransactionDirection.DEBIT.value)
                    & (tx_type == TransactionType.EXPENSE.value),
                    func.abs(amount_base_expr()),
                ),
                else_=0,
            )
        ),
        0,
    )


def _typed_sum(transaction_type: TransactionType, direction: TransactionDirection) -> Any:
    tx_type = effective_transaction_type_expr()
    return func.coalesce(
        func.sum(
            case(
                (
                    (Transaction.direction == direction.value)
                    & (tx_type == transaction_type.value),
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


def _scope_filters(start: date | None, *, include_transfers: bool) -> list[Any]:
    filters = [*non_transfer_filters(include_transfers=include_transfers)]
    if start is not None:
        filters.append(Transaction.booking_date >= start)
    return filters


def _base_filters(start: date | None, *, include_transfers: bool) -> list[Any]:
    return [
        *_scope_filters(start, include_transfers=include_transfers),
        amount_base_expr().is_not(None),
    ]


def _month_parts() -> tuple[Any, Any]:
    return (
        cast(func.extract("year", Transaction.booking_date), Integer),
        cast(func.extract("month", Transaction.booking_date), Integer),
    )


def _month_label(year: int, month: int) -> str:
    return f"{int(year):04d}-{int(month):02d}"


def _category_candidate_type_filter() -> Any:
    return category_candidate_type_filter()


def overview(
    session: Session,
    *,
    months: int | None,
    include_transfers: bool = False,
) -> Overview:
    start = _period_start(months)
    safe_amount = amount_base_expr()
    converted = safe_amount.is_not(None)
    provisional = (
        Transaction.transaction_type_confirmation_method.is_(None)
        | Transaction.transaction_type_confirmation_method.not_in(TYPE_GOLD_METHODS)
    )
    stmt = select(
        _income_expr().label("inc"),
        _expense_expr().label("gross_exp"),
        _typed_sum(TransactionType.REFUND, TransactionDirection.CREDIT).label("refunds"),
        _typed_sum(TransactionType.DEBT_PAYMENT, TransactionDirection.DEBIT).label("debt"),
        _typed_sum(TransactionType.ASSET_ALLOCATION, TransactionDirection.DEBIT).label(
            "allocations"
        ),
        func.sum(case((converted, 1), else_=0)).label("cnt"),
        func.sum(
            case(
                (and_(converted, provisional), 1),
                else_=0,
            )
        ).label("provisional"),
        func.min(case((converted, Transaction.booking_date))).label("dmin"),
        func.max(case((converted, Transaction.booking_date))).label("dmax"),
        func.sum(case((safe_amount.is_(None), 1), else_=0)).label("unconverted"),
    ).where(*_scope_filters(start, include_transfers=include_transfers))
    row = session.execute(stmt).one()
    income = Decimal(row.inc or 0)
    gross_expenses = Decimal(row.gross_exp or 0)
    refunds = Decimal(row.refunds or 0)
    expenses = gross_expenses - refunds
    debt = Decimal(row.debt or 0)
    allocations = Decimal(row.allocations or 0)
    net = income - expenses - debt - allocations
    saved = income - expenses - debt
    savings = float(saved / income) if income > 0 else 0.0
    return Overview(
        period_from=row.dmin,
        period_to=row.dmax,
        total_income=income,
        gross_expenses=gross_expenses,
        total_refunds=refunds,
        total_expenses=expenses,
        total_debt_payments=debt,
        total_asset_allocations=allocations,
        net_cashflow=net,
        savings_rate=max(min(savings, 1.0), -10.0),
        tx_count=int(row.cnt or 0),
        base_currency=resolve_base_currency(session),
        provisional_transaction_count=int(row.provisional or 0),
        unconverted_count=int(row.unconverted or 0),
    )


def cashflow(
    session: Session,
    *,
    months: int | None,
    include_transfers: bool = False,
) -> list[CashflowBucket]:
    start = _period_start(months)
    year, month = _month_parts()
    transaction_type = effective_transaction_type_expr()
    stmt = select(
        year.label("year"),
        month.label("month"),
        transaction_type.label("transaction_type"),
        func.sum(func.abs(amount_base_expr())).label("amount"),
    ).where(*_base_filters(start, include_transfers=include_transfers)).group_by(
        year,
        month,
        transaction_type,
    )
    rows = session.execute(stmt).all()
    sums: dict[str, dict[str, Decimal]] = {}
    for row in rows:
        month_label = _month_label(row.year, row.month)
        bucket = sums.setdefault(
            month_label,
            {
                "income": Decimal(0),
                "expenses": Decimal(0),
                "refunds": Decimal(0),
                "debt": Decimal(0),
                "allocations": Decimal(0),
            },
        )
        amount = Decimal(row.amount or 0)
        if row.transaction_type in {
            TransactionType.SALARY.value,
            TransactionType.INCOME.value,
        }:
            bucket["income"] += amount
        elif row.transaction_type == TransactionType.EXPENSE.value:
            bucket["expenses"] += amount
        elif row.transaction_type == TransactionType.REFUND.value:
            bucket["refunds"] += amount
        elif row.transaction_type == TransactionType.DEBT_PAYMENT.value:
            bucket["debt"] += amount
        elif row.transaction_type == TransactionType.ASSET_ALLOCATION.value:
            bucket["allocations"] += amount
    return [
        CashflowBucket(
            month=month,
            income=values["income"],
            expenses=values["expenses"] - values["refunds"],
            refunds=values["refunds"],
            debt_payments=values["debt"],
            asset_allocations=values["allocations"],
            net=(
                values["income"]
                - values["expenses"]
                + values["refunds"]
                - values["debt"]
                - values["allocations"]
            ),
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
    amount = (
        func.coalesce(
            func.sum(
                case(
                    (
                        Transaction.direction == TransactionDirection.CREDIT.value,
                        -func.abs(amount_base_expr()),
                    ),
                    else_=func.abs(amount_base_expr()),
                )
            ),
            0,
        ).label("amount")
        if direction == TransactionDirection.DEBIT.value
        else _abs_amount_sum().label("amount")
    )
    count = func.count().label("cnt")
    filters = [
        *_base_filters(start, include_transfers=include_transfers),
    ]
    if direction == TransactionDirection.DEBIT.value:
        filters.append(_category_candidate_type_filter())
    else:
        filters.append(Transaction.direction == direction)
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


def by_transaction_type(
    session: Session,
    *,
    months: int | None,
    direction: str,
    limit: int,
    include_transfers: bool = False,
) -> list[CategorySpend]:
    start = _period_start(months)
    transaction_type = effective_transaction_type_expr()
    amount = _abs_amount_sum().label("amount")
    count = func.count().label("cnt")
    rows = session.execute(
        select(transaction_type.label("category"), amount, count)
        .where(
            *_base_filters(start, include_transfers=include_transfers),
            Transaction.direction == direction,
        )
        .group_by(transaction_type)
        .order_by(amount.desc())
        .limit(limit)
    ).all()
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
    filters = [
        *_base_filters(start, include_transfers=include_transfers),
        Transaction.direction == direction,
    ]
    if direction == TransactionDirection.DEBIT.value:
        filters.append(
            effective_transaction_type_expr() == TransactionType.EXPENSE.value
        )
    resolver = load_merchant_identity_resolver(session)
    amount = func.abs(amount_base_expr())
    groups: dict[str, dict[str, Any]] = {}
    rows = session.execute(
        select(
            Transaction.merchant,
            Transaction.title,
            Transaction.category,
            func.sum(amount).label("amount"),
            func.count(Transaction.id).label("tx_count"),
        )
        .where(*filters)
        .group_by(Transaction.merchant, Transaction.title, Transaction.category)
    ).all()
    for row in rows:
        identity = resolver.resolve(row.merchant, row.title)
        key = identity.canonical_key
        if not key:
            continue
        label = identity.display_label or merchant_display_label(row.merchant, row.title)
        value = Decimal(row.amount or 0)
        row_count = int(row.tx_count or 0)
        group = groups.setdefault(
            key,
            {
                "amount": Decimal(0),
                "count": 0,
                "merchant_canonical_key": key,
                "labels": {},
                "categories": {},
            },
        )
        group["amount"] += value
        group["count"] += row_count
        labels = group["labels"]
        label_stats = labels.setdefault(label, {"count": 0, "amount": Decimal(0)})
        label_stats["count"] += row_count
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
                merchant_display=label,
                merchant_canonical_key=str(group["merchant_canonical_key"]),
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
    amount = func.coalesce(
        func.sum(
            case(
                (
                    Transaction.direction == TransactionDirection.CREDIT.value,
                    -func.abs(amount_base_expr()),
                ),
                else_=func.abs(amount_base_expr()),
            )
        ),
        0,
    ).label("amount")
    base: tuple[Any, ...] = (
        *_base_filters(start, include_transfers=include_transfers),
        Transaction.category.is_not(None),
    )
    if direction == TransactionDirection.DEBIT.value:
        base = (*base, _category_candidate_type_filter())
    else:
        base = (*base, Transaction.direction == direction)

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

    year, month = _month_parts()
    rows = session.execute(
        select(
            year.label("year"),
            month.label("month"),
            Transaction.category.label("category"),
            func.sum(
                case(
                    (
                        Transaction.direction == TransactionDirection.CREDIT.value,
                        -func.abs(amount_base_expr()),
                    ),
                    else_=func.abs(amount_base_expr()),
                )
            ).label("amount"),
        )
        .where(*base, Transaction.category.in_(top_categories))
        .group_by(year, month, Transaction.category)
    ).all()
    return [
        CategoryTrendPoint(
            month=_month_label(row.year, row.month),
            category=row.category,
            amount=Decimal(row.amount or 0),
        )
        for row in sorted(rows, key=lambda item: (item.year, item.month, item.category))
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
    filters = [
        *_base_filters(start, include_transfers=include_transfers),
        Transaction.direction == direction,
    ]
    if direction == TransactionDirection.DEBIT.value:
        filters.append(
            effective_transaction_type_expr() == TransactionType.EXPENSE.value
        )
    rows = session.execute(
        select(func.abs(amount_base_expr()))
        .where(*filters)
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
