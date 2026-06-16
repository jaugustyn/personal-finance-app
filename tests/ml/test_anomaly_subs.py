"""Tests for anomaly detector + subscription detector."""
import numpy as np
import pandas as pd
import pytest

from finance.ml.anomaly import detect_anomalies
from finance.ml.subscriptions import detect_subscriptions


def _normal_txs(n: int, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    merchants = rng.choice(["BIEDRONKA", "LIDL", "CARREFOUR"], size=n)
    amounts = -np.abs(rng.normal(50, 10, size=n))
    return pd.DataFrame({
        "booking_date": dates,
        "amount": amounts,
        "direction": ["debit"] * n,
        "merchant": merchants,
        "category": ["food"] * n,
    })


def test_anomaly_flags_huge_outlier() -> None:
    df = _normal_txs(40)
    # Inject a 50x outlier on day 5.
    df.loc[5, "amount"] = -3000.0
    df.loc[5, "merchant"] = "MYSTERIOUS BIG TRANSFER"
    res = detect_anomalies(df)
    out = res.df
    assert out.loc[5, "anomaly"]
    assert out.loc[5, "severity"] > 0
    assert out.loc[5, "reasons"]
    assert "z=" not in out.loc[5, "reasons"]
    assert "z>" not in out.loc[5, "reasons"]


def test_anomaly_handles_empty_frame() -> None:
    res = detect_anomalies(pd.DataFrame(
        columns=["booking_date", "amount", "direction", "merchant", "category"]
    ))
    assert res.df.empty


def test_anomaly_excludes_own_transfers() -> None:
    df = _normal_txs(40)
    df["is_transfer"] = False
    df.loc[5, "amount"] = -9999.0
    df.loc[5, "merchant"] = "OWN ACCOUNT TRANSFER"
    df.loc[5, "is_transfer"] = True
    res = detect_anomalies(df)
    assert not bool(res.df.loc[5, "anomaly"])


def test_anomaly_excludes_non_expense_transaction_types() -> None:
    df = _normal_txs(40)
    df["transaction_type"] = "purchase"
    df.loc[5, "amount"] = -9999.0
    df.loc[5, "merchant"] = "XTB S.A."
    df.loc[5, "transaction_type"] = "savings_investment"

    res = detect_anomalies(df)

    assert not bool(res.df.loc[5, "anomaly"])


@pytest.mark.parametrize("tx_type", ["salary", "income", "refund", "own_transfer"])
def test_anomaly_excludes_non_candidate_transaction_types(tx_type: str) -> None:
    df = _normal_txs(40)
    df["transaction_type"] = "purchase"
    df.loc[5, "amount"] = -9999.0
    df.loc[5, "merchant"] = "NON EXPENSE FLOW"
    df.loc[5, "transaction_type"] = tx_type

    res = detect_anomalies(df)

    assert not bool(res.df.loc[5, "anomaly"])


def test_regular_monthly_large_merchant_is_not_anomaly() -> None:
    dates = pd.date_range("2025-01-05", periods=8, freq="MS")
    df = pd.DataFrame(
        {
            "booking_date": dates,
            "amount": [-3200, -3300, -3150, -3350, -3250, -3400, -3300, -3200],
            "direction": ["debit"] * 8,
            "merchant": ["Jan Kowalski"] * 8,
            "category": ["housing"] * 8,
            "transaction_type": ["purchase"] * 8,
        }
    )

    res = detect_anomalies(df)

    assert not res.df["anomaly"].any()
    assert res.df["is_recurring_merchant"].all()


def test_regular_merchant_amount_spike_is_anomaly() -> None:
    dates = pd.date_range("2025-01-05", periods=8, freq="MS")
    amounts = [-3000, -3050, -3100, -3000, -3025, -3075, -3050, -7000]
    df = pd.DataFrame(
        {
            "booking_date": dates,
            "amount": amounts,
            "direction": ["debit"] * 8,
            "merchant": ["Jan Kowalski"] * 8,
            "category": ["housing"] * 8,
            "transaction_type": ["purchase"] * 8,
        }
    )

    res = detect_anomalies(df)

    assert bool(res.df.loc[7, "anomaly"])
    assert res.df.loc[7, "anomaly_type"] == "merchant_amount_outlier"
    assert "merchant-amount-outlier" in res.df.loc[7, "reason_codes"]


def test_medium_retail_merchant_spikes_do_not_flood_review() -> None:
    dates = pd.date_range("2025-01-01", periods=10, freq="MS")
    df = pd.DataFrame(
        {
            "booking_date": dates,
            "amount": [-80, -120, -95, -110, -100, -140, -90, -780, -820, -930],
            "direction": ["debit"] * 10,
            "merchant": ["Allegro"] * 10,
            "category": ["shopping"] * 10,
            "transaction_type": ["purchase"] * 10,
        }
    )

    res = detect_anomalies(df)

    assert not res.df["anomaly"].any()


def test_new_large_merchant_gets_review_priority() -> None:
    df = _normal_txs(40)
    df["transaction_type"] = "purchase"
    df.loc[5, "amount"] = -3000.0
    df.loc[5, "merchant"] = "KRAJOWY INTEGRATOR PŁATNOŚCI S.A."

    res = detect_anomalies(df)

    assert bool(res.df.loc[5, "anomaly"])
    assert res.df.loc[5, "anomaly_type"] in {"unexpected_large", "suspicious"}
    assert res.df.loc[5, "priority_score"] >= 0.45


def test_large_missing_context_is_data_quality_or_suspicious() -> None:
    df = _normal_txs(40)
    df["transaction_type"] = "purchase"
    df.loc[5, "amount"] = -20000.0
    df.loc[5, "merchant"] = ""
    df.loc[5, "category"] = None

    res = detect_anomalies(df)

    assert bool(res.df.loc[5, "anomaly"])
    assert res.df.loc[5, "anomaly_type"] in {"data_quality", "suspicious"}
    assert "missing-merchant-large" in res.df.loc[5, "reason_codes"]


def test_model_only_is_separate_low_priority_type() -> None:
    df = _normal_txs(40)
    res = detect_anomalies(df, contamination=0.2)
    model_only = res.df[res.df["anomaly_type"] == "model_only"]

    assert not model_only.empty
    assert (model_only["priority_score"] <= 0.35).all()


def test_subscription_detected_for_monthly_payment() -> None:
    dates = pd.date_range("2025-09-15", periods=6, freq="30D")
    df = pd.DataFrame({
        "booking_date": dates,
        "amount": [-29.99] * 6,
        "direction": ["debit"] * 6,
        "merchant": ["Spotify Premium"] * 6,
        "category": ["subscriptions"] * 6,
    })
    subs = detect_subscriptions(df)
    assert len(subs) == 1
    s = subs[0]
    assert s.cadence == "monthly"
    assert s.occurrences == 6
    assert abs(s.median_amount - 29.99) < 0.01
    assert s.confidence >= 0.8  # whitelisted Spotify with regular amount


def test_subscription_uses_raw_merchant_for_display() -> None:
    dates = pd.date_range("2025-09-15", periods=3, freq="30D")
    df = pd.DataFrame({
        "booking_date": dates,
        "amount": [-67.99] * 3,
        "direction": ["debit"] * 3,
        "merchant": [
            "NETFLIX.COM AMSTERDAM",
            "NETFLIX.COM AMSTERDAM",
            "NETFLIX.COM AMSTERDAM",
        ],
        "category": ["subscriptions"] * 3,
    })

    subs = detect_subscriptions(df)

    assert len(subs) == 1
    assert subs[0].merchant == "NETFLIX.COM AMSTERDAM"
    assert subs[0].merchant_key == "netflix com amsterdam"


def test_subscription_display_compacts_repeated_descriptor() -> None:
    dates = pd.date_range("2025-09-15", periods=3, freq="30D")
    df = pd.DataFrame({
        "booking_date": dates,
        "amount": [-43.63] * 3,
        "direction": ["debit"] * 3,
        "merchant": ["NETFLIX.COM NETFLIX.COM"] * 3,
        "category": ["subscriptions"] * 3,
    })

    subs = detect_subscriptions(df)

    assert len(subs) == 1
    assert subs[0].merchant == "NETFLIX.COM"
    assert subs[0].merchant_key == "netflix com netflix com"


def test_subscription_blacklist_rejects_grocery() -> None:
    # Even with 4 monthly visits, Biedronka should never be a subscription.
    dates = pd.date_range("2025-09-15", periods=4, freq="30D")
    df = pd.DataFrame({
        "booking_date": dates,
        "amount": [-50.0] * 4,
        "direction": ["debit"] * 4,
        "merchant": ["BIEDRONKA"] * 4,
        "category": ["food"] * 4,
    })
    assert detect_subscriptions(df) == []


def test_subscription_rejects_short_history() -> None:
    # 2 weekly transactions in 7 days — span < 1.5 × 7 = 10.5 days.
    df = pd.DataFrame({
        "booking_date": pd.to_datetime(["2026-04-01", "2026-04-08"]),
        "amount": [-10.99, -10.99],
        "direction": ["debit", "debit"],
        "merchant": ["Some shop", "Some shop"],
        "category": [None, None],
    })
    assert detect_subscriptions(df) == []


def test_subscription_rejects_irregular_amounts() -> None:
    dates = pd.date_range("2025-09-15", periods=4, freq="30D")
    df = pd.DataFrame({
        "booking_date": dates,
        "amount": [-30.0, -120.0, -45.0, -10.0],  # wildly different
        "direction": ["debit"] * 4,
        "merchant": ["Random shop"] * 4,
        "category": [None] * 4,
    })
    assert detect_subscriptions(df) == []


def test_subscription_handles_empty_frame() -> None:
    assert detect_subscriptions(pd.DataFrame(
        columns=["booking_date", "amount", "direction", "merchant"]
    )) == []


def test_subscription_excludes_transfers_and_savings() -> None:
    dates = pd.date_range("2025-09-15", periods=6, freq="30D")
    df = pd.DataFrame({
        "booking_date": list(dates) + list(dates),
        "amount": [-500.0] * 12,
        "direction": ["debit"] * 12,
        "merchant": ["Own transfer"] * 6 + ["Savings account"] * 6,
        "category": ["subscriptions"] * 6 + ["savings"] * 6,
        "is_transfer": [True] * 6 + [False] * 6,
    })
    assert detect_subscriptions(df) == []


def test_subscription_excludes_non_candidate_transaction_types() -> None:
    dates = pd.date_range("2025-09-15", periods=6, freq="30D")
    df = pd.DataFrame({
        "booking_date": list(dates) + list(dates),
        "amount": [-29.99] * 12,
        "direction": ["debit"] * 12,
        "merchant": ["Spotify Premium"] * 6 + ["OpenAI"] * 6,
        "category": ["subscriptions"] * 12,
        "is_transfer": ["false"] * 12,
        "transaction_type": ["refund"] * 6 + ["own_transfer"] * 6,
    })

    assert detect_subscriptions(df) == []
