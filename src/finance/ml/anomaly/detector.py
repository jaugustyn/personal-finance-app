"""Hybrid anomaly detector: IsolationForest + heuristic rules."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

# Categories that are by nature large + recurring (salary, transfers between own
# accounts, savings deposits) — exclude from anomaly flags.
EXCLUDED_CATEGORIES: set[str] = {"salary", "income", "savings", "transfer"}

# Map internal reason codes → user-facing Polish text.
REASON_PL: dict[str, str] = {
    "amount-outlier": "nietypowo wysoka kwota",
    "new-merchant-large-debit": "nowy odbiorca + duża kwota",
    "isolation-forest": "nietypowy wzorzec (model)",
}


@dataclass
class AnomalyResult:
    df: pd.DataFrame  # original frame + columns: anomaly, severity, reasons


def _merchant_freq(df: pd.DataFrame) -> pd.Series:
    key = df["merchant"].fillna("").str.lower().str.strip()
    return df.groupby(key)["merchant"].transform("count")


def _amount_zscore_per_category(df: pd.DataFrame) -> pd.Series:
    """Robust z-score using median + MAD per (category, direction)."""
    out = pd.Series(0.0, index=df.index)
    grp = df.groupby([df["category"].fillna("__none"), df["direction"]])
    for _, idx in grp.groups.items():
        sub = df.loc[idx, "abs_amount"].astype(float)
        med = float(sub.median())
        mad = float((sub - med).abs().median())
        if mad < 1e-9:
            continue
        out.loc[idx] = 0.6745 * (sub - med) / mad
    return out


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Numeric matrix used by IsolationForest."""
    d = df.copy()
    d["booking_date"] = pd.to_datetime(d["booking_date"])
    if "abs_amount" not in d:
        d["abs_amount"] = d["amount"].abs().astype(float)
    else:
        d["abs_amount"] = d["abs_amount"].astype(float)
    d["log_abs"] = np.log1p(d["abs_amount"])
    d["dow"] = d["booking_date"].dt.dayofweek
    d["dom"] = d["booking_date"].dt.day
    d["merchant_freq"] = _merchant_freq(d)
    d["amount_z"] = _amount_zscore_per_category(d)
    d["is_debit"] = (d["direction"] == "debit").astype(int)
    return d[["log_abs", "dow", "dom", "merchant_freq", "amount_z", "is_debit"]]


def detect_anomalies(
    df: pd.DataFrame,
    *,
    contamination: float = 0.05,
    z_threshold: float = 3.5,
    new_merchant_threshold: int = 1,
    seed: int = 42,
    direction: str | None = "debit",
    excluded_categories: set[str] | None = None,
) -> AnomalyResult:
    """Run hybrid detection. Returns the original df with extra columns.

    Required df columns: booking_date, amount, direction, merchant, category.

    Args:
        direction: filter to 'debit'/'credit' before scoring; None = both.
        excluded_categories: categories to never flag (defaults to salary/income/transfers).
    """
    if df.empty:
        return AnomalyResult(df=df.assign(anomaly=False, severity=0.0, reasons=""))

    work = df.copy().reset_index(drop=True)
    work["booking_date"] = pd.to_datetime(work["booking_date"])
    if "abs_amount" not in work.columns:
        work["abs_amount"] = work["amount"].abs().astype(float)
    if "is_transfer" not in work.columns:
        work["is_transfer"] = False

    if direction is not None:
        # Keep rows of the requested direction; others get anomaly=False later.
        mask_dir = work["direction"] == direction
    else:
        mask_dir = pd.Series(True, index=work.index)

    excluded = excluded_categories if excluded_categories is not None else EXCLUDED_CATEGORIES
    cat_lower = work["category"].fillna("").astype(str).str.lower()
    mask_cat = ~cat_lower.isin(excluded)
    mask_transfer = ~work["is_transfer"].fillna(False).astype(bool)

    eligible = mask_dir & mask_cat & mask_transfer
    feats = _build_features(work)

    # Isolation Forest score (higher = more anomalous).
    n = len(work)
    if eligible.sum() >= 20:
        iso = IsolationForest(
            contamination=contamination, random_state=seed, n_estimators=200
        )
        iso.fit(feats[eligible])
        iso_score = np.zeros(n)
        iso_score[eligible] = -iso.decision_function(feats[eligible])
        iso_flag = np.zeros(n, dtype=bool)
        iso_flag[eligible] = iso.predict(feats[eligible]) == -1
    else:
        iso_score = np.zeros(n)
        iso_flag = np.zeros(n, dtype=bool)

    # Rules.
    reasons: list[list[str]] = [[] for _ in range(n)]
    z = np.asarray(feats["amount_z"].values)
    eligible_arr = np.asarray(eligible.values)
    for i in range(n):
        if eligible_arr[i] and abs(z[i]) >= z_threshold:
            reasons[i].append(REASON_PL["amount-outlier"] + f" (z={z[i]:.1f})")
    new_merchant = np.asarray(feats["merchant_freq"].values) <= new_merchant_threshold
    debit = np.asarray(work["direction"].values) == "debit"
    big_debit = np.asarray(work["abs_amount"].values) > work["abs_amount"].quantile(0.95)
    for i in range(n):
        if eligible_arr[i] and new_merchant[i] and debit[i] and big_debit[i]:
            reasons[i].append(REASON_PL["new-merchant-large-debit"])
        if eligible_arr[i] and iso_flag[i]:
            reasons[i].append(REASON_PL["isolation-forest"])

    # Severity: blended Iso-Forest score + |z|.
    if n:
        rng = float(iso_score.max() - iso_score.min())
        iso_norm = (iso_score - iso_score.min()) / (rng + 1e-9)
    else:
        iso_norm = np.zeros(n)
    severity = 0.5 * iso_norm + 0.5 * np.minimum(np.abs(z) / 6.0, 1.0)
    severity = np.where(eligible_arr, severity, 0.0)
    anomaly = eligible_arr & (
        iso_flag
        | (np.abs(z) >= z_threshold)
        | (new_merchant & debit & big_debit)
    )

    out = work.assign(
        anomaly=anomaly,
        severity=severity.round(3),
        reasons=[", ".join(r) if r else "" for r in reasons],
    )
    return AnomalyResult(df=out)
