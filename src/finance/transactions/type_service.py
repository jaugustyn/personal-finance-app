"""Use case for transaction-type mutations."""
from __future__ import annotations

from typing import Any, cast

from sqlalchemy.orm import Session

from finance.domain.enums import TransactionType
from finance.domain.models import Transaction
from finance.transactions.mutation_rules import (
    TRANSFER_TYPES,
    can_assign_expense_category,
    clear_category_state,
)


class TransactionTypeService:
    """Applies transaction-type changes and keeps derived flags consistent."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def update_transaction_type(
        self,
        tx_id: int,
        transaction_type: str,
    ) -> Transaction | None:
        """Manually override the transaction type.

        Keeps ``is_transfer`` consistent with the chosen type so downstream
        aggregations that exclude transfers stay correct.
        """
        try:
            value = TransactionType(transaction_type).value
        except ValueError:
            return None
        tx = self.session.get(Transaction, tx_id)
        if tx is None:
            return None
        self.apply_transaction_type(tx, value)
        self.session.commit()
        self.session.refresh(tx)
        return tx

    def apply_transaction_type(self, tx: Transaction, value: str) -> None:
        tx_model = cast(Any, tx)
        tx_model.transaction_type = value
        tx_model.is_transfer = value in TRANSFER_TYPES
        if not can_assign_expense_category(tx):
            clear_category_state(tx)

    def apply_transfer_marker(self, tx: Transaction, mark_transfer: bool) -> None:
        value = (
            TransactionType.OWN_TRANSFER.value
            if mark_transfer
            else TransactionType.PURCHASE.value
        )
        self.apply_transaction_type(tx, value)
