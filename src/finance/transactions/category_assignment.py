"""Use cases for manual category assignment."""
from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.domain.enums import CategorySource, TransactionType
from finance.domain.models import Transaction
from finance.ml.feedback import (
    EVENT_MANUAL_CATEGORY,
    EVENT_MANUAL_CLEAR,
    record_transaction_feedback,
)
from finance.profile.service import remember_merchant_category
from finance.transactions.merchants import load_merchant_alias_maps, merchant_identity
from finance.transactions.mutation_rules import (
    InvalidCategoryAssignment,
    can_assign_expense_category,
    resolve_category_assignment,
)
from finance.transactions.type_service import TransactionTypeService


class CategoryAssignmentService:
    """Handles manual category changes and related feedback side effects."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def update_category(
        self,
        tx_id: int,
        category: str | None,
        *,
        subcategory: str | None = None,
        remember_rule: bool = False,
    ) -> Transaction | None:
        tx = self.session.get(Transaction, tx_id)
        if tx is None:
            return None
        category, subcategory = resolve_category_assignment(
            self.session, category, subcategory
        )
        if category is not None and not can_assign_expense_category(tx):
            raise InvalidCategoryAssignment(
                "Category can only be assigned to debit expense transactions."
            )

        previous_prediction = tx.category_predicted
        previous_category = tx.category
        self.apply_manual_category(tx, category, subcategory=subcategory)

        if category is not None:
            record_transaction_feedback(
                self.session,
                tx,
                event_type=EVENT_MANUAL_CATEGORY,
                final_category=category,
            )
            if remember_rule:
                remember_merchant_category(
                    self.session, merchant=tx.merchant, category=category
                )
        elif previous_prediction is not None or previous_category is not None:
            record_transaction_feedback(
                self.session,
                tx,
                event_type=EVENT_MANUAL_CLEAR,
                final_category=None,
            )

        self.session.commit()
        self.session.refresh(tx)
        return tx

    def bulk_categorize(
        self,
        *,
        ids: list[int] | None,
        merchant: str | None,
        category: str | None | object,
        merchant_canonical_key: str | None = None,
        mark_transfer: bool | None = None,
        transaction_type: str | None = None,
        unchanged: object,
    ) -> int:
        tx_type_value: str | None = None
        if transaction_type is not None:
            tx_type_value = TransactionType(transaction_type).value

        stmt = select(Transaction)
        if ids:
            stmt = stmt.where(Transaction.id.in_(ids))
        if merchant:
            stmt = stmt.where(Transaction.merchant == merchant)
        rows = self.session.execute(stmt).scalars().all()
        canonical_key = (
            merchant_canonical_key.strip() if merchant_canonical_key else None
        )
        if canonical_key:
            alias_map, label_map = load_merchant_alias_maps(self.session)
            rows = [
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

        type_service = TransactionTypeService(self.session)
        affected = 0
        for tx in rows:
            changed = False
            if mark_transfer is not None:
                type_service.apply_transfer_marker(tx, mark_transfer)
                changed = True
            if tx_type_value is not None:
                type_service.apply_transaction_type(tx, tx_type_value)
                changed = True

            if category is unchanged:
                affected += int(changed)
                continue
            if category is None:
                self.clear_manual_category(tx)
                changed = True
                affected += int(changed)
                continue
            if not can_assign_expense_category(tx):
                affected += int(changed)
                continue
            self.apply_manual_category(tx, cast(str, category), subcategory=None)
            changed = True
            affected += int(changed)

        self.session.commit()
        return affected

    @staticmethod
    def apply_manual_category(
        tx: Transaction,
        category: str | None,
        *,
        subcategory: str | None,
    ) -> None:
        tx_model = cast(Any, tx)
        tx_model.category = category
        tx_model.subcategory = subcategory if category is not None else None
        tx_model.category_source = (
            CategorySource.MANUAL.value if category is not None else None
        )
        if category is not None:
            tx_model.category_suggestion_rejected = False

    @staticmethod
    def clear_manual_category(tx: Transaction) -> None:
        tx_model = cast(Any, tx)
        tx_model.category = None
        tx_model.subcategory = None
        tx_model.category_source = None
