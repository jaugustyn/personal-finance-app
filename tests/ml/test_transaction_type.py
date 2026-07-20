from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pandas as pd

from finance.domain.models import Transaction
from finance.ml.transaction_type.dataset import (
    LABEL_SOURCE,
    load_training_set,
    prepare_training_frame,
)
from finance.ml.transaction_type.train import build_evidence_report, evaluate


def _multiclass_df() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    confirmed_at = datetime.now(UTC)
    examples = {
        "expense": [
            ("Lidl", "zakupy spozywcze", -42.0, "debit"),
            ("Biedronka", "sklep", -31.0, "debit"),
            ("Allegro", "platnosc online", -120.0, "debit"),
            ("Orlen", "paliwo", -220.0, "debit"),
        ],
        "salary": [
            ("ACME", "wynagrodzenie maj", 5000.0, "credit"),
            ("Employer", "salary payroll", 5200.0, "credit"),
            ("Firma", "wyplata wynagrodzenia", 4800.0, "credit"),
            ("Payroll", "umowa o prace", 5100.0, "credit"),
        ],
        "own_transfer": [
            ("Rachunek wlasny", "przelew miedzy rachunkami", -1000.0, "debit"),
            ("Revolut", "exchanged to usd", -300.0, "debit"),
            ("Savings", "transfer to savings", -700.0, "debit"),
            ("Kantor", "wymiana waluty", -500.0, "debit"),
        ],
    }
    for tx_type, values in examples.items():
        for merchant, title, amount, direction in values:
            rows.append(
                {
                    "merchant": merchant,
                    "title": title,
                    "raw_category": "",
                    "amount": amount,
                    "direction": direction,
                    "source": "synthetic",
                    "transaction_type": tx_type,
                    "transaction_type_confirmation_method": "manual",
                    "transaction_type_confirmed_at": confirmed_at,
                }
            )
    return pd.DataFrame(rows)


def test_prepare_training_frame_filters_invalid_transaction_types() -> None:
    df = _multiclass_df()
    df = pd.concat(
        [
            df,
            pd.DataFrame(
                [
                    {
                        "merchant": "Unknown",
                        "title": "bad label",
                        "amount": -10,
                        "direction": "debit",
                        "source": "synthetic",
                        "transaction_type": "not_a_type",
                        "transaction_type_confirmation_method": "manual",
                        "transaction_type_confirmed_at": datetime.now(UTC),
                    },
                    {
                        "merchant": "Empty",
                        "title": "missing label",
                        "amount": -10,
                        "direction": "debit",
                        "source": "synthetic",
                        "transaction_type": None,
                        "transaction_type_confirmation_method": "manual",
                        "transaction_type_confirmed_at": datetime.now(UTC),
                    },
                ]
            ),
        ],
        ignore_index=True,
    )

    prepared = prepare_training_frame(df)

    assert len(prepared) == len(_multiclass_df())
    assert set(prepared["transaction_type"]) == {"expense", "salary", "own_transfer"}
    assert (prepared["label_source"] == LABEL_SOURCE).all()
    assert prepared["text"].str.len().min() > 0
    assert prepared["abs_amount"].min() > 0


def test_transaction_type_evidence_requires_gold_provenance() -> None:
    without_provenance = _multiclass_df().drop(
        columns=[
            "transaction_type_confirmation_method",
            "transaction_type_confirmed_at",
        ]
    )
    report = build_evidence_report(without_provenance)

    assert report["skipped"] is True
    assert report["reason"] == "no_valid_gold_transaction_type_labels"
    assert report["diagnostics"]["input_rows"] == len(without_provenance)


def test_transaction_type_evidence_excludes_automatic_labels() -> None:
    silver = _multiclass_df().assign(
        transaction_type_confirmation_method="personal_rule_auto",
        transaction_type_confirmed_at=None,
    )

    assert prepare_training_frame(silver).empty


def test_transaction_type_evidence_excludes_missing_amounts() -> None:
    frame = _multiclass_df()
    frame.loc[0, "amount"] = None

    prepared = prepare_training_frame(frame)

    assert len(prepared) == len(frame) - 1
    assert prepared["abs_amount"].notna().all()


def test_evaluate_transaction_type_returns_metrics() -> None:
    report = evaluate(_multiclass_df(), n_splits=2)

    assert report["label_source"] == "confirmed_transaction_type"
    assert report["n_classes"] == 3
    assert set(report["models"]) == {
        "dummy_most_frequent",
        "logreg",
        "linear_svc",
    }
    for info in report["models"].values():
        assert 0.0 <= info["macro_f1"] <= 1.0
        assert 0.0 <= info["weighted_f1"] <= 1.0
        assert "confusion_matrix" in info
        assert "per_class" in info


def test_build_transaction_type_evidence_report_marks_runtime_policy() -> None:
    report = build_evidence_report(_multiclass_df(), n_splits=2)

    assert report["report_type"] == "transaction_type_classification_evidence"
    assert report["classification_task"] == "multiclass_transaction_type"
    assert report["label_source"] == "confirmed_transaction_type"
    assert report["runtime_policy"] == "evidence_only_rules_remain_source_of_truth"
    assert report["semantic_note"]
    assert report["models"]["linear_svc"]["confusion_matrix"]
    assert report["models"]["linear_svc"]["per_class"]


def test_db_training_set_contains_only_manual_and_accepted_type_labels(
    db_session,
) -> None:
    now = datetime.now(UTC)
    methods = ["manual", "accepted_suggestion", None, None]
    sources = ["manual", "model", "bank", "rule"]
    for index, (method, source) in enumerate(zip(methods, sources, strict=True)):
        db_session.add(
            Transaction(
                booking_date=date(2026, 1, index + 1),
                amount=Decimal("-10"),
                amount_base=Decimal("-10"),
                currency="PLN",
                direction="debit",
                merchant=f"Merchant {index}",
                title="Payment",
                raw_transaction_type="CARD PAYMENT",
                transaction_type="expense",
                transaction_type_source=source,
                transaction_type_confirmation_method=method,
                transaction_type_confirmed_at=now if method else None,
                source="pekao",
                dedup_hash=f"type-gold-{index}",
            )
        )
    db_session.commit()

    frame = load_training_set(db_session)

    assert len(frame) == 2
    assert set(frame["label_source"]) == {"confirmed_transaction_type"}
    assert frame["text"].str.contains("CARD PAYMENT").all()
    assert set(frame["transaction_type_confirmation_method"]) == {
        "manual",
        "accepted_suggestion",
    }
    assert len(prepare_training_frame(frame)) == 2
