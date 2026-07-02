"""Sankey flow data for income -> categories -> merchants."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finance.currencies import amount_base_expr
from finance.domain.enums import TransactionDirection
from finance.domain.models import Transaction
from finance.transactions.merchants import (
    load_merchant_alias_maps,
    merchant_display_label,
    merchant_identity,
)

SankeyNode = dict[str, str | None]


def sankey(
    session: Session,
    *,
    months: int,
    top_categories: int,
    top_merchants_per_cat: int,
) -> tuple[list[SankeyNode], list[dict[str, int | Decimal]]]:
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
            Transaction.title.label("title"),
            func.sum(func.abs(amount_expr)).label("amt"),
        )
        .where(
            Transaction.booking_date >= start,
            Transaction.direction == TransactionDirection.DEBIT.value,
        )
        .group_by("cat", "merchant", "title")
    )

    rows = session.execute(expense_q).all()
    if not rows:
        return [{"name": "Przychody", "node_type": "income"}], []

    alias_map, label_map = load_merchant_alias_maps(session)
    cat_totals: dict[str, Decimal] = {}
    cat_merchants: dict[str, dict[str, dict[str, str | Decimal]]] = {}
    for cat, merchant, title, amount in rows:
        value = Decimal(amount or 0)
        cat_totals[cat] = cat_totals.get(cat, Decimal("0")) + value
        identity = merchant_identity(
            merchant,
            title,
            alias_map=alias_map,
            label_map=label_map,
        )
        merchant_key = identity.canonical_key or "(b/d)"
        merchant_display = (
            identity.display_label
            or merchant_display_label(merchant, title)
            or "(b/d)"
        )
        group = cat_merchants.setdefault(cat, {}).setdefault(
            merchant_key,
            {
                "merchant_display": merchant_display,
                "merchant_canonical_key": merchant_key,
                "amount": Decimal("0"),
            },
        )
        group["amount"] = Decimal(group["amount"]) + value

    sorted_cats = sorted(cat_totals.items(), key=lambda item: item[1], reverse=True)
    top_cats = sorted_cats[:top_categories]
    other_total = sum((value for _, value in sorted_cats[top_categories:]), Decimal("0"))

    income_total = session.execute(
        select(func.coalesce(func.sum(func.abs(amount_expr)), 0)).where(
            Transaction.booking_date >= start,
            Transaction.direction == TransactionDirection.CREDIT.value,
        )
    ).scalar_one()
    income_total = Decimal(income_total or 0)

    nodes: list[SankeyNode] = [{"name": "Przychody", "node_type": "income"}]
    links: list[dict[str, int | Decimal]] = []
    cat_index: dict[str, int] = {}

    for cat, total in top_cats:
        idx = len(nodes)
        nodes.append({"name": cat, "node_type": "category", "category": cat})
        cat_index[cat] = idx
        links.append({"source": 0, "target": idx, "value": total})

    if other_total > 0:
        idx = len(nodes)
        nodes.append({"name": "Inne", "node_type": "other"})
        links.append({"source": 0, "target": idx, "value": other_total})

    spent_total = sum(cat_totals.values(), Decimal("0"))
    savings = income_total - spent_total
    if savings > 0:
        idx = len(nodes)
        nodes.append({"name": "Oszczędności", "node_type": "savings"})
        links.append({"source": 0, "target": idx, "value": savings})

    for cat, _ in top_cats:
        merchants = sorted(
            cat_merchants[cat].values(),
            key=lambda item: Decimal(item["amount"]),
            reverse=True,
        )
        top_m = merchants[:top_merchants_per_cat]
        rest = sum(
            (
                Decimal(row["amount"])
                for row in merchants[top_merchants_per_cat:]
            ),
            Decimal("0"),
        )
        for merchant_row in top_m:
            idx = len(nodes)
            merchant_amount = Decimal(merchant_row["amount"])
            nodes.append(
                {
                    "name": str(merchant_row["merchant_display"]),
                    "node_type": "merchant",
                    "merchant_display": str(merchant_row["merchant_display"]),
                    "merchant_canonical_key": str(
                        merchant_row["merchant_canonical_key"]
                    ),
                }
            )
            links.append(
                {"source": cat_index[cat], "target": idx, "value": merchant_amount}
            )
        if rest > 0:
            idx = len(nodes)
            nodes.append({"name": f"{cat} - inni", "node_type": "other"})
            links.append({"source": cat_index[cat], "target": idx, "value": rest})

    return nodes, links
