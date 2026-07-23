"""Atomicity regressions for composed transaction mutation use cases."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from finance.domain.models import MlFeedbackEvent, PersonalRule, Transaction
from finance.transactions.category_assignment import CategoryAssignmentService
from finance.transactions.type_service import TransactionTypeService


def test_remembered_rule_rolls_back_with_failed_category_decision(
    db_session,
    monkeypatch,
) -> None:
    transaction = Transaction(
        booking_date=date(2026, 7, 1),
        amount=Decimal("-25.00"),
        currency="PLN",
        direction="debit",
        merchant="Sklep testowy",
        title="Zakupy",
        transaction_type="expense",
        source="manual",
        dedup_hash="category-atomicity",
    )
    db_session.add(transaction)
    db_session.commit()

    def fail_after_rule(_: Transaction) -> None:
        raise RuntimeError("failure after remembered rule")

    monkeypatch.setattr(
        "finance.transactions.category_assignment.clear_suggestion",
        fail_after_rule,
    )

    with pytest.raises(RuntimeError, match="failure after remembered rule"):
        CategoryAssignmentService(db_session).update_category(
            transaction.id,
            "food",
            remember_rule=True,
        )

    restored = db_session.get(Transaction, transaction.id)
    assert restored is not None
    assert restored.category is None
    assert restored.category_confirmation_method is None
    assert db_session.scalar(select(func.count(PersonalRule.id))) == 0
    assert db_session.scalar(select(func.count(MlFeedbackEvent.id))) == 0


def test_bulk_mutation_rolls_back_rows_changed_before_a_later_failure(
    db_session,
    monkeypatch,
) -> None:
    transactions = [
        Transaction(
            booking_date=date(2026, 7, day),
            amount=Decimal("-25.00"),
            currency="PLN",
            direction="debit",
            merchant=f"Shop {day}",
            title="Purchase",
            source="manual",
            dedup_hash=f"bulk-category-atomicity-{day}",
        )
        for day in (1, 2)
    ]
    db_session.add_all(transactions)
    db_session.commit()
    transaction_ids = [transaction.id for transaction in transactions]
    original = TransactionTypeService.apply_manual_type
    calls = 0

    def fail_on_second(self, transaction, value, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("failure after first bulk row")
        return original(self, transaction, value, **kwargs)

    monkeypatch.setattr(TransactionTypeService, "apply_manual_type", fail_on_second)
    unchanged = object()

    with pytest.raises(RuntimeError, match="failure after first bulk row"):
        CategoryAssignmentService(db_session).bulk_categorize(
            ids=transaction_ids,
            merchant=None,
            category=unchanged,
            transaction_type="expense",
            unchanged=unchanged,
        )

    for transaction_id in transaction_ids:
        restored = db_session.get(Transaction, transaction_id)
        assert restored is not None
        assert restored.transaction_type is None
    assert db_session.scalar(select(func.count(MlFeedbackEvent.id))) == 0
