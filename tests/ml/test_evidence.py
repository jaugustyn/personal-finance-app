from __future__ import annotations

from datetime import date

import pandas as pd

from finance.ml.evidence import (
    build_anomaly_review,
    build_eda_summary,
    build_forecasting_evidence,
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
