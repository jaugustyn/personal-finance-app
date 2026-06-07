"""Hybrid anomaly detector: IsolationForest + heuristic rules."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from finance.analytics.filters import expense_category_candidate_mask

# Legacy/non-expense category labels that may exist in older imports. Current
# data should represent these via transaction_type/is_transfer instead.
EXCLUDED_CATEGORIES: set[str] = {"salary", "income", "savings", "transfer"}
ANOMALY_EXCLUDED_TRANSACTION_TYPES: set[str] = {"savings_investment"}
MIN_RECURRING_MERCHANT_OCCURRENCES = 4
NEW_MERCHANT_MIN_AMOUNT = 1000.0
AMOUNT_OUTLIER_MIN_AMOUNT = 1000.0
MERCHANT_OUTLIER_MIN_AMOUNT = 1000.0
MERCHANT_OUTLIER_RATIO_THRESHOLD = 2.5
MERCHANT_OUTLIER_Z_THRESHOLD = 3.5
MODEL_ONLY_PRIORITY_CUTOFF = 0.35
MERCHANT_OUTLIER_MIN_AMOUNT_BY_CATEGORY = {
    "food": 500.0,
    "shopping": 1500.0,
}

# Map internal reason codes → user-facing Polish text.
REASON_PL: dict[str, str] = {
    "amount-outlier": "nietypowo wysoka kwota",
    "merchant-amount-outlier": "nietypowa kwota dla tego odbiorcy",
    "new-merchant-large-debit": "nowy odbiorca + duża kwota",
    "missing-merchant-large": "duża kwota bez nazwy odbiorcy",
    "missing-category-large": "duża kwota bez kategorii",
    "isolation-forest": "nietypowy wzorzec (model)",
}


@dataclass
class AnomalyResult:
    df: pd.DataFrame  # original frame + columns: anomaly, severity, reasons


def _merchant_freq(df: pd.DataFrame) -> pd.Series:
    key = _merchant_key(df)
    return df.groupby(key)["merchant"].transform("count")


def _merchant_key(df: pd.DataFrame) -> pd.Series:
    return df["merchant"].fillna("").astype(str).str.lower().str.strip()


def _amount_zscore_per_category(
    df: pd.DataFrame,
    *,
    min_group_size: int = 8,
) -> pd.Series:
    """Robust z-score using median + MAD per (category, direction)."""
    out = pd.Series(0.0, index=df.index)
    grp = df.groupby([df["category"].fillna("__none"), df["direction"]])
    for _, idx in grp.groups.items():
        if len(idx) < min_group_size:
            continue
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


def _merchant_outlier_min_amount(category: object) -> float:
    key = "" if category is None else str(category).lower()
    return MERCHANT_OUTLIER_MIN_AMOUNT_BY_CATEGORY.get(
        key,
        MERCHANT_OUTLIER_MIN_AMOUNT,
    )


def _is_monthly_recurring(dates: pd.Series) -> bool:
    ordered = pd.to_datetime(dates).sort_values()
    if len(ordered) < MIN_RECURRING_MERCHANT_OCCURRENCES:
        return False
    span_days = int((ordered.iloc[-1] - ordered.iloc[0]).days)
    if span_days < 75:
        return False
    diffs = ordered.diff().dropna().dt.days.astype(int)
    if not diffs.empty:
        monthly_like = ((diffs >= 25) & (diffs <= 35)).mean() >= 0.5
        if monthly_like:
            return True
    dom = ordered.dt.day.astype(int)
    return int(dom.max() - dom.min()) <= 14


def _merchant_context(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    out["merchant_key"] = _merchant_key(df)
    out["merchant_occurrences"] = _merchant_freq(df).fillna(0).astype(int)
    out["merchant_median_amount"] = 0.0
    out["merchant_amount_ratio"] = 0.0
    out["merchant_amount_z"] = 0.0
    out["is_recurring_merchant"] = False

    for merchant_key, idx in out.groupby("merchant_key").groups.items():
        if not merchant_key:
            continue
        sub = df.loc[idx, "abs_amount"].astype(float)
        median = float(sub.median())
        if median <= 0:
            continue
        out.loc[idx, "merchant_median_amount"] = median
        out.loc[idx, "merchant_amount_ratio"] = sub / median
        if len(idx) >= MIN_RECURRING_MERCHANT_OCCURRENCES:
            mad = float((sub - median).abs().median())
            if mad >= 1e-9:
                out.loc[idx, "merchant_amount_z"] = 0.6745 * (sub - median) / mad
            out.loc[idx, "is_recurring_merchant"] = _is_monthly_recurring(
                df.loc[idx, "booking_date"]
            )
    return out


def _amount_percentile(values: pd.Series) -> np.ndarray:
    if values.empty:
        return np.asarray([], dtype=float)
    return values.rank(method="average", pct=True).fillna(0.0).to_numpy(dtype=float)


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
        return AnomalyResult(
            df=df.assign(
                anomaly=False,
                severity=0.0,
                priority_score=0.0,
                anomaly_type="none",
                reasons="",
                reason_codes=[[] for _ in range(len(df))],
                merchant_occurrences=0,
                merchant_median_amount=0.0,
                is_recurring_merchant=False,
            )
        )

    work = df.copy().reset_index(drop=True)
    work["booking_date"] = pd.to_datetime(work["booking_date"])
    if "abs_amount" not in work.columns:
        work["abs_amount"] = work["amount"].abs().astype(float)
    if "is_transfer" not in work.columns:
        work["is_transfer"] = False
    if "transaction_type" not in work.columns:
        work["transaction_type"] = "purchase"
    if "category" not in work.columns:
        work["category"] = None

    excluded = excluded_categories if excluded_categories is not None else EXCLUDED_CATEGORIES
    cat_lower = work["category"].fillna("").astype(str).str.lower()
    mask_cat = ~cat_lower.isin(excluded)
    candidate = expense_category_candidate_mask(work, direction=direction)
    tx_type = work["transaction_type"].fillna("purchase").astype(str)
    mask_tx_type = ~tx_type.isin(ANOMALY_EXCLUDED_TRANSACTION_TYPES)

    eligible = candidate & mask_cat & mask_tx_type
    feats = _build_features(work)
    merchant_ctx = _merchant_context(work)

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
    reason_codes: list[list[str]] = [[] for _ in range(n)]
    anomaly_types = np.asarray(["none"] * n, dtype=object)
    z = np.asarray(feats["amount_z"].values)
    eligible_arr = np.asarray(eligible.values)
    recurring = np.asarray(merchant_ctx["is_recurring_merchant"].values, dtype=bool)
    merchant_occ = np.asarray(merchant_ctx["merchant_occurrences"].values, dtype=int)
    merchant_ratio = np.asarray(merchant_ctx["merchant_amount_ratio"].values, dtype=float)
    merchant_z = np.asarray(merchant_ctx["merchant_amount_z"].values, dtype=float)
    amount = np.asarray(work["abs_amount"].values, dtype=float)
    debit = np.asarray(work["direction"].values) == "debit"

    eligible_amount = work.loc[eligible, "abs_amount"].astype(float)
    global_large_threshold = (
        max(NEW_MERCHANT_MIN_AMOUNT, float(eligible_amount.quantile(0.95)))
        if not eligible_amount.empty
        else NEW_MERCHANT_MIN_AMOUNT
    )
    very_large_threshold = (
        max(10000.0, float(eligible_amount.quantile(0.99)))
        if not eligible_amount.empty
        else 10000.0
    )
    amount_rank = np.zeros(n, dtype=float)
    if not eligible_amount.empty:
        ranks = _amount_percentile(work.loc[eligible, "abs_amount"].astype(float))
        amount_rank[np.asarray(eligible.values)] = ranks

    def add_reason(index: int, code: str, detail: str | None = None) -> None:
        text = REASON_PL[code]
        if detail:
            text = f"{text} ({detail})"
        if code not in reason_codes[index]:
            reason_codes[index].append(code)
            reasons[index].append(text)

    def promote_type(index: int, candidate: str) -> None:
        order = {
            "none": 0,
            "model_only": 1,
            "unexpected_large": 2,
            "merchant_amount_outlier": 3,
            "data_quality": 4,
            "suspicious": 5,
        }
        if order[candidate] > order[str(anomaly_types[index])]:
            anomaly_types[index] = candidate

    for i in range(n):
        if not eligible_arr[i]:
            continue
        merchant_min_amount = _merchant_outlier_min_amount(work.loc[i, "category"])
        merchant_outlier = (
            merchant_occ[i] >= MIN_RECURRING_MERCHANT_OCCURRENCES
            and amount[i] >= merchant_min_amount
            and (
                merchant_ratio[i] >= MERCHANT_OUTLIER_RATIO_THRESHOLD
                or abs(merchant_z[i]) >= MERCHANT_OUTLIER_Z_THRESHOLD
            )
        )
        if recurring[i] and not merchant_outlier:
            continue
        if abs(z[i]) >= z_threshold and amount[i] >= AMOUNT_OUTLIER_MIN_AMOUNT:
            add_reason(i, "amount-outlier")
            promote_type(i, "unexpected_large")
        if merchant_outlier:
            add_reason(i, "merchant-amount-outlier")
            promote_type(i, "merchant_amount_outlier")

    merchant_key = np.asarray(merchant_ctx["merchant_key"].values, dtype=object)
    new_merchant = (merchant_occ <= new_merchant_threshold) & (merchant_key != "")
    big_debit = amount >= global_large_threshold
    missing_merchant = np.asarray(work["merchant"].fillna("").astype(str).str.strip() == "")
    missing_category = np.asarray(work["category"].isna() | (work["category"].astype(str) == ""))
    for i in range(n):
        if eligible_arr[i] and new_merchant[i] and debit[i] and big_debit[i]:
            add_reason(i, "new-merchant-large-debit")
            promote_type(
                i,
                "suspicious"
                if (missing_category[i] and amount[i] >= very_large_threshold)
                else "unexpected_large",
            )
        if eligible_arr[i] and missing_merchant[i] and debit[i] and big_debit[i]:
            add_reason(i, "missing-merchant-large")
            promote_type(i, "data_quality")
        if eligible_arr[i] and missing_category[i] and debit[i] and big_debit[i]:
            add_reason(i, "missing-category-large")
            promote_type(
                i,
                "suspicious" if amount[i] >= very_large_threshold else "data_quality",
            )
        if eligible_arr[i] and iso_flag[i]:
            add_reason(i, "isolation-forest")
            promote_type(i, "model_only")

    # Severity: technical score. Priority is a user-facing review ranking.
    if n:
        rng = float(iso_score.max() - iso_score.min())
        iso_norm = (iso_score - iso_score.min()) / (rng + 1e-9)
    else:
        iso_norm = np.zeros(n)
    severity = 0.35 * iso_norm + 0.65 * np.minimum(np.abs(z) / 12.0, 1.0)
    severity = np.where(eligible_arr, severity, 0.0)
    type_base = {
        "none": 0.0,
        "model_only": 0.22,
        "unexpected_large": 0.42,
        "merchant_amount_outlier": 0.48,
        "data_quality": 0.6,
        "suspicious": 0.78,
    }
    priority = np.asarray([type_base[str(value)] for value in anomaly_types], dtype=float)
    priority += 0.15 * amount_rank
    priority += 0.04 * iso_norm
    priority += 0.05 * np.minimum(np.abs(z) / 20.0, 1.0)
    priority = np.where(eligible_arr, np.clip(priority, 0.0, 1.0), 0.0)
    priority = np.where(
        anomaly_types == "model_only",
        np.minimum(priority, MODEL_ONLY_PRIORITY_CUTOFF),
        priority,
    )
    anomaly = eligible_arr & (anomaly_types != "none")

    out = work.assign(
        anomaly=anomaly,
        severity=severity.round(3),
        priority_score=priority.round(3),
        anomaly_type=anomaly_types,
        reasons=[", ".join(r) if r else "" for r in reasons],
        reason_codes=reason_codes,
        merchant_occurrences=merchant_ctx["merchant_occurrences"].astype(int),
        merchant_median_amount=merchant_ctx["merchant_median_amount"].round(2),
        is_recurring_merchant=merchant_ctx["is_recurring_merchant"].astype(bool),
    )
    return AnomalyResult(df=out)
