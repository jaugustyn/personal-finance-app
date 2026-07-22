"""Spending and comparison function-calling tools."""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from finance.analytics.filters import (
    debit_spending_filters,
    expense_category_candidate_filters,
    non_transfer_filters,
    period_filters,
)
from finance.currencies import amount_base_expr, resolve_base_currency
from finance.domain.models import Transaction
from finance.llm.periods import parse_period
from finance.llm.tool_schemas import (
    CashflowOverviewArgs,
    ComparePeriodsArgs,
    GetSpendingArgs,
    TopCategoriesArgs,
    TopMerchantsArgs,
)
from finance.llm.types import (
    CashflowOverviewResult,
    CategorySpend,
    ComparePeriodsResult,
    GetSpendingResult,
    MerchantSpend,
    PeriodRange,
    PeriodTotal,
    ToolResult,
    TopCategoriesResult,
    TopMerchantsResult,
    tool_result,
)
from finance.stats.recap import cashflow_totals
from finance.transactions.merchants import (
    load_merchant_alias_maps,
    merchant_display_label,
    merchant_identity,
)


def get_spending(session: Session, args: dict[str, Any]) -> ToolResult:
    parsed = GetSpendingArgs(**args)
    start, end = parse_period(parsed.period)
    amount = amount_base_expr()
    net_amount = case(
        (Transaction.direction == "credit", -func.abs(amount)),
        else_=func.abs(amount),
    )
    filters = [
        *expense_category_candidate_filters(),
        *period_filters(start, end),
        amount.is_not(None),
    ]
    if parsed.category:
        filters.append(Transaction.category == parsed.category)
    stmt = select(func.sum(net_amount), func.count(amount)).where(*filters)
    total, n = session.execute(stmt).one()
    return tool_result(
        GetSpendingResult(
            period=PeriodRange(start=start.isoformat(), end=end.isoformat()),
            category=parsed.category,
            total=float(total or 0.0),
            currency=resolve_base_currency(session),
            transactions=int(n or 0),
        )
    )


def top_merchants(session: Session, args: dict[str, Any]) -> ToolResult:
    parsed = TopMerchantsArgs(**args)
    start, end = parse_period(parsed.period)
    amount_expr = amount_base_expr()
    rows = session.execute(
        select(Transaction.merchant, Transaction.title, func.abs(amount_expr)).where(
            *debit_spending_filters(start, end, category=parsed.category),
            amount_expr.is_not(None),
        )
    ).all()
    alias_map, label_map = load_merchant_alias_maps(session)
    groups: dict[str, dict[str, Any]] = {}
    for merchant, title, amount in rows:
        identity = merchant_identity(
            merchant,
            title,
            alias_map=alias_map,
            label_map=label_map,
        )
        if not identity.canonical_key:
            continue
        group = groups.setdefault(
            identity.canonical_key,
            {"total": 0.0, "count": 0, "labels": {}},
        )
        total = float(amount or 0.0)
        group["total"] += total
        group["count"] += 1
        label = identity.display_label or merchant_display_label(merchant, title)
        labels = group["labels"]
        label_stats = labels.setdefault(label, {"count": 0, "total": 0.0})
        label_stats["count"] += 1
        label_stats["total"] += total
    merchants: list[MerchantSpend] = []
    for group in sorted(
        groups.values(),
        key=lambda item: (item["total"], item["count"]),
        reverse=True,
    )[: parsed.limit]:
        label = max(
            group["labels"].items(),
            key=lambda item: (item[1]["count"], item[1]["total"], item[0]),
        )[0]
        merchants.append(
            MerchantSpend(
                merchant=label,
                total=float(group["total"]),
                transactions=int(group["count"]),
            )
        )
    return tool_result(
        TopMerchantsResult(
            period=PeriodRange(start=start.isoformat(), end=end.isoformat()),
            category=parsed.category,
            currency=resolve_base_currency(session),
            merchants=merchants,
        )
    )


def top_categories(session: Session, args: dict[str, Any]) -> ToolResult:
    parsed = TopCategoriesArgs(**args)
    start, end = parse_period(parsed.period)
    amount_expr = amount_base_expr()
    net_amount = case(
        (Transaction.direction == "credit", -func.abs(amount_expr)),
        else_=func.abs(amount_expr),
    )
    base_filters = [
        *expense_category_candidate_filters(),
        *period_filters(start, end),
        amount_expr.is_not(None),
    ]
    total_stmt = select(
        func.sum(net_amount),
        func.count(amount_expr),
    ).where(*base_filters)
    total, tx_count = session.execute(total_stmt).one()
    total_candidate_spend = float(total or 0.0)

    rows = session.execute(
        select(
            Transaction.category,
            func.sum(net_amount).label("total"),
            func.count(amount_expr).label("n"),
        )
        .where(*base_filters, Transaction.category.is_not(None))
        .group_by(Transaction.category)
        .order_by(func.sum(net_amount).desc())
    ).all()
    categorized_total = float(sum(float(total or 0.0) for _, total, _ in rows))
    uncategorized_total = max(total_candidate_spend - categorized_total, 0.0)
    category_coverage = (
        categorized_total / total_candidate_spend if total_candidate_spend else 0.0
    )

    categories: list[CategorySpend] = []
    for category, category_total, n in rows[: parsed.limit]:
        value = float(category_total or 0.0)
        categories.append(
            CategorySpend(
                category=str(category),
                total=value,
                transactions=int(n or 0),
                share=value / total_candidate_spend if total_candidate_spend else 0.0,
            )
        )

    return tool_result(
        TopCategoriesResult(
            period=PeriodRange(start=start.isoformat(), end=end.isoformat()),
            currency=resolve_base_currency(session),
            total_candidate_spend=total_candidate_spend,
            categorized_total=categorized_total,
            uncategorized_total=uncategorized_total,
            category_coverage=category_coverage,
            transactions=int(tx_count or 0),
            categories=categories,
        )
    )


def cashflow_overview(session: Session, args: dict[str, Any]) -> ToolResult:
    parsed = CashflowOverviewArgs(**args)
    start, end = parse_period(parsed.period)
    amount_expr = amount_base_expr()
    totals = cashflow_totals(session, date_from=start, date_to=end)
    tx_count = int(
        session.scalar(
            select(func.count()).where(
                *period_filters(start, end),
                *non_transfer_filters(),
                amount_expr.is_not(None),
            )
        )
        or 0
    )
    income = float(totals["income"])
    expenses = float(totals["expenses"])
    debt_payments = float(totals["debt_payments"])
    net = float(totals["net"])
    saved = income - expenses - debt_payments
    savings_rate = saved / income if income > 0 else 0.0
    return tool_result(
        CashflowOverviewResult(
            period=PeriodRange(start=start.isoformat(), end=end.isoformat()),
            currency=resolve_base_currency(session),
            income=income,
            gross_expenses=float(totals["gross_expenses"]),
            refunds=float(totals["refunds"]),
            expenses=expenses,
            debt_payments=debt_payments,
            asset_allocations=float(totals["asset_allocations"]),
            net=net,
            savings_rate=max(min(savings_rate, 1.0), -10.0),
            transactions=tx_count,
        )
    )


def compare_periods(session: Session, args: dict[str, Any]) -> ToolResult:
    parsed = ComparePeriodsArgs(**args)
    a_start, a_end = parse_period(parsed.period_a)
    b_start, b_end = parse_period(parsed.period_b)

    def _sum(start: date, end: date) -> float:
        amount_expr = amount_base_expr()
        net_amount = case(
            (Transaction.direction == "credit", -func.abs(amount_expr)),
            else_=func.abs(amount_expr),
        )
        filters = [
            *expense_category_candidate_filters(),
            *period_filters(start, end),
            amount_expr.is_not(None),
        ]
        if parsed.category:
            filters.append(Transaction.category == parsed.category)
        stmt = select(func.sum(net_amount)).where(*filters)
        return float(session.execute(stmt).scalar() or 0.0)

    total_a, total_b = _sum(a_start, a_end), _sum(b_start, b_end)
    delta = total_a - total_b
    pct = (delta / total_b * 100.0) if total_b else None
    return tool_result(
        ComparePeriodsResult(
            category=parsed.category,
            currency=resolve_base_currency(session),
            a=PeriodTotal(
                start=a_start.isoformat(),
                end=a_end.isoformat(),
                total=total_a,
            ),
            b=PeriodTotal(
                start=b_start.isoformat(),
                end=b_end.isoformat(),
                total=total_b,
            ),
            delta=delta,
            delta_pct=pct,
        )
    )
