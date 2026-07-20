"""Read-side transaction queries."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from finance.analytics.filters import expense_category_candidate_filters
from finance.currencies import (
    amount_base_expr,
    amount_base_fields_expr,
    amount_base_value,
)
from finance.domain.enums import (
    TRANSACTION_DIRECTION_VALUES,
    TransactionDirection,
    TransactionType,
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
from finance.transactions.type_decision import (
    TYPE_GOLD_METHODS,
    effective_transaction_type,
    effective_transaction_type_expr,
    fallback_type_expr,
)
from finance.transactions.types import (
    CategorySummary,
    FilterSummaryResult,
    MerchantGroupSortBy,
    MerchantGroupSummary,
    TransactionFilters,
    TransactionSortBy,
    TransactionSortDirection,
)


def _merchant_canonical_key_filter(filters: TransactionFilters) -> str | None:
    value = filters.merchant_canonical_key
    return value.strip() if value else None


def _filter_rows_by_merchant_canonical_key(
    session: Session,
    rows: list[Transaction],
    canonical_key: str | None,
    *,
    alias_map: dict[str, str] | None = None,
    label_map: dict[str, str] | None = None,
) -> list[Transaction]:
    if not canonical_key:
        return rows
    if alias_map is None or label_map is None:
        alias_map, label_map = load_merchant_alias_maps(session)
    return [
        tx
        for tx in rows
        if merchant_identity(
            tx.merchant,
            tx.title,
            alias_map=alias_map,
            label_map=label_map,
        ).canonical_key
        == canonical_key
    ]


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
        transaction_type=effective_transaction_type(tx),
        policy=policy,
    )
    return review_priority_for_decision(decision)


def _transaction_order_by(
    sort_by: TransactionSortBy,
    sort_direction: TransactionSortDirection,
) -> tuple[Any, ...]:
    direction = "asc" if sort_direction == "asc" else "desc"
    if sort_by == "amount":
        amount = amount_base_expr()
        return (
            getattr(amount, direction)().nulls_last(),
            Transaction.booking_date.desc(),
            Transaction.id.desc(),
        )
    return (
        getattr(Transaction.booking_date, direction)(),
        getattr(Transaction.id, direction)(),
    )


def filtered_transactions_stmt(
    filters: TransactionFilters,
    *,
    sort_by: TransactionSortBy = "date",
    sort_direction: TransactionSortDirection = "desc",
):
    stmt = select(Transaction)
    if filters.date_from is not None:
        stmt = stmt.where(Transaction.booking_date >= filters.date_from)
    if filters.date_to is not None:
        stmt = stmt.where(Transaction.booking_date <= filters.date_to)
    if not filters.include_transfers:
        stmt = stmt.where(
            Transaction.is_transfer.is_(False),
            effective_transaction_type_expr() != TransactionType.OWN_TRANSFER.value,
        )
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
    absolute_amount = func.abs(amount_base_expr())
    if filters.min_amount is not None:
        stmt = stmt.where(absolute_amount >= filters.min_amount)
    if filters.max_amount is not None:
        stmt = stmt.where(absolute_amount <= filters.max_amount)
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
        if filters.transaction_type_state in {"needs_review", "suggested"}:
            stmt = stmt.where(
                Transaction.transaction_type_predicted == filters.transaction_type
            )
        else:
            stmt = stmt.where(
                effective_transaction_type_expr() == filters.transaction_type
            )
    if filters.transaction_type_state == "confirmed":
        stmt = stmt.where(
            Transaction.transaction_type_confirmation_method.in_(TYPE_GOLD_METHODS)
        )
    elif filters.transaction_type_state == "provisional":
        stmt = stmt.where(
            Transaction.transaction_type_confirmation_method.is_(None)
        )
    elif filters.transaction_type_state == "needs_review":
        stmt = stmt.where(
            Transaction.transaction_type_confirmation_method.is_(None),
            Transaction.transaction_type_predicted.is_not(None),
            Transaction.transaction_type_predicted != fallback_type_expr(),
        )
    elif filters.transaction_type_state == "suggested":
        stmt = stmt.where(Transaction.transaction_type_predicted.is_not(None))
        stmt = stmt.where(
            Transaction.transaction_type_predicted != fallback_type_expr(),
        )
    if filters.transaction_type_source:
        stmt = stmt.where(
            func.coalesce(
                Transaction.transaction_type_source,
                Transaction.transaction_type_predicted_source,
            )
            == filters.transaction_type_source
        )
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
    stmt = stmt.order_by(*_transaction_order_by(sort_by, sort_direction))
    return stmt


def filter_summary(
    session: Session,
    filters: TransactionFilters,
) -> FilterSummaryResult:
    """Aggregate count + income/expenses/net for the given filter set."""
    canonical_key = _merchant_canonical_key_filter(filters)
    if canonical_key:
        rows = _filter_rows_by_merchant_canonical_key(
            session,
            list(session.execute(filtered_transactions_stmt(filters)).scalars().all()),
            canonical_key,
        )
        income = Decimal(0)
        expenses = Decimal(0)
        unconverted_count = 0
        for row in rows:
            amount = amount_base_value(row)
            if amount is None:
                unconverted_count += 1
                continue
            value = abs(amount)
            if row.direction == TransactionDirection.CREDIT.value:
                income += value
            elif row.direction == TransactionDirection.DEBIT.value:
                expenses += value
        return FilterSummaryResult(
            count=len(rows),
            total_income=income,
            total_expenses=expenses,
            net=income - expenses,
            unconverted_count=unconverted_count,
        )

    base = filtered_transactions_stmt(filters).subquery()
    base_amount = amount_base_fields_expr(
        currency=base.c.currency,
        amount=base.c.amount,
        amount_base=base.c.amount_base,
        base_currency=base.c.base_currency,
        fx_rate=base.c.fx_rate,
    )
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
    aggregate_row = session.execute(
        select(
            func.count().label("cnt"),
            income_expr.label("inc"),
            expense_expr.label("exp"),
            func.sum(case((base_amount.is_(None), 1), else_=0)).label(
                "unconverted"
            ),
        ).select_from(base)
    ).one()
    income = Decimal(str(aggregate_row.inc or 0))
    expenses = Decimal(str(aggregate_row.exp or 0))
    return FilterSummaryResult(
        count=int(aggregate_row.cnt or 0),
        total_income=income,
        total_expenses=expenses,
        net=income - expenses,
        unconverted_count=int(aggregate_row.unconverted or 0),
    )


def list_transactions(
    session: Session,
    filters: TransactionFilters,
    *,
    limit: int,
    offset: int,
    policy: ClassificationPolicy = DEFAULT_POLICY,
    sort_by: TransactionSortBy = "date",
    sort_direction: TransactionSortDirection = "desc",
) -> list[Transaction]:
    canonical_key = _merchant_canonical_key_filter(filters)
    if filters.review_priority:
        rows = list(session.execute(filtered_transactions_stmt(filters)).scalars().all())
        rows = _filter_rows_by_merchant_canonical_key(session, rows, canonical_key)
        rows.sort(
            key=lambda row: (
                _review_priority(row, policy),
                -row.booking_date.toordinal(),
                -int(row.id or 0),
            )
        )
        return rows[offset : offset + limit]
    if sort_by == "merchant":
        rows = list(session.execute(filtered_transactions_stmt(filters)).scalars().all())
        alias_map, label_map = load_merchant_alias_maps(session)
        rows = _filter_rows_by_merchant_canonical_key(
            session,
            rows,
            canonical_key,
            alias_map=alias_map,
            label_map=label_map,
        )

        def merchant_sort_key(row: Transaction) -> tuple[str, str]:
            display_label = merchant_identity(
                row.merchant,
                row.title,
                alias_map=alias_map,
                label_map=label_map,
            ).display_label
            return normalize_text(display_label), display_label.casefold()

        rows.sort(
            key=merchant_sort_key,
            reverse=sort_direction == "desc",
        )
        return rows[offset : offset + limit]
    if canonical_key:
        rows = _filter_rows_by_merchant_canonical_key(
            session,
            list(session.execute(filtered_transactions_stmt(filters)).scalars().all()),
            canonical_key,
        )
        return rows[offset : offset + limit]
    stmt = (
        filtered_transactions_stmt(
            filters,
            sort_by=sort_by,
            sort_direction=sort_direction,
        )
        .offset(offset)
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())


def matching_transactions(
    session: Session,
    filters: TransactionFilters,
) -> list[Transaction]:
    """Return all transactions matching filters, including canonical merchant filters."""
    rows = list(session.execute(filtered_transactions_stmt(filters)).scalars().all())
    return _filter_rows_by_merchant_canonical_key(
        session,
        rows,
        _merchant_canonical_key_filter(filters),
    )


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

    stmt = (
        select(Transaction.category, debit, credit, tx_count)
        .where(amount_base_expr().is_not(None))
        .group_by(Transaction.category)
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
    sort_by: MerchantGroupSortBy = "count",
    sort_direction: TransactionSortDirection = "desc",
) -> list[MerchantGroupSummary]:
    stmt = select(Transaction).where(
        Transaction.merchant != "",
        amount_base_expr().is_not(None),
    )
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
                "merchant_display": label,
                "merchant_canonical_key": identity.canonical_key,
                "count": 0,
                "total_debit": Decimal(0),
                "total_credit": Decimal(0),
                "merchants": [],
                "titles": [],
                "categories": [],
            },
        )
        group["count"] += 1
        amount = amount_base_value(tx)
        if amount is not None:
            if tx.direction == TransactionDirection.DEBIT.value:
                group["total_debit"] += amount
            elif tx.direction == TransactionDirection.CREDIT.value:
                group["total_credit"] += amount
        if tx.merchant:
            group["merchants"].append(tx.merchant)
        if tx.title:
            group["titles"].append(tx.title)
        if tx.category:
            group["categories"].append(tx.category)

    eligible_groups = [
        group for group in grouped.values() if int(group["count"]) >= min_count
    ]
    for group in eligible_groups:
        categories = [
            str(category) for category in group["categories"] if category
        ]
        group["common_category"] = (
            max(set(categories), key=lambda value: (categories.count(value), value))
            if categories
            else None
        )

    def sort_value(group: dict[str, Any]) -> str | int | Decimal:
        if sort_by == "merchant":
            return str(group["merchant_display"]).casefold()
        if sort_by == "amount":
            return abs(Decimal(group["total_credit"])) - abs(
                Decimal(group["total_debit"])
            )
        return int(group["count"])

    # A stable first pass keeps ties deterministic without reversing the
    # canonical-key order when the primary direction changes.
    eligible_groups.sort(key=lambda group: str(group["merchant_canonical_key"]))
    eligible_groups.sort(
        key=sort_value,
        reverse=sort_direction == "desc",
    )
    sorted_groups = eligible_groups[:limit]
    out: list[MerchantGroupSummary] = []
    for group in sorted_groups:
        merchants = list(
            dict.fromkeys(
                str(merchant) for merchant in group["merchants"] if merchant
            )
        )[:3]
        titles = list(dict.fromkeys(str(title) for title in group["titles"] if title))[:3]
        out.append(
            MerchantGroupSummary(
                merchant=str(group["merchant"]),
                merchant_display=str(group["merchant_display"]),
                merchant_canonical_key=str(group["merchant_canonical_key"]),
                count=int(group["count"]),
                total_debit=Decimal(group["total_debit"]),
                total_credit=Decimal(group["total_credit"]),
                common_category=(
                    str(group["common_category"])
                    if group["common_category"] is not None
                    else None
                ),
                sample_merchants=merchants,
                sample_titles=titles,
            )
        )
    return out
