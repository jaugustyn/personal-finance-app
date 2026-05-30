"""Heuristic subscription detector.

A subscription candidate has:
  - >=N debit transactions to the same normalised merchant
  - amount within ±AMOUNT_TOL of the median
  - median inter-arrival close to one of {7, 14, 30, 365} days (±DAY_TOL)
  - history span >= 1.5 × cadence (rules out 2 same-week random purchases)
  - merchant not on the blacklist of grocery/retail chains
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from finance.transactions.normalization import normalize_merchant

CADENCES: dict[str, int] = {
    "weekly": 7,
    "biweekly": 14,
    "monthly": 30,
    "yearly": 365,
}
AMOUNT_TOL = 0.10  # ±10 % — forgiving for FX/price tweaks
DAY_TOL = 5  # days — weekends shift booking dates
MIN_OCCURRENCES = 2  # short data window: 2 hits is enough to suggest a sub
MIN_SPAN_RATIO = 1.5  # require span >= 1.5 × cadence (rules out random twin buys)

# Substrings (lowercased, normalised) of merchants that are almost never
# real subscriptions — grocery / retail chains. Prevents false positives like
# "Empik weekly 10.99".
DEFAULT_BLACKLIST: tuple[str, ...] = (
    "biedronka", "lidl", "carrefour", "kaufland", "auchan", "tesco", "stokrotka",
    "zabka", "rossmann", "hebe", "drogeria", "empik", "media markt", "ikea",
    "decathlon", "leroy", "castorama", "jysk", "mcdonalds", "kfc", "burger king",
    "starbucks", "costa", "orlen", "shell", "bp", "circle k", "lotos",
)
# Substrings (lowercased) of well-known subscription providers that should be
# flagged even if they fail amount-stability (e.g. annual price hike).
DEFAULT_WHITELIST: tuple[str, ...] = (
    "spotify", "netflix", "hbo", "disney", "apple.com/bill", "icloud",
    "google one", "google storage", "youtube premium", "openai", "chatgpt",
    "github", "jetbrains", "anthropic",
)


@dataclass
class Subscription:
    merchant: str
    cadence: str
    median_amount: float
    occurrences: int
    last_seen: pd.Timestamp
    estimated_monthly_cost: float
    confidence: float  # 0..1
    samples: pd.DataFrame


EXCLUDED_CATEGORIES: set[str] = {"savings", "income", "salary", "transfer"}


def _normalise(name: str | None) -> str:
    return normalize_merchant(name)


def _classify_cadence(median_days: float, *, day_tol: int = DAY_TOL) -> str | None:
    for label, target in CADENCES.items():
        if abs(median_days - target) <= day_tol:
            return label
    return None


def _monthly_cost(amount: float, cadence: str) -> float:
    days = CADENCES[cadence]
    return float(amount) * (30.4375 / days)


def _is_blacklisted(name: str, blacklist: tuple[str, ...]) -> bool:
    return any(b in name for b in blacklist)


def _is_whitelisted(name: str, whitelist: tuple[str, ...]) -> bool:
    return any(w in name for w in whitelist)


def detect_subscriptions(
    df: pd.DataFrame,
    *,
    min_occurrences: int = MIN_OCCURRENCES,
    amount_tol: float = AMOUNT_TOL,
    day_tol: int = DAY_TOL,
    min_span_ratio: float = MIN_SPAN_RATIO,
    blacklist: tuple[str, ...] = DEFAULT_BLACKLIST,
    whitelist: tuple[str, ...] = DEFAULT_WHITELIST,
) -> list[Subscription]:
    """Return subscription candidates sorted by estimated monthly cost desc.

    Confidence score combines: occurrence count, amount stability, cadence
    regularity, and history span. Whitelist always passes (confidence=1.0);
    blacklist always rejects.
    """
    if df.empty:
        return []
    d = df[df["direction"] == "debit"].copy()
    if d.empty:
        return []
    if "is_transfer" in d.columns:
        d = d[~d["is_transfer"].fillna(False).astype(bool)]
    if "category" in d.columns:
        category = d["category"].fillna("").astype(str).str.lower()
        d = d[~category.isin(EXCLUDED_CATEGORIES)]
    if d.empty:
        return []
    d["booking_date"] = pd.to_datetime(d["booking_date"])
    if "abs_amount" not in d.columns:
        d["abs_amount"] = d["amount"].abs().astype(float)
    d["merchant_norm"] = d["merchant"].fillna("").map(_normalise)
    d = d[d["merchant_norm"].str.len() > 0]

    out: list[Subscription] = []
    for merch, group in d.groupby("merchant_norm"):
        whitelisted = _is_whitelisted(merch, whitelist)
        if _is_blacklisted(merch, blacklist) and not whitelisted:
            continue
        if len(group) < min_occurrences:
            continue
        amounts = group["abs_amount"].astype(float).values
        med = float(np.median(amounts))
        if med <= 0:
            continue
        amount_dev = float(np.max(np.abs(amounts - med) / med))
        if amount_dev > amount_tol and not whitelisted:
            continue
        dates = np.sort(group["booking_date"].values).astype("datetime64[D]")
        diffs = np.diff(dates).astype("timedelta64[D]").astype(int)
        if len(diffs) == 0:
            continue
        median_days = float(np.median(diffs))
        cadence = _classify_cadence(median_days, day_tol=day_tol)
        if cadence is None:
            continue
        # History span check: span >= min_span_ratio × cadence.
        span_days = int((dates.max() - dates.min()).astype(int))
        cadence_days = CADENCES[cadence]
        if span_days < min_span_ratio * cadence_days and not whitelisted:
            continue

        # Confidence: blend of (occurrences, amount stability, cadence regularity, span).
        occ_score = min(len(group) / 6.0, 1.0)
        amt_score = max(0.0, 1.0 - amount_dev / max(amount_tol, 1e-6))
        if len(diffs) >= 2:
            cad_cv = float(np.std(diffs) / max(np.mean(diffs), 1e-6))
            cad_score = max(0.0, 1.0 - cad_cv)
        else:
            cad_score = 0.5
        span_score = min(span_days / (cadence_days * 3), 1.0)
        confidence = round(
            0.30 * occ_score + 0.25 * amt_score + 0.25 * cad_score + 0.20 * span_score,
            3,
        )
        if whitelisted:
            confidence = max(confidence, 0.9)

        out.append(
            Subscription(
                merchant=merch,
                cadence=cadence,
                median_amount=round(med, 2),
                occurrences=len(group),
                last_seen=pd.Timestamp(dates.max()),
                estimated_monthly_cost=round(_monthly_cost(med, cadence), 2),
                confidence=confidence,
                samples=group.reset_index(drop=True),
            )
        )
    out.sort(key=lambda s: s.estimated_monthly_cost, reverse=True)
    return out
