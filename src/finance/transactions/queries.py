"""Read-side transaction queries."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from finance.domain.models import Transaction

CategoryState = Literal[
    "all",
    "categorized",
    "uncategorized",
    "suggested",
    "needs_review",
    "rejected",
]


@dataclass(frozen=True)
class TransactionFilters:
    date_from: date | None = None
    date_to: date | None = None
    include_transfers: bool = True
    import_id: int | None = None
    merchant: str | None = None
    category_state: CategoryState = "all"
    has_suggestion: bool | None = None
    min_confidence: float | None = None
    max_confidence: float | None = None
    transaction_type: str | None = None
    review_priority: bool = False


@dataclass(frozen=True)
class CategorySummary:
    category: str | None
    total_debit: Decimal
    total_credit: Decimal
    count: int


@dataclass(frozen=True)
class MerchantGroupSummary:
    merchant: str
    count: int
    total_debit: Decimal
    total_credit: Decimal
    common_category: str | None
    sample_titles: list[str]


def _review_priority_expr():
    return case(
        (
            Transaction.category.is_not(None),
            90,
        ),
        (
            Transaction.category_suggestion_rejected.is_(True),
            80,
        ),
        (
            Transaction.category_predicted.is_(None),
            0,
        ),
        (
            Transaction.category_confidence.is_(None),
            10,
        ),
        (
            Transaction.category_confidence < 0.55,
            20,
        ),
        (
            Transaction.category_confidence < 0.75,
            30,
        ),
        else_=40,
    )


def filtered_transactions_stmt(filters: TransactionFilters):
    stmt = select(Transaction)
    if filters.date_from is not None:
        stmt = stmt.where(Transaction.booking_date >= filters.date_from)
    if filters.date_to is not None:
        stmt = stmt.where(Transaction.booking_date <= filters.date_to)
    if not filters.include_transfers:
        stmt = stmt.where(Transaction.is_transfer.is_(False))
    if filters.import_id is not None:
        stmt = stmt.where(Transaction.import_id == filters.import_id)
    if filters.merchant:
        stmt = stmt.where(Transaction.merchant == filters.merchant)
    if filters.transaction_type:
        stmt = stmt.where(Transaction.transaction_type == filters.transaction_type)
    if filters.category_state == "categorized":
        stmt = stmt.where(Transaction.category.is_not(None))
    elif filters.category_state == "uncategorized":
        stmt = stmt.where(Transaction.category.is_(None))
    elif filters.category_state == "suggested":
        stmt = stmt.where(Transaction.category.is_(None))
        stmt = stmt.where(Transaction.category_predicted.is_not(None))
        stmt = stmt.where(Transaction.category_suggestion_rejected.is_(False))
    elif filters.category_state == "needs_review":
        stmt = stmt.where(Transaction.category.is_(None))
        stmt = stmt.where(Transaction.category_suggestion_rejected.is_(False))
    elif filters.category_state == "rejected":
        stmt = stmt.where(Transaction.category.is_(None))
        stmt = stmt.where(Transaction.category_suggestion_rejected.is_(True))
    if filters.has_suggestion is True:
        stmt = stmt.where(Transaction.category_predicted.is_not(None))
        stmt = stmt.where(Transaction.category_suggestion_rejected.is_(False))
    elif filters.has_suggestion is False:
        stmt = stmt.where(Transaction.category_predicted.is_(None))
    if filters.min_confidence is not None:
        stmt = stmt.where(Transaction.category_confidence >= filters.min_confidence)
    if filters.max_confidence is not None:
        stmt = stmt.where(Transaction.category_confidence <= filters.max_confidence)
    if filters.review_priority:
        stmt = stmt.order_by(_review_priority_expr().asc(), Transaction.booking_date.desc())
    else:
        stmt = stmt.order_by(Transaction.booking_date.desc())
    return stmt


def list_transactions(
    session: Session,
    filters: TransactionFilters,
    *,
    limit: int,
    offset: int,
) -> list[Transaction]:
    stmt = filtered_transactions_stmt(filters).offset(offset).limit(limit)
    return list(session.execute(stmt).scalars().all())


def summary_by_category(
    session: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[CategorySummary]:
    debit = func.sum(
        case((Transaction.direction == "debit", Transaction.amount), else_=0)
    ).label("total_debit")
    credit = func.sum(
        case((Transaction.direction == "credit", Transaction.amount), else_=0)
    ).label("total_credit")
    tx_count = func.count().label("tx_count")

    stmt = select(Transaction.category, debit, credit, tx_count).group_by(
        Transaction.category
    )
    if date_from is not None:
        stmt = stmt.where(Transaction.booking_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(Transaction.booking_date <= date_to)

    rows = session.execute(stmt).all()
    return [
        CategorySummary(
            category=row.category,
            total_debit=row.total_debit or Decimal(0),
            total_credit=row.total_credit or Decimal(0),
            count=int(row.tx_count),
        )
        for row in rows
    ]


def merchant_groups(
    session: Session,
    *,
    only_uncategorized: bool,
    min_count: int,
    limit: int,
) -> list[MerchantGroupSummary]:
    debit = func.sum(
        case((Transaction.direction == "debit", Transaction.amount), else_=0)
    ).label("total_debit")
    credit = func.sum(
        case((Transaction.direction == "credit", Transaction.amount), else_=0)
    ).label("total_credit")
    tx_count = func.count().label("tx_count")

    stmt = select(Transaction.merchant, debit, credit, tx_count).where(
        Transaction.merchant != ""
    )
    if only_uncategorized:
        stmt = stmt.where(Transaction.category.is_(None))
    stmt = stmt.group_by(Transaction.merchant).having(tx_count >= min_count)
    stmt = stmt.order_by(tx_count.desc()).limit(limit)
    rows = session.execute(stmt).all()

    out: list[MerchantGroupSummary] = []
    for row in rows:
        samples = session.execute(
            select(Transaction.title, Transaction.category)
            .where(Transaction.merchant == row.merchant)
            .order_by(Transaction.booking_date.desc())
            .limit(20)
        ).all()
        titles = list({sample.title for sample in samples if sample.title})[:3]
        cats = [sample.category for sample in samples if sample.category]
        common_cat = max(set(cats), key=cats.count) if cats else None
        out.append(
            MerchantGroupSummary(
                merchant=row.merchant,
                count=int(row.tx_count),
                total_debit=row.total_debit or Decimal(0),
                total_credit=row.total_credit or Decimal(0),
                common_category=common_cat,
                sample_titles=titles,
            )
        )
    return out
