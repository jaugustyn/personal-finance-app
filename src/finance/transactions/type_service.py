"""Use cases for transaction-type decisions and review."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.domain.enums import CategorySource, TransactionDirection, TransactionType
from finance.domain.models import Transaction
from finance.ml.classification.evaluation_sets import invalidate_for_label_change
from finance.ml.feedback import (
    EVENT_ACCEPT_TRANSACTION_TYPE,
    EVENT_AUTO_TRANSACTION_TYPE,
    EVENT_MANUAL_CLEAR,
    EVENT_MANUAL_TRANSACTION_TYPE,
    FeedbackEventInput,
    record_feedback_event,
    record_transaction_feedback,
)
from finance.transactions.mutation_rules import (
    can_assign_expense_category,
    clear_category_state,
)
from finance.transactions.type_decision import (
    TYPE_CONFIRMATION_ACCEPTED,
    TYPE_CONFIRMATION_MANUAL,
    TYPE_GOLD_METHODS,
    TransactionTypeDecision,
    direction_matches,
    fallback_type,
)


class TransactionTypeDirectionMismatch(ValueError):
    """Raised when a manual type is unusual for the transaction direction."""


class TransactionTypeService:
    """Applies type changes while preserving confirmed user decisions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def update_transaction_type(
        self,
        tx_id: int,
        transaction_type: str,
        *,
        allow_direction_mismatch: bool = False,
    ) -> Transaction | None:
        try:
            value = TransactionType(transaction_type).value
        except ValueError:
            return None
        tx = self.session.get(Transaction, tx_id)
        if tx is None:
            return None
        self.apply_manual_type(
            tx,
            value,
            allow_direction_mismatch=allow_direction_mismatch,
        )
        self.session.commit()
        self.session.refresh(tx)
        return tx

    def apply_manual_type(
        self,
        tx: Transaction,
        value: str,
        *,
        allow_direction_mismatch: bool = False,
    ) -> None:
        value = TransactionType(value).value
        if not allow_direction_mismatch and not direction_matches(value, tx.direction):
            raise TransactionTypeDirectionMismatch(
                f"{value!r} is unusual for direction {str(tx.direction)!r}."
            )
        previous = str(tx.transaction_type) if tx.transaction_type else None
        predicted = (
            str(tx.transaction_type_predicted) if tx.transaction_type_predicted else None
        )
        corrected_source = (
            tx.transaction_type_predicted_source
            or tx.transaction_type_source
            or CategorySource.MANUAL.value
        )
        corrected_ref = (
            tx.transaction_type_predicted_ref or tx.transaction_type_origin_ref
        )
        self._set_current(
            tx,
            value=value,
            source=CategorySource.MANUAL.value,
            confirmation_method=TYPE_CONFIRMATION_MANUAL,
            origin_ref=None,
        )
        self._clear_suggestion(tx)
        self._record(
            tx,
            event_type=EVENT_MANUAL_TRANSACTION_TYPE,
            previous=previous,
            predicted=predicted,
            final=value,
            source=corrected_source,
            confirmation_method=TYPE_CONFIRMATION_MANUAL,
            origin_ref=corrected_ref,
        )

    def apply_transaction_type(self, tx: Transaction, value: str) -> None:
        """Compatibility alias for existing bulk mutation callers."""
        self.apply_manual_type(tx, value)

    def accept_suggestion(self, tx_id: int) -> Transaction | None:
        tx = self.session.get(Transaction, tx_id)
        if tx is None or not self._accept_provisional(tx):
            return None
        self.session.commit()
        self.session.refresh(tx)
        return tx

    def _accept_provisional(self, tx: Transaction) -> bool:
        if tx.transaction_type_confirmation_method in TYPE_GOLD_METHODS:
            return False
        if tx.transaction_type_predicted is not None:
            value = TransactionType(str(tx.transaction_type_predicted)).value
            source = tx.transaction_type_predicted_source
            origin_ref = tx.transaction_type_predicted_ref
            confidence = tx.transaction_type_confidence
        elif tx.transaction_type is not None:
            value = TransactionType(str(tx.transaction_type)).value
            source = tx.transaction_type_source
            origin_ref = tx.transaction_type_origin_ref
            confidence = None
        else:
            return False
        previous = str(tx.transaction_type) if tx.transaction_type else None
        self._set_current(
            tx,
            value=value,
            source=source,
            confirmation_method=TYPE_CONFIRMATION_ACCEPTED,
            origin_ref=origin_ref,
        )
        self._clear_suggestion(tx)
        self._record(
            tx,
            event_type=EVENT_ACCEPT_TRANSACTION_TYPE,
            previous=previous,
            predicted=value,
            final=value,
            source=source,
            confirmation_method=TYPE_CONFIRMATION_ACCEPTED,
            origin_ref=origin_ref,
            confidence=confidence,
        )
        return True

    def accept_suggestions(self, *, ids: list[int] | None) -> int:
        if not ids:
            return 0
        stmt = select(Transaction).where(
            Transaction.id.in_(ids),
            Transaction.transaction_type_confirmation_method.is_(None),
            (
                Transaction.transaction_type_predicted.is_not(None)
                | Transaction.transaction_type.is_not(None)
            ),
        )
        rows = list(self.session.execute(stmt).scalars())
        affected = 0
        for tx in rows:
            if not self._accept_provisional(tx):
                continue
            affected += 1
        self.session.commit()
        return affected

    def apply_decision(self, tx: Transaction, decision: TransactionTypeDecision) -> bool:
        """Apply an automatic decision without touching gold labels."""
        if tx.transaction_type_confirmation_method in TYPE_GOLD_METHODS:
            return False
        previous = str(tx.transaction_type) if tx.transaction_type else None
        previous_prediction = (
            str(tx.transaction_type_predicted) if tx.transaction_type_predicted else None
        )
        if decision.mode == "auto_apply":
            self._set_current(
                tx,
                value=decision.value,
                source=decision.source,
                confirmation_method=None,
                origin_ref=decision.origin_ref,
            )
            self._clear_suggestion(tx)
        else:
            tx_model = cast(Any, tx)
            tx_model.transaction_type = None
            tx_model.transaction_type_source = None
            tx_model.transaction_type_origin_ref = None
            tx_model.transaction_type_confirmed_at = None
            tx_model.transaction_type_confirmation_method = None
            tx_model.transaction_type_predicted = decision.value
            tx_model.transaction_type_confidence = decision.confidence
            tx_model.transaction_type_predicted_source = decision.source
            tx_model.transaction_type_predicted_ref = decision.origin_ref
            tx_model.is_transfer = False
        changed = (
            previous != (decision.value if decision.mode == "auto_apply" else None)
            or previous_prediction
            != (decision.value if decision.mode == "suggest_only" else None)
        )
        if changed:
            self._record(
                tx,
                event_type=EVENT_AUTO_TRANSACTION_TYPE,
                previous=previous,
                predicted=(decision.value if decision.mode == "suggest_only" else None),
                final=(decision.value if decision.mode == "auto_apply" else previous),
                source=decision.source,
                origin_ref=decision.origin_ref,
                confidence=decision.confidence,
            )
        return changed

    def apply_transfer_marker(self, tx: Transaction, mark_transfer: bool) -> None:
        value = (
            TransactionType.OWN_TRANSFER.value
            if mark_transfer
            else fallback_type(tx.direction)
        )
        self.apply_manual_type(tx, value)

    def confirm_from_category(
        self,
        tx: Transaction,
        *,
        confirmation_method: str,
    ) -> None:
        value = (
            TransactionType.REFUND.value
            if str(tx.direction) == TransactionDirection.CREDIT.value
            else TransactionType.EXPENSE.value
        )
        if (
            str(tx.transaction_type or "") == value
            and tx.transaction_type_confirmation_method in TYPE_GOLD_METHODS
        ):
            return
        previous = str(tx.transaction_type) if tx.transaction_type else None
        predicted = (
            str(tx.transaction_type_predicted) if tx.transaction_type_predicted else None
        )
        self._set_current(
            tx,
            value=value,
            source=CategorySource.MANUAL.value,
            confirmation_method=confirmation_method,
            origin_ref=None,
        )
        self._clear_suggestion(tx)
        self._record(
            tx,
            event_type=(
                EVENT_ACCEPT_TRANSACTION_TYPE
                if confirmation_method == TYPE_CONFIRMATION_ACCEPTED
                else EVENT_MANUAL_TRANSACTION_TYPE
            ),
            previous=previous,
            predicted=predicted,
            final=value,
            source=CategorySource.MANUAL.value,
            confirmation_method=confirmation_method,
        )

    def _set_current(
        self,
        tx: Transaction,
        *,
        value: str,
        source: str | None,
        confirmation_method: str | None,
        origin_ref: str | None,
    ) -> None:
        tx_model = cast(Any, tx)
        tx_model.transaction_type = value
        tx_model.transaction_type_source = source
        tx_model.transaction_type_confirmation_method = confirmation_method
        tx_model.transaction_type_confirmed_at = (
            datetime.now(UTC) if confirmation_method in TYPE_GOLD_METHODS else None
        )
        tx_model.transaction_type_origin_ref = origin_ref
        tx_model.is_transfer = value == TransactionType.OWN_TRANSFER.value
        self._clear_incompatible_category(tx)

    @staticmethod
    def _clear_suggestion(tx: Transaction) -> None:
        tx_model = cast(Any, tx)
        tx_model.transaction_type_predicted = None
        tx_model.transaction_type_confidence = None
        tx_model.transaction_type_predicted_source = None
        tx_model.transaction_type_predicted_ref = None

    def _clear_incompatible_category(self, tx: Transaction) -> None:
        if can_assign_expense_category(tx):
            return
        previous_category = str(tx.category) if tx.category else None
        if previous_category is not None:
            invalidate_for_label_change(self.session, tx.id)
            record_transaction_feedback(
                self.session,
                tx,
                event_type=EVENT_MANUAL_CLEAR,
                final_category=None,
                previous_category=previous_category,
                origin_ref=tx.category_origin_ref,
                source=tx.category_source,
            )
        clear_category_state(tx)

    def _record(
        self,
        tx: Transaction,
        *,
        event_type: str,
        previous: str | None,
        predicted: str | None,
        final: str | None,
        source: str | None,
        confirmation_method: str | None = None,
        origin_ref: str | None = None,
        confidence: float | None = None,
    ) -> None:
        record_feedback_event(
            self.session,
            FeedbackEventInput(
                transaction_id=tx.id,
                entity_type="transaction_type",
                entity_key=str(tx.id),
                event_type=event_type,
                predicted_transaction_type=predicted,
                previous_transaction_type=previous,
                final_transaction_type=final,
                confirmation_method=confirmation_method,
                origin_ref=origin_ref,
                confidence=confidence,
                source=source,
            ),
        )
