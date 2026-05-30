"""Tests for anomaly detector + subscription detector."""
import numpy as np
import pandas as pd

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
