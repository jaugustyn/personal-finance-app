from __future__ import annotations

from datetime import date

import pandas as pd

from finance.ml.evidence import (
    build_anomaly_review,
    build_eda_summary,
    build_forecasting_evidence,
    build_subscription_evidence,
)


def _df() -> pd.DataFrame:
    rows = []
    for i in range(8):
        rows.append(
            {
                "booking_date": date(2026, min(i + 1, 12), 5),
                "amount": -50.0 - i,
                "abs_amount": 50.0 + i,
                "direction": "debit",
                "merchant": "Lidl" if i % 2 else "Carrefour",
                "title": "Zakupy",
                "category": "food",
                "is_transfer": False,
                "transaction_type": "expense",
            }
        )
    rows.append(
        {
            "booking_date": date(2026, 8, 10),
            "amount": -5000.0,
            "abs_amount": 5000.0,
            "direction": "debit",
            "merchant": "New Merchant",
            "title": "Large",
            "category": "other",
            "is_transfer": False,
            "transaction_type": "expense",
        }
    )
    rows.append(
        {
            "booking_date": date(2026, 8, 1),
            "amount": 7000.0,
            "abs_amount": 7000.0,
            "direction": "credit",
            "merchant": "Employer",
            "title": "Salary",
            "category": None,
            "is_transfer": False,
            "transaction_type": "salary",
        }
    )
    return pd.DataFrame(rows)


def test_build_eda_summary_uses_aggregate_aliases() -> None:
    summary = build_eda_summary(_df(), top_n=2)
    assert summary["n_rows"] == 10
    assert summary["direction_counts"]["debit"] == 9
    assert summary["top_merchants"][0]["merchant_alias"].startswith("merchant_")
    assert "Lidl" not in str(summary["top_merchants"])


def test_build_forecasting_evidence_reports_models() -> None:
    report = build_forecasting_evidence(_df(), categories=[None], min_train=2)
    assert report["series"][0]["category"] is None
    assert report["series"][0]["n_months"] >= 1
    assert isinstance(report["series"][0]["models"], dict)


def test_build_anomaly_review_splits_private_and_public() -> None:
    review = build_anomaly_review(_df(), top_n=5)
    assert "merchant" in review.private_rows.columns or review.private_rows.empty
    assert "examples" in review.public_summary
    assert "New Merchant" not in str(review.public_summary)


def test_build_subscription_evidence_uses_aliases() -> None:
    df = _df()
    extra = pd.DataFrame(
        [
            {
                "booking_date": date(2026, 1, 1),
                "amount": -29.99,
                "abs_amount": 29.99,
                "direction": "debit",
                "merchant": "Netflix",
                "title": "subskrypcja",
                "category": "subscriptions",
                "is_transfer": False,
                "transaction_type": "expense",
            },
            {
                "booking_date": date(2026, 2, 1),
                "amount": -29.99,
                "abs_amount": 29.99,
                "direction": "debit",
                "merchant": "Netflix",
                "title": "subskrypcja",
                "category": "subscriptions",
                "is_transfer": False,
                "transaction_type": "expense",
            },
        ]
    )
    report = build_subscription_evidence(pd.concat([df, extra], ignore_index=True))

    assert report["detector"] == "cadence_amount_heuristic"
    assert report["subscriptions_detected"] >= 1
    assert report["examples"][0]["subscription_alias"].startswith("subscription_")
    assert "Netflix" not in str(report)
