"""Regression coverage for evolving data and frozen evaluation membership."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import delete
from sqlalchemy.orm import sessionmaker

from finance.domain.enums import Category
from finance.domain.models import Import, MlEvaluationMember, MlTrainingJob, Transaction
from finance.ingestion.use_cases import delete_import
from finance.ml.classification import lifecycle
from finance.ml.classification.candidate_evaluation import (
    ValidationSplitNotFeasible,
    development_split_ids,
    prepare_experiment,
)
from finance.ml.classification.dataset import load_training_set
from finance.ml.classification.evaluation_sets import (
    evaluation_set_summary,
    freeze_evaluation_set,
    split_transaction_ids,
)
from finance.transactions.merchants import create_aliases
from finance.transactions.mutations import bulk_delete, delete_transaction
from scripts import evaluate_llm_fallback


def _experiment_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "transaction_id": 2 * day + label_index,
                "category": label,
                "booking_date": date(2025, 1, 1) + timedelta(days=day),
                "merchant": f"Store {day % 10}",
                "merchant_group": f"store-{day % 10}",
                "title": "Purchase",
            }
            for day in range(41)
            for label_index, label in enumerate(("food", "transport"))
        ]
    )


def test_time_split_keeps_the_entire_boundary_day_in_holdout() -> None:
    frame = _experiment_frame()
    splits = development_split_ids(frame)
    test = frame[frame.transaction_id.isin(splits["time"])]
    train = frame[~frame.transaction_id.isin(splits["time"])]

    assert train.booking_date.max() < test.booking_date.min()


def test_frozen_split_excludes_new_future_rows_and_held_out_merchants() -> None:
    frame = _experiment_frame()
    splits = development_split_ids(frame)
    time_cutoff = frame.loc[frame.transaction_id.isin(splits["time"]), "booking_date"].min()
    held_out_groups = set(
        frame.loc[frame.transaction_id.isin(splits["merchant"]), "merchant_group"]
    )
    train_group = next(group for group in frame.merchant_group if group not in held_out_groups)
    additions = pd.DataFrame(
        [
            dict(
                frame.iloc[0],
                transaction_id=100,
                booking_date=date(2026, 1, 1),
                merchant_group=train_group,
            ),
            dict(frame.iloc[0], transaction_id=101, merchant_group=sorted(held_out_groups)[0]),
            dict(
                frame.iloc[0],
                transaction_id=102,
                booking_date=time_cutoff,
                merchant_group="new-store",
            ),
            dict(frame.iloc[0], transaction_id=103, merchant_group="new-store"),
        ]
    )

    prepared = prepare_experiment(pd.concat([frame, additions]), split_ids=splits)

    assert set(prepared.training_pool.transaction_id) & {100, 101, 102, 103} == {103}
    assert prepared.training_pool.booking_date.max() < time_cutoff
    assert set(prepared.training_pool.merchant_group).isdisjoint(held_out_groups)


@pytest.mark.parametrize("invalid", [set(), {99999}])
def test_incomplete_frozen_membership_rejects_experiment(invalid) -> None:
    frame = _experiment_frame()
    splits = development_split_ids(frame) | {"time": invalid}
    with pytest.raises(ValidationSplitNotFeasible, match="holdout"):
        prepare_experiment(frame, split_ids=splits)


@pytest.fixture
def frozen_set(db_session):
    merchants = [
        "alpha",
        "beta",
        "gamma",
        "delta",
        "epsilon",
        "zeta",
        "theta",
        "kappa",
        "lambda",
        "sigma",
        "omega",
        "atlas",
        "nova",
        "orion",
        "lumen",
    ]
    for category_index, category in enumerate(Category):
        for item in range(91):
            db_session.add(
                Transaction(
                    booking_date=date(2025, 1, 1) + timedelta(days=item * 5),
                    amount=Decimal("-10"),
                    amount_base=Decimal("-10"),
                    base_currency="PLN",
                    currency="EUR",
                    fx_rate=Decimal("1"),
                    direction="debit",
                    merchant=f"{merchants[item % len(merchants)]} store",
                    title="Synthetic purchase",
                    category=category.value,
                    category_source="manual",
                    category_confirmation_method="manual",
                    category_confirmed_at=datetime(2026, 6, 1, tzinfo=UTC),
                    source="pekao",
                    transaction_type="expense",
                    is_transfer=False,
                    dedup_hash=f"evaluation-{category_index}-{item}",
                )
            )
    db_session.commit()
    frozen = freeze_evaluation_set(db_session)
    ids = split_transaction_ids(db_session, frozen.id)
    member = db_session.get(Transaction, min(ids["time"]))
    return frozen, member


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", "Corrected purchase"),
        ("amount_base", Decimal("-25")),
        ("fx_rate", None),
        ("booking_date", date(2025, 1, 1)),
        ("category_confirmation_method", None),
        ("category_origin_ref", "corrected-origin"),
    ],
)
def test_changed_frozen_features_or_provenance_invalidate_summary(
    db_session,
    frozen_set,
    field,
    value,
) -> None:
    frozen, member = frozen_set
    setattr(member, field, value)
    db_session.commit()

    assert evaluation_set_summary(db_session)["active"] is False
    db_session.refresh(frozen)
    assert frozen.status == "invalidated"


def test_alias_change_invalidates_frozen_merchant_identity(db_session, frozen_set) -> None:
    frozen, member = frozen_set
    create_aliases(db_session, canonical_label="Renamed store", aliases=[member.merchant])

    assert evaluation_set_summary(db_session)["active"] is False
    db_session.refresh(frozen)
    assert frozen.status == "invalidated"


def test_unrelated_changes_do_not_invalidate_frozen_set(db_session, frozen_set) -> None:
    frozen, member = frozen_set
    member.notes = "Notes do not feed classification"
    held_out = set().union(*split_transaction_ids(db_session, frozen.id).values())
    train_row = next(row for row in db_session.query(Transaction) if row.id not in held_out)
    train_row.title = "Corrected training title"
    db_session.add(
        Transaction(
            booking_date=date(2027, 1, 1),
            amount=Decimal("-20"),
            currency="PLN",
            direction="debit",
            merchant="New store",
            title="New confirmed transaction",
            category="food",
            category_source="manual",
            category_confirmation_method="manual",
            category_confirmed_at=datetime(2027, 1, 1, tzinfo=UTC),
            source="manual",
            transaction_type="expense",
            dedup_hash="new-confirmed-row",
        )
    )
    db_session.commit()

    assert evaluation_set_summary(db_session)["active"] is True


@pytest.mark.parametrize("null_member", [False, True])
def test_missing_frozen_transaction_invalidates_summary(
    db_session, frozen_set, null_member
) -> None:
    frozen, member = frozen_set
    member_id = member.id
    db_session.execute(delete(Transaction).where(Transaction.id == member_id))
    if null_member:
        # Reproduce PostgreSQL ON DELETE SET NULL (the default SQLite fixture
        # does not enforce foreign keys).
        for row in db_session.query(MlEvaluationMember).filter_by(transaction_id=member_id):
            row.transaction_id = None
    db_session.commit()

    assert evaluation_set_summary(db_session)["active"] is False
    db_session.refresh(frozen)
    assert frozen.status == "invalidated"


def test_frozen_set_without_snapshot_requires_refreezing(db_session, frozen_set) -> None:
    frozen, _ = frozen_set
    frozen.config = {
        key: value for key, value in frozen.config.items() if key != "split_fingerprints"
    }
    db_session.commit()

    assert evaluation_set_summary(db_session)["active"] is False
    replacement = freeze_evaluation_set(db_session)
    assert replacement.id != frozen.id


@pytest.mark.parametrize("operation", ["single", "bulk", "import"])
def test_deletion_invalidates_frozen_set_in_same_transaction(
    db_session,
    frozen_set,
    operation,
) -> None:
    frozen, member = frozen_set
    if operation == "single":
        assert delete_transaction(db_session, member.id)
    elif operation == "bulk":
        assert bulk_delete(db_session, [member.id]) == 1
    else:
        batch = Import(
            source="pekao", filename="synthetic.csv", total_rows=1, inserted=1, duplicates=0
        )
        db_session.add(batch)
        db_session.flush()
        member.import_id = batch.id
        db_session.commit()
        assert delete_import(db_session, batch.id).deleted_transactions == 1

    db_session.refresh(frozen)
    assert frozen.status == "invalidated"
    assert frozen.invalidation_reason == "frozen_transaction_deleted"


@pytest.mark.parametrize("operation", ["single", "bulk", "import"])
def test_failed_delete_rolls_back_invalidation(
    db_session,
    frozen_set,
    monkeypatch,
    operation,
) -> None:
    frozen, member = frozen_set
    member_id = member.id
    batch = Import(source="pekao", filename="synthetic.csv", total_rows=1, inserted=1, duplicates=0)
    db_session.add(batch)
    db_session.flush()
    member.import_id = batch.id
    db_session.commit()

    def fail_commit():
        raise RuntimeError("simulated write failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)
    with pytest.raises(RuntimeError, match="simulated"):
        if operation == "single":
            delete_transaction(db_session, member_id)
        elif operation == "bulk":
            bulk_delete(db_session, [member_id])
        else:
            delete_import(db_session, batch.id)

    db_session.refresh(frozen)
    assert frozen.status == "active"
    assert db_session.get(Transaction, member_id) is not None
    assert db_session.get(Import, batch.id) is not None


@pytest.mark.parametrize("condition", ["changed_data", "different_model_set"])
def test_llm_experiment_rejects_invalid_evaluation_before_predictions(
    db_engine,
    db_session,
    frozen_set,
    monkeypatch,
    condition,
) -> None:
    frozen, member = frozen_set
    if condition == "changed_data":
        member.title = "Changed after freezing"
        db_session.commit()
    monkeypatch.setattr(evaluate_llm_fallback, "SessionLocal", sessionmaker(bind=db_engine))
    monkeypatch.setattr(
        evaluate_llm_fallback, "get_settings", lambda: SimpleNamespace(llm_fallback_enabled=True)
    )
    monkeypatch.setattr(
        evaluate_llm_fallback,
        "require_registered_active_artifact",
        lambda session: {"evaluation_set_id": "another-evaluation"},
    )

    with pytest.raises(SystemExit, match="[Ff]rozen set|[Ff]rozen evaluation set"):
        evaluate_llm_fallback.main([])

    db_session.refresh(frozen)
    assert frozen.status == ("invalidated" if condition == "changed_data" else "active")


def test_training_rejects_modified_frozen_data_before_evaluating(
    db_engine,
    db_session,
    frozen_set,
    monkeypatch,
) -> None:
    frozen, member = frozen_set
    member.title = "Modified since freeze"
    db_session.commit()
    job_id = lifecycle.enqueue_training_job(db_session).id
    calls = []
    monkeypatch.setattr(lifecycle, "evaluate_candidate", lambda *args, **kwargs: calls.append(1))

    lifecycle.run_training_job(session_factory=sessionmaker(bind=db_engine), job_id=job_id)

    db_session.expire_all()
    job = db_session.get(MlTrainingJob, job_id)
    assert calls == []
    assert job.status == "failed"
    assert job.execution_slot is None
    assert "evaluation set" in job.error.lower()
    assert frozen.status == "invalidated"


def test_frozen_training_pool_respects_both_boundaries(db_session, frozen_set) -> None:
    frozen, _ = frozen_set
    frame = load_training_set(db_session)
    splits = split_transaction_ids(db_session, frozen.id)
    prepared = prepare_experiment(frame, split_ids=splits)
    time_test = frame[frame.transaction_id.isin(splits["time"])]
    merchant_test = frame[frame.transaction_id.isin(splits["merchant"])]

    time_train = frame[~frame.transaction_id.isin(splits["time"])]
    assert time_train.booking_date.max() < time_test.booking_date.min()
    assert prepared.training_pool.booking_date.max() < time_test.booking_date.min()
    assert set(prepared.training_pool.merchant_group).isdisjoint(merchant_test.merchant_group)
