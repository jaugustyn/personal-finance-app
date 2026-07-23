"""Use cases for accepting, rejecting and restoring category suggestions."""
from __future__ import annotations

from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.db import command_transaction
from finance.domain.enums import (
    CategoryConfirmationMethod,
    CategorySource,
)
from finance.domain.models import Transaction
from finance.ml.classification.policy import (
    DEFAULT_POLICY,
    ClassificationPolicy,
    decide_classification,
)
from finance.ml.feedback import (
    EVENT_ACCEPT_SUGGESTION,
    EVENT_REJECT_SUGGESTION,
    record_transaction_feedback,
)
from finance.transactions.category_provenance import clear_suggestion, confirm_category
from finance.transactions.mutation_rules import can_assign_expense_category
from finance.transactions.type_decision import (
    TYPE_CONFIRMATION_ACCEPTED,
    effective_transaction_type,
)
from finance.transactions.type_service import TransactionTypeService


class SuggestionAcceptanceService:
    """Handles review actions for ML category suggestions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def accept_suggestions(
        self,
        *,
        ids: list[int] | None,
        min_confidence: float,
        policy: ClassificationPolicy = DEFAULT_POLICY,
        manual: bool = False,
    ) -> int:
        with command_transaction(self.session):
            return self._accept_suggestions(
                ids=ids,
                min_confidence=min_confidence,
                policy=policy,
                manual=manual,
            )

    def _accept_suggestions(
        self,
        *,
        ids: list[int] | None,
        min_confidence: float,
        policy: ClassificationPolicy,
        manual: bool,
    ) -> int:
        if manual and not ids:
            return 0
        rows = self._suggestion_rows(ids=ids, rejected=False)
        affected = 0
        for tx in rows:
            if not can_assign_expense_category(tx):
                continue
            decision = decide_classification(
                category=tx.category_predicted,
                confidence=tx.category_confidence,
                direction=tx.direction,
                is_transfer=tx.is_transfer,
                transaction_type=effective_transaction_type(tx),
                policy=policy,
            )
            if decision.action != "accept" and not manual:
                continue
            if (
                not manual
                and tx.category_confidence is not None
                and min_confidence > decision.threshold_used
                and tx.category_confidence < min_confidence
            ):
                continue
            self._accept(tx)
            affected += 1
        return affected

    def reject_suggestions(self, *, ids: list[int] | None) -> int:
        with command_transaction(self.session):
            return self._reject_suggestions(ids=ids)

    def _reject_suggestions(self, *, ids: list[int] | None) -> int:
        rows = self._suggestion_rows(ids=ids, rejected=False)
        affected = 0
        for tx in rows:
            if not can_assign_expense_category(tx):
                continue
            record_transaction_feedback(
                self.session,
                tx,
                event_type=EVENT_REJECT_SUGGESTION,
                final_category=None,
            )
            tx_model = cast(Any, tx)
            tx_model.category_suggestion_rejected = True
            affected += 1
        return affected

    def restore_suggestions(self, *, ids: list[int] | None) -> int:
        with command_transaction(self.session):
            return self._restore_suggestions(ids=ids)

    def _restore_suggestions(self, *, ids: list[int] | None) -> int:
        rows = self._suggestion_rows(ids=ids, rejected=True)
        affected = 0
        for tx in rows:
            if not can_assign_expense_category(tx):
                continue
            tx_model = cast(Any, tx)
            tx_model.category_suggestion_rejected = False
            affected += 1
        return affected

    def _suggestion_rows(
        self,
        *,
        ids: list[int] | None,
        rejected: bool,
    ) -> list[Transaction]:
        stmt = select(Transaction).where(Transaction.category.is_(None))
        stmt = stmt.where(Transaction.category_predicted.is_not(None))
        stmt = stmt.where(Transaction.category_suggestion_rejected.is_(rejected))
        stmt = stmt.where(Transaction.is_transfer.is_(False))
        if ids:
            stmt = stmt.where(Transaction.id.in_(ids))
        return list(self.session.execute(stmt).scalars().all())

    def _accept(self, tx: Transaction) -> None:
        TransactionTypeService(self.session).confirm_from_category(
            tx,
            confirmation_method=TYPE_CONFIRMATION_ACCEPTED,
        )
        record_transaction_feedback(
            self.session,
            tx,
            event_type=EVENT_ACCEPT_SUGGESTION,
            final_category=str(tx.category_predicted),
            previous_category=str(tx.category) if tx.category else None,
            confirmation_method=CategoryConfirmationMethod.ACCEPTED_SUGGESTION.value,
            origin_ref=tx.category_predicted_ref,
        )
        confirm_category(
            tx,
            category=str(tx.category_predicted),
            source=tx.category_predicted_source or CategorySource.MODEL.value,
            method=CategoryConfirmationMethod.ACCEPTED_SUGGESTION,
            origin_ref=tx.category_predicted_ref,
        )
        clear_suggestion(tx)
