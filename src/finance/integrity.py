"""Read-only integrity checks for locally stored finance data."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from finance.categories import missing_system_category_names
from finance.currencies import BASE_CURRENCY, amount_base_expr
from finance.domain.enums import (
    CATEGORY_CONFIRMATION_METHOD_VALUES,
    CategoryConfirmationMethod,
    TransactionType,
)
from finance.domain.models import Transaction, UserProfile
from finance.transactions.type_decision import (
    TYPE_CONFIRMATION_ACCEPTED,
    TYPE_GOLD_METHODS,
    effective_transaction_type_expr,
)

SAMPLE_LIMIT = 5


@dataclass(frozen=True)
class IntegrityIssue:
    code: str
    count: int
    sample_ids: tuple[int, ...]


def _transaction_issue(
    session: Session,
    *,
    code: str,
    condition: Any,
) -> IntegrityIssue | None:
    count = int(
        session.scalar(
            select(func.count()).select_from(Transaction).where(condition)
        )
        or 0
    )
    if not count:
        return None
    sample_ids = tuple(
        int(value)
        for value in session.scalars(
            select(Transaction.id)
            .where(condition)
            .order_by(Transaction.id)
            .limit(SAMPLE_LIMIT)
        )
    )
    return IntegrityIssue(code=code, count=count, sample_ids=sample_ids)


def check_data_integrity(session: Session) -> list[IntegrityIssue]:
    """Return actionable aggregate issues without exposing transaction contents."""

    issues: list[IntegrityIssue] = []

    missing_categories = missing_system_category_names(session)
    if missing_categories:
        issues.append(
            IntegrityIssue(
                code="missing_system_categories",
                count=len(missing_categories),
                sample_ids=(),
            )
        )

    foreign_invalid = _transaction_issue(
        session,
        code="invalid_or_missing_fx_conversion",
        condition=and_(
            func.upper(Transaction.currency) != BASE_CURRENCY,
            or_(
                amount_base_expr().is_(None),
                func.abs(
                    Transaction.amount_base
                    - (Transaction.amount * Transaction.fx_rate)
                )
                > 0.011,
            ),
        ),
    )
    if foreign_invalid:
        issues.append(foreign_invalid)

    non_pln_base = _transaction_issue(
        session,
        code="transaction_base_currency_not_pln",
        condition=and_(
            Transaction.base_currency.is_not(None),
            func.upper(Transaction.base_currency) != BASE_CURRENCY,
        ),
    )
    if non_pln_base:
        issues.append(non_pln_base)

    duplicate_hashes = (
        select(Transaction.dedup_hash)
        .group_by(Transaction.dedup_hash)
        .having(func.count(Transaction.id) > 1)
    )
    duplicate_rows = _transaction_issue(
        session,
        code="duplicate_dedup_hash",
        condition=Transaction.dedup_hash.in_(duplicate_hashes),
    )
    if duplicate_rows:
        issues.append(duplicate_rows)

    incomplete_category = _transaction_issue(
        session,
        code="incomplete_confirmed_category_provenance",
        condition=and_(
            Transaction.category.is_not(None),
            Transaction.category_confirmation_method.in_(
                CATEGORY_CONFIRMATION_METHOD_VALUES
            ),
            or_(
                Transaction.category_confirmed_at.is_(None),
                Transaction.category_source.is_(None),
                and_(
                    Transaction.category_confirmation_method
                    == CategoryConfirmationMethod.ACCEPTED_SUGGESTION.value,
                    Transaction.category_origin_ref.is_(None),
                ),
            ),
        ),
    )
    if incomplete_category:
        issues.append(incomplete_category)

    incomplete_type = _transaction_issue(
        session,
        code="incomplete_confirmed_transaction_type_provenance",
        condition=and_(
            Transaction.transaction_type.is_not(None),
            Transaction.transaction_type_confirmation_method.in_(TYPE_GOLD_METHODS),
            or_(
                Transaction.transaction_type_confirmed_at.is_(None),
                Transaction.transaction_type_source.is_(None),
                and_(
                    Transaction.transaction_type_confirmation_method
                    == TYPE_CONFIRMATION_ACCEPTED,
                    Transaction.transaction_type_origin_ref.is_(None),
                ),
            ),
        ),
    )
    if incomplete_type:
        issues.append(incomplete_type)

    effective_type = effective_transaction_type_expr()
    transfer_mismatch = _transaction_issue(
        session,
        code="transfer_marker_mismatch",
        condition=or_(
            and_(
                Transaction.is_transfer.is_(True),
                effective_type != TransactionType.OWN_TRANSFER.value,
            ),
            and_(
                Transaction.is_transfer.is_(False),
                effective_type == TransactionType.OWN_TRANSFER.value,
            ),
        ),
    )
    if transfer_mismatch:
        issues.append(transfer_mismatch)

    profile_ids = tuple(
        int(value)
        for value in session.scalars(
            select(UserProfile.id).where(
                func.upper(UserProfile.base_currency) != BASE_CURRENCY
            )
        )
    )
    if profile_ids:
        issues.append(
            IntegrityIssue(
                code="profile_base_currency_not_pln",
                count=len(profile_ids),
                sample_ids=profile_ids[:SAMPLE_LIMIT],
            )
        )

    return issues
