"""Use cases for manual category assignment."""
from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.domain.enums import CategoryConfirmationMethod, CategorySource, TransactionType
from finance.domain.models import Transaction
from finance.ml.classification.evaluation_sets import invalidate_for_label_change
from finance.ml.feedback import (
    EVENT_MANUAL_CATEGORY,
    EVENT_MANUAL_CLEAR,
    record_transaction_feedback,
)
from finance.profile.service import remember_merchant_category
from finance.transactions.category_provenance import (
    clear_confirmation,
    clear_suggestion,
    confirm_category,
)
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
        self.apply_manual_decision(
            tx,
            category,
            subcategory=subcategory,
            remember_rule=remember_rule,
        )
        self.session.commit()
        self.session.refresh(tx)
        return tx

    def apply_manual_decision(
        self,
        tx: Transaction,
        category: str | None,
        *,
        subcategory: str | None = None,
        remember_rule: bool = False,
    ) -> None:
        """Apply and audit a manual category decision without committing."""
        category, subcategory = resolve_category_assignment(
            self.session, category, subcategory
        )
        if category is not None:
            TransactionTypeService(self.session).confirm_from_category(
                tx,
                confirmation_method=CategoryConfirmationMethod.MANUAL.value,
            )
        if category is not None and not can_assign_expense_category(tx):
            raise InvalidCategoryAssignment(
                "Category can only be assigned to expenses or refunds."
            )

        previous_prediction = tx.category_predicted
        previous_category = tx.category
        previous_category_value = str(previous_category) if previous_category else None
        decision_changed = (
            previous_category_value != category
            or tx.subcategory != subcategory
            or (
                category is not None
                and tx.category_confirmation_method
                != CategoryConfirmationMethod.MANUAL.value
            )
        )
        if previous_category_value != category:
            invalidate_for_label_change(self.session, tx.id)
        if decision_changed:
            self.apply_manual_category(tx, category, subcategory=subcategory)

        if category is not None and decision_changed:
            record_transaction_feedback(
                self.session,
                tx,
                event_type=EVENT_MANUAL_CATEGORY,
                final_category=category,
                previous_category=str(previous_category) if previous_category else None,
                confirmation_method=CategoryConfirmationMethod.MANUAL.value,
                source=CategorySource.MANUAL.value,
            )
            if remember_rule:
                remember_merchant_category(
                    self.session, merchant=tx.merchant, category=category
                )
        elif category is None and (
            previous_prediction is not None or previous_category is not None
        ):
            record_transaction_feedback(
                self.session,
                tx,
                event_type=EVENT_MANUAL_CLEAR,
                final_category=None,
                previous_category=str(previous_category) if previous_category else None,
            )
        clear_suggestion(tx)

    def bulk_categorize(
        self,
        *,
        ids: list[int] | None,
        merchant: str | None,
        category: str | None | object,
        merchant_canonical_key: str | None = None,
        mark_transfer: bool | None = None,
        transaction_type: str | None = None,
        allow_direction_mismatch: bool = False,
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
            previous_category = str(tx.category) if tx.category else None
            if mark_transfer is not None:
                type_service.apply_transfer_marker(tx, mark_transfer)
                changed = True
            if tx_type_value is not None:
                type_service.apply_manual_type(
                    tx,
                    tx_type_value,
                    allow_direction_mismatch=allow_direction_mismatch,
                )
                changed = True

            if category is unchanged:
                affected += int(changed)
                continue
            if category is None:
                if previous_category is not None:
                    invalidate_for_label_change(self.session, tx.id)
                self.clear_manual_category(tx)
                if previous_category is not None:
                    record_transaction_feedback(
                        self.session,
                        tx,
                        event_type=EVENT_MANUAL_CLEAR,
                        final_category=None,
                        previous_category=previous_category,
                    )
                changed = True
                affected += int(changed)
                continue
            type_service.confirm_from_category(
                tx,
                confirmation_method=CategoryConfirmationMethod.MANUAL.value,
            )
            if not can_assign_expense_category(tx):
                affected += int(changed)
                continue
            if previous_category != cast(str, category):
                invalidate_for_label_change(self.session, tx.id)
            self.apply_manual_category(tx, cast(str, category), subcategory=None)
            record_transaction_feedback(
                self.session,
                tx,
                event_type=EVENT_MANUAL_CATEGORY,
                final_category=cast(str, category),
                previous_category=previous_category,
                confirmation_method=CategoryConfirmationMethod.MANUAL.value,
                source=CategorySource.MANUAL.value,
            )
            clear_suggestion(tx)
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
        tx_model.subcategory = subcategory if category is not None else None
        if category is not None:
            confirm_category(
                tx,
                category=category,
                source=CategorySource.MANUAL.value,
                method=CategoryConfirmationMethod.MANUAL,
                origin_ref=None,
            )
        else:
            clear_confirmation(tx)

    @staticmethod
    def clear_manual_category(tx: Transaction) -> None:
        tx_model = cast(Any, tx)
        clear_confirmation(tx)
        tx_model.subcategory = None
