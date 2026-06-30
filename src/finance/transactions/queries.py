"""Read-side transaction queries."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from finance.analytics.filters import expense_category_candidate_filters
from finance.currencies import amount_base_expr
from finance.domain.enums import (
    TRANSACTION_DIRECTION_VALUES,
    TransactionDirection,
)
from finance.domain.models import Transaction
from finance.ml.classification.policy import (
    DEFAULT_POLICY,
    ClassificationPolicy,
    decide_classification,
    review_priority_for_decision,
)
from finance.transactions.merchants import (
    load_merchant_alias_maps,
    merchant_display_label,
    merchant_identity,
)
from finance.transactions.normalization import normalize_text

CategoryState = Literal[
    "all",
    "categorized",
    "uncategorized",
    "suggested",
    "assignable",
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
    search: str | None = None
    direction: str | None = None
    category: str | None = None
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


def _category_candidate_conditions():
    return tuple(expense_category_candidate_filters())


def _review_priority(tx: Transaction, policy: ClassificationPolicy) -> int:
    if tx.category is not None:
        return 90
    if tx.category_suggestion_rejected:
        return 80
    decision = decide_classification(
        category=tx.category_predicted,
        confidence=tx.category_confidence,
        direction=tx.direction,
        is_transfer=tx.is_transfer,
        transaction_type=tx.transaction_type,
        policy=policy,
    )
    return review_priority_for_decision(decision)


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
    if filters.search:
        search = filters.search.strip().lower()
        pattern = f"%{search}%"
        search_conditions: list[Any] = [
            func.lower(Transaction.merchant).like(pattern),
            func.lower(Transaction.title).like(pattern),
        ]
        terms = normalize_text(filters.search).split()
        if len(terms) > 1:
            search_conditions.append(
                and_(
                    *[
                        or_(
                            func.lower(Transaction.merchant).like(f"%{term}%"),
                            func.lower(Transaction.title).like(f"%{term}%"),
                        )
                        for term in terms
                    ]
                )
            )
        stmt = stmt.where(
            or_(*search_conditions)
        )
    if filters.direction in TRANSACTION_DIRECTION_VALUES:
        stmt = stmt.where(Transaction.direction == filters.direction)
    if filters.category:
        predicted_match = and_(
            Transaction.category.is_(None),
            Transaction.category_predicted == filters.category,
            *_category_candidate_conditions(),
        )
        if filters.category_state not in {"assignable", "rejected"}:
            predicted_match = and_(
                predicted_match,
                Transaction.category_suggestion_rejected.is_(False),
            )
        stmt = stmt.where(
            or_(Transaction.category == filters.category, predicted_match)
        )
    if filters.transaction_type:
        stmt = stmt.where(Transaction.transaction_type == filters.transaction_type)
    if filters.category_state == "categorized":
        stmt = stmt.where(Transaction.category.is_not(None))
    elif filters.category_state == "uncategorized":
        stmt = stmt.where(Transaction.category.is_(None))
    elif filters.category_state == "suggested":
        stmt = stmt.where(Transaction.category.is_(None))
        stmt = stmt.where(*_category_candidate_conditions())
        stmt = stmt.where(Transaction.category_predicted.is_not(None))
        stmt = stmt.where(Transaction.category_suggestion_rejected.is_(False))
    elif filters.category_state == "assignable":
        stmt = stmt.where(Transaction.category.is_(None))
        stmt = stmt.where(*_category_candidate_conditions())
    elif filters.category_state == "needs_review":
        stmt = stmt.where(Transaction.category.is_(None))
        stmt = stmt.where(*_category_candidate_conditions())
        stmt = stmt.where(Transaction.category_suggestion_rejected.is_(False))
    elif filters.category_state == "rejected":
        stmt = stmt.where(Transaction.category.is_(None))
        stmt = stmt.where(*_category_candidate_conditions())
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
    stmt = stmt.order_by(Transaction.booking_date.desc())
    return stmt


@dataclass(frozen=True)
class FilterSummaryResult:
    count: int
    total_income: Decimal
    total_expenses: Decimal
    net: Decimal


def filter_summary(
    session: Session,
    filters: TransactionFilters,
) -> FilterSummaryResult:
    """Aggregate count + income/expenses/net for the given filter set."""
    base = filtered_transactions_stmt(filters).subquery()
    base_amount = func.coalesce(base.c.amount_base, base.c.amount)
    income_expr = func.coalesce(
        func.sum(
            case(
                (
                    base.c.direction == TransactionDirection.CREDIT.value,
                    func.abs(base_amount),
                ),
                else_=0,
            )
        ),
        0,
    )
    expense_expr = func.coalesce(
        func.sum(
            case(
                (
                    base.c.direction == TransactionDirection.DEBIT.value,
                    func.abs(base_amount),
                ),
                else_=0,
            )
        ),
        0,
    )
    row = session.execute(
        select(
            func.count().label("cnt"),
            income_expr.label("inc"),
            expense_expr.label("exp"),
        ).select_from(base)
    ).one()
    income = Decimal(str(row.inc or 0))
    expenses = Decimal(str(row.exp or 0))
    return FilterSummaryResult(
        count=int(row.cnt or 0),
        total_income=income,
        total_expenses=expenses,
        net=income - expenses,
    )


def list_transactions(
    session: Session,
    filters: TransactionFilters,
    *,
    limit: int,
    offset: int,
    policy: ClassificationPolicy = DEFAULT_POLICY,
) -> list[Transaction]:
    if filters.review_priority:
        rows = list(session.execute(filtered_transactions_stmt(filters)).scalars().all())
        rows.sort(
            key=lambda row: (
                _review_priority(row, policy),
                -row.booking_date.toordinal(),
                -int(row.id or 0),
            )
        )
        return rows[offset : offset + limit]
    stmt = filtered_transactions_stmt(filters).offset(offset).limit(limit)
    return list(session.execute(stmt).scalars().all())


def summary_by_category(
    session: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[CategorySummary]:
    debit = func.sum(
        case(
            (Transaction.direction == TransactionDirection.DEBIT.value, amount_base_expr()),
            else_=0,
        )
    ).label("total_debit")
    credit = func.sum(
        case(
            (
                Transaction.direction == TransactionDirection.CREDIT.value,
                amount_base_expr(),
            ),
            else_=0,
        )
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
    stmt = select(Transaction).where(Transaction.merchant != "")
    if only_uncategorized:
        stmt = stmt.where(Transaction.category.is_(None))
        stmt = stmt.where(*_category_candidate_conditions())
    rows = session.execute(stmt).scalars().all()

    alias_map, label_map = load_merchant_alias_maps(session)
    grouped: dict[str, dict[str, Any]] = {}
    for tx in rows:
        identity = merchant_identity(
            tx.merchant,
            tx.title,
            alias_map=alias_map,
            label_map=label_map,
        )
        if not identity.canonical_key:
            continue
        label = identity.display_label or merchant_display_label(tx.merchant, tx.title)
        group = grouped.setdefault(
            identity.canonical_key,
            {
                "merchant": label,
                "count": 0,
                "total_debit": Decimal(0),
                "total_credit": Decimal(0),
                "titles": [],
                "categories": [],
            },
        )
        group["count"] += 1
        amount = tx.amount_base if tx.amount_base is not None else tx.amount
        if tx.direction == TransactionDirection.DEBIT.value:
            group["total_debit"] += amount or Decimal(0)
        elif tx.direction == TransactionDirection.CREDIT.value:
            group["total_credit"] += amount or Decimal(0)
        if tx.title:
            group["titles"].append(tx.title)
        if tx.category:
            group["categories"].append(tx.category)

    sorted_groups = sorted(
        (
            group
            for group in grouped.values()
            if int(group["count"]) >= min_count
        ),
        key=lambda group: int(group["count"]),
        reverse=True,
    )[:limit]
    out: list[MerchantGroupSummary] = []
    for group in sorted_groups:
        titles = list(dict.fromkeys(str(title) for title in group["titles"] if title))[:3]
        cats = [str(category) for category in group["categories"] if category]
        common_cat = max(set(cats), key=cats.count) if cats else None
        out.append(
            MerchantGroupSummary(
                merchant=str(group["merchant"]),
                count=int(group["count"]),
                total_debit=Decimal(group["total_debit"]),
                total_credit=Decimal(group["total_credit"]),
                common_category=common_cat,
                sample_titles=titles,
            )
        )
    return out
