"""Focused tests for category dataset provenance and offline evidence."""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from finance.ml.classification import train
from finance.ml.classification.evaluation import (
    build_label_readiness,
    filter_category_training_rows,
)


def _labelled_frame() -> pd.DataFrame:
    now = datetime.now(UTC)
    return pd.DataFrame(
        [
            {
                "text": "Biedronka zakupy",
                "merchant": "Biedronka",
                "title": "zakupy",
                "abs_amount": 30.0,
                "day_of_week": 1,
                "booking_date": "2026-01-01",
                "category": "food",
                "category_confirmation_method": "manual",
                "category_confirmed_at": now,
                "source": "pekao",
                "direction": "debit",
                "transaction_type": "expense",
                "is_transfer": False,
            },
            {
                "text": "Orlen paliwo",
                "merchant": "Orlen",
                "title": "paliwo",
                "abs_amount": 200.0,
                "day_of_week": 2,
                "booking_date": "2026-01-02",
                "category": "transport",
                "category_confirmation_method": "accepted_suggestion",
                "category_confirmed_at": now,
                "source": "pekao",
                "direction": "debit",
                "transaction_type": "expense",
                "is_transfer": False,
            },
        ]
    )


def test_training_filter_requires_full_gold_provenance() -> None:
    confirmed = _labelled_frame()
    missing_columns = confirmed.drop(
        columns=["category_confirmation_method", "category_confirmed_at"]
    )
    silver = confirmed.assign(
        category_confirmation_method="personal_rule_auto",
        category_confirmed_at=None,
    )

    assert len(filter_category_training_rows(confirmed)) == 2
    assert filter_category_training_rows(missing_columns).empty
    assert filter_category_training_rows(silver).empty


def test_training_filter_excludes_non_expense_and_custom_labels() -> None:
    frame = _labelled_frame()
    invalid = pd.concat(
        [
            frame,
            frame.iloc[[0]].assign(category="custom"),
            frame.iloc[[0]].assign(transaction_type="own_transfer", is_transfer=True),
            frame.iloc[[0]].assign(direction="credit"),
        ],
        ignore_index=True,
    )

    assert filter_category_training_rows(invalid)["category"].tolist() == [
        "food",
        "transport",
    ]


def test_readiness_counts_only_gold_labels() -> None:
    readiness = build_label_readiness(_labelled_frame())

    assert readiness["total_labelled"] == 2
    assert readiness["category_counts"]["food"] == 1
    assert readiness["technical_ready"] is False


def test_offline_evidence_skips_below_300_and_keeps_experiments_separate() -> None:
    frame = _labelled_frame()
    synthetic = frame.drop(
        columns=["category_confirmation_method", "category_confirmed_at"]
    )

    report = train.build_evidence_report(
        frame,
        augmented_df=synthetic,
        external_df=synthetic,
    )

    assert report["skipped"] is True
    assert report["reason"] == "total_confirmed_labels_below_300"
    assert report["models"] == {}
    assert report["separate_experiments"]["synthetic_rows"] == 2
    assert report["separate_experiments"]["external_rows"] == 2
    assert report["confidence_policy"]["default_threshold"] == 0.55


def test_files_without_provenance_never_become_gold() -> None:
    frame = _labelled_frame().drop(
        columns=["category_confirmation_method", "category_confirmed_at"]
    )
    report = train.build_evidence_report(frame)

    assert report["n_total_labelled"] == 0
    assert report["skipped"] is True


def test_guess_source_pekao_revolut_and_unknown() -> None:
    from finance.domain.enums import BankSource

    assert train._guess_source(Path("pekao_2026.csv")) is BankSource.PEKAO
    assert train._guess_source(Path("revolut-account-statement.csv")) is BankSource.REVOLUT
    with pytest.raises(ValueError):
        train._guess_source(Path("mystery.csv"))


def test_load_synthetic_validates_columns(tmp_path: Path) -> None:
    good = tmp_path / "synth.csv"
    good.write_text(
        "text,abs_amount,day_of_week,category\nfoo,10,1,food\n",
        encoding="utf-8",
    )
    assert train._load_synthetic(good).iloc[0]["source"] == "synthetic"

    bad = tmp_path / "bad.csv"
    bad.write_text("text,category\nfoo,food\n", encoding="utf-8")
    with pytest.raises(ValueError):
        train._load_synthetic(bad)
