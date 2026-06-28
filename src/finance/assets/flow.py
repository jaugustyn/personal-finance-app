"""Sankey flow data for income -> categories -> merchants."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finance.currencies import amount_base_expr
from finance.domain.models import Transaction


def sankey(
    session: Session,
    *,
    months: int,
    top_categories: int,
    top_merchants_per_cat: int,
) -> tuple[list[dict[str, str]], list[dict[str, int | Decimal]]]:
    today = date.today()
    year = today.year
    month = today.month - (months - 1)
    while month <= 0:
        month += 12
        year -= 1
    start = date(year, month, 1)
    amount_expr = amount_base_expr()

    expense_q = (
        select(
            func.coalesce(Transaction.category, "(brak)").label("cat"),
            Transaction.merchant.label("merchant"),
            func.sum(func.abs(amount_expr)).label("amt"),
        )
        .where(
            Transaction.booking_date >= start,
            Transaction.direction == "debit",
        )
        .group_by("cat", "merchant")
    )

    rows = session.execute(expense_q).all()
    if not rows:
        return [{"name": "Przychody"}], []

    cat_totals: dict[str, Decimal] = {}
    cat_merchants: dict[str, list[tuple[str, Decimal]]] = {}
    for cat, merchant, amount in rows:
        value = Decimal(amount or 0)
        cat_totals[cat] = cat_totals.get(cat, Decimal("0")) + value
        cat_merchants.setdefault(cat, []).append((merchant or "(b/d)", value))

    sorted_cats = sorted(cat_totals.items(), key=lambda item: item[1], reverse=True)
    top_cats = sorted_cats[:top_categories]
    other_total = sum((value for _, value in sorted_cats[top_categories:]), Decimal("0"))

    income_total = session.execute(
        select(func.coalesce(func.sum(func.abs(amount_expr)), 0)).where(
            Transaction.booking_date >= start,
            Transaction.direction == "credit",
        )
    ).scalar_one()
    income_total = Decimal(income_total or 0)

    nodes: list[dict[str, str]] = [{"name": "Przychody"}]
    links: list[dict[str, int | Decimal]] = []
    cat_index: dict[str, int] = {}

    for cat, total in top_cats:
        idx = len(nodes)
        nodes.append({"name": cat})
        cat_index[cat] = idx
        links.append({"source": 0, "target": idx, "value": total})

    if other_total > 0:
        idx = len(nodes)
        nodes.append({"name": "Inne"})
        links.append({"source": 0, "target": idx, "value": other_total})

    spent_total = sum(cat_totals.values(), Decimal("0"))
    savings = income_total - spent_total
    if savings > 0:
        idx = len(nodes)
        nodes.append({"name": "Oszczędności"})
        links.append({"source": 0, "target": idx, "value": savings})

    for cat, _ in top_cats:
        merchants = sorted(cat_merchants[cat], key=lambda item: item[1], reverse=True)
        top_m = merchants[:top_merchants_per_cat]
        rest = sum((value for _, value in merchants[top_merchants_per_cat:]), Decimal("0"))
        for merchant_name, merchant_amount in top_m:
            idx = len(nodes)
            nodes.append({"name": merchant_name})
            links.append({"source": cat_index[cat], "target": idx, "value": merchant_amount})
        if rest > 0:
            idx = len(nodes)
            nodes.append({"name": f"{cat} - inni"})
            links.append({"source": cat_index[cat], "target": idx, "value": rest})

    return nodes, links
