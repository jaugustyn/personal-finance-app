"""PostgreSQL foreign-key, account deduplication and deletion contracts."""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from finance.domain.models import (
    Account,
    FixedCharge,
    FixedChargeTransaction,
    Import,
    MlEvaluationMember,
    MlEvaluationSet,
    MlFeedbackEvent,
    Transaction,
)
from finance.ingestion.use_cases import delete_import
from finance.transactions.mutations import bulk_delete, delete_transaction

pytestmark = pytest.mark.postgres_integration


def _transaction(account_id: int, *, dedup_hash: str = "synthetic-pg") -> Transaction:
    return Transaction(
        account_id=account_id, booking_date=date(2026, 1, 15),
        amount=Decimal("-100"), currency="PLN", direction="debit",
        transaction_type="expense", merchant="Synthetic store", title="Synthetic purchase",
        source="generic", dedup_hash=dedup_hash,
    )


@pytest.fixture
def linked_transaction(postgres_reference):
    session, _client = postgres_reference
    account = Account(name="Synthetic account")
    session.add(account)
    session.flush()
    batch = Import(account_id=account.id, source="generic", filename="synthetic.csv")
    frozen = MlEvaluationSet(
        id="synthetic-evaluation", status="active", ontology_version="category_v1",
        dataset_fingerprint="0" * 64, config={},
    )
    charge = FixedCharge(
        name="Synthetic charge", amount=Decimal("100"), cadence="monthly",
        anchor_date=date(2026, 1, 15),
    )
    session.add_all([batch, frozen, charge])
    session.flush()
    tx = _transaction(account.id)
    tx.import_id = batch.id
    unrelated = _transaction(account.id, dedup_hash="unrelated-synthetic-pg")
    session.add_all([tx, unrelated])
    session.flush()
    member = MlEvaluationMember(
        evaluation_set_id=frozen.id, transaction_id=tx.id, split="time",
        category="food", booking_date=tx.booking_date, merchant_hash="0" * 64,
    )
    feedback = MlFeedbackEvent(transaction_id=tx.id, event_type="manual_category")
    link = FixedChargeTransaction(
        fixed_charge_id=charge.id, transaction_id=tx.id, scheduled_due_date=tx.booking_date,
    )
    session.add_all([member, feedback, link])
    session.commit()
    return session, tx, batch, frozen, member, feedback, link, charge, unrelated


@pytest.mark.parametrize("operation", ["single", "bulk", "import"])
def test_deletion_preserves_audit_and_cascades_payment_links(linked_transaction, operation) -> None:
    session, tx, batch, frozen, member, feedback, link, charge, unrelated = linked_transaction
    tx_id, link_id, batch_id = tx.id, link.id, batch.id
    if operation == "single":
        assert delete_transaction(session, tx_id)
    elif operation == "bulk":
        assert bulk_delete(session, [tx_id]) == 1
    else:
        assert delete_import(session, batch_id).deleted_transactions == 1
    session.expire_all()

    assert session.get(Transaction, tx_id) is None
    assert session.get(FixedChargeTransaction, link_id) is None
    assert session.get(Transaction, unrelated.id) is not None
    assert session.get(FixedCharge, charge.id) is not None
    assert (session.get(Import, batch_id) is None) == (operation == "import")
    assert member.transaction_id is None
    assert feedback.transaction_id is None
    assert frozen.status == "invalidated"
    assert frozen.invalidation_reason == "frozen_transaction_deleted"


@pytest.mark.parametrize("operation", ["single", "bulk", "import"])
def test_failed_delete_rolls_back_foreign_key_effects(linked_transaction, monkeypatch, operation) -> None:
    session, tx, batch, frozen, member, feedback, link, _charge, _unrelated = linked_transaction
    tx_id, batch_id, link_id = tx.id, batch.id, link.id

    def fail_commit():
        raise RuntimeError("Synthetic commit failure")

    monkeypatch.setattr(session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="Synthetic commit failure"):
        if operation == "single":
            delete_transaction(session, tx_id)
        elif operation == "bulk":
            bulk_delete(session, [tx_id])
        else:
            delete_import(session, batch_id)
    session.expire_all()

    assert session.get(Transaction, tx_id) is not None
    assert session.get(Import, batch_id) is not None
    assert session.get(FixedChargeTransaction, link_id) is not None
    assert member.transaction_id == tx_id
    assert feedback.transaction_id == tx_id
    assert frozen.status == "active"


@pytest.mark.parametrize("missing_reference", ["account", "import"])
def test_postgres_rejects_missing_transaction_parent(postgres_reference, missing_reference) -> None:
    session, _client = postgres_reference
    account = Account(name="Synthetic account")
    session.add(account)
    session.commit()
    tx = _transaction(account.id)
    if missing_reference == "account":
        tx.account_id = 999999
    else:
        tx.import_id = 999999
    session.add(tx)

    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    assert session.scalar(select(func.count(Transaction.id))) == 0


def test_deduplication_is_enforced_per_account(postgres_reference) -> None:
    session, _client = postgres_reference
    accounts = [Account(name="First synthetic account"), Account(name="Second synthetic account")]
    session.add_all(accounts)
    session.flush()
    session.add_all([_transaction(account.id) for account in accounts])
    session.commit()
    assert session.scalar(select(func.count(Transaction.id))) == 2
    session.add(_transaction(accounts[0].id))

    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
    assert session.scalar(select(func.count(Transaction.id))) == 2
