from __future__ import annotations

import pandas as pd

from finance.ml.transaction_type.dataset import LABEL_SOURCE, prepare_training_frame
from finance.ml.transaction_type.train import build_evidence_report, evaluate


def _multiclass_df() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    examples = {
        "purchase": [
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
                    },
                    {
                        "merchant": "Empty",
                        "title": "missing label",
                        "amount": -10,
                        "direction": "debit",
                        "source": "synthetic",
                        "transaction_type": None,
                    },
                ]
            ),
        ],
        ignore_index=True,
    )

    prepared = prepare_training_frame(df)

    assert len(prepared) == len(_multiclass_df())
    assert set(prepared["transaction_type"]) == {"purchase", "salary", "own_transfer"}
    assert (prepared["label_source"] == LABEL_SOURCE).all()
    assert prepared["text"].str.len().min() > 0
    assert prepared["abs_amount"].min() > 0


def test_evaluate_transaction_type_returns_metrics() -> None:
    report = evaluate(_multiclass_df(), n_splits=2)

    assert report["label_source"] == "silver_transaction_type"
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
    assert report["label_source"] == "silver_transaction_type"
    assert report["runtime_policy"] == "evidence_only_rules_remain_source_of_truth"
    assert report["semantic_note"]
    assert report["models"]["linear_svc"]["confusion_matrix"]
    assert report["models"]["linear_svc"]["per_class"]
