"""Projection helpers for subscription review rows and KPIs."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from finance.domain.enums import Category, CategorySource
from finance.domain.models import SubscriptionPreference
from finance.ml.feedback import EVENT_SUBSCRIPTION_REJECTED
from finance.ml.subscriptions.detector import CADENCES
from finance.ml.subscriptions.types import (
    ANNUAL_RENEWAL_WINDOW_DAYS,
    PRICE_CHANGE_ABSOLUTE_THRESHOLD,
    PRICE_CHANGE_RELATIVE_THRESHOLD,
    REVIEW_CONFIDENCE_THRESHOLD,
    UPCOMING_WINDOW_DAYS,
    SubscriptionOverview,
    SubscriptionReviewRow,
    SubscriptionTransactionSample,
    SubscriptionUpcomingPayment,
    SubscriptionUserDecision,
)


def subscription_key(merchant_norm: str, currency: str | None) -> str:
    currency = str(currency or "").lower()
    return f"{merchant_norm}|{currency}" if currency else merchant_norm


def user_decision(
    key: str,
    *,
    preferences: dict[str, SubscriptionPreference],
    feedback_decisions: dict[str, str],
) -> SubscriptionUserDecision:
    pref = preferences.get(key)
    if pref and pref.confirmed:
        return "confirmed"
    if feedback_decisions.get(key) == EVENT_SUBSCRIPTION_REJECTED:
        return "rejected"
    return "suggested"


def _cadence_days(cadence: str) -> int | None:
    return CADENCES.get(cadence)


def monthly_ratio(cadence: str) -> float:
    if cadence == "monthly":
        return 1.0
    if cadence == "yearly":
        return 1.0 / 12.0
    if cadence == "weekly":
        return 52.0 / 12.0
    if cadence == "biweekly":
        return 26.0 / 12.0
    days = _cadence_days(cadence)
    if not days:
        return 1.0
    return 30.4375 / days


def infer_cadence(samples: pd.DataFrame, *, fallback: str = "unknown") -> str:
    if len(samples) < 2:
        return fallback
    dates = pd.to_datetime(samples["booking_date"]).sort_values().tolist()
    diffs = [
        int((right.date() - left.date()).days)
        for left, right in zip(dates, dates[1:], strict=False)
    ]
    if not diffs:
        return fallback
    median_days = float(pd.Series(diffs).median())
    for label, days in CADENCES.items():
        if abs(median_days - days) <= 7:
            return label
    return fallback


def next_expected(last_seen: date, cadence: str) -> date | None:
    days = _cadence_days(cadence)
    if not days:
        return None
    return last_seen + timedelta(days=days)


def status_for(
    *,
    cadence: str,
    confidence: float,
    is_confirmed: bool,
    source: str,
    occurrences: int,
    next_expected_date: date | None,
    last_seen: date,
    price_change_pct: float | None,
    as_of: date,
) -> str:
    cadence_days = _cadence_days(cadence)
    if next_expected_date and cadence_days:
        overdue_days = (as_of - next_expected_date).days
        if overdue_days >= cadence_days:
            return "probably_cancelled"
        if overdue_days > 7:
            return "paused_or_missing"
        if cadence == "yearly" and timedelta(0) <= next_expected_date - as_of <= timedelta(
            days=ANNUAL_RENEWAL_WINDOW_DAYS
        ):
            return "annual_renewal"
    if cadence_days is None:
        stale_days = (as_of - last_seen).days
        if stale_days >= 180:
            return "probably_cancelled"
        if stale_days >= 60:
            return "paused_or_missing"
    if price_change_pct is not None and price_change_pct > 0:
        return "price_increased"
    if not is_confirmed and confidence < REVIEW_CONFIDENCE_THRESHOLD:
        return "needs_review"
    if source == "category" and occurrences < 2:
        return "needs_review"
    if not is_confirmed:
        return "new"
    return "active"


def price_change(samples: pd.DataFrame) -> tuple[float | None, float | None, float | None]:
    if len(samples) < 2:
        return None, None, None
    ordered = samples.sort_values("booking_date")
    amounts = ordered["amount_base"].abs().astype(float).tolist()
    if len(amounts) < 2:
        return None, None, None
    current = round(float(amounts[-1]), 2)
    previous = round(float(pd.Series(amounts[:-1]).median()), 2)
    if previous <= 0:
        return previous, current, None
    pct = (current - previous) / previous
    pct_result: float | None = pct
    if (
        abs(pct) < PRICE_CHANGE_RELATIVE_THRESHOLD
        or abs(current - previous) < PRICE_CHANGE_ABSOLUTE_THRESHOLD
    ):
        pct_result = None
    return (
        previous,
        current,
        round(pct_result * 100, 2) if pct_result is not None else None,
    )


def sample_evidence(
    samples: pd.DataFrame,
    *,
    source: str,
    cadence: str,
    confidence: float,
) -> dict[str, object]:
    dates = [
        value.date().isoformat() if hasattr(value, "date") else str(value)
        for value in pd.to_datetime(samples["booking_date"]).sort_values().tail(6).tolist()
    ]
    amount_stability = None
    amounts = samples["amount_base"].abs().astype(float).tolist()
    if amounts:
        median = float(pd.Series(amounts).median())
        if median > 0:
            max_dev = max(abs(value - median) / median for value in amounts)
            amount_stability = round(max(0.0, 1.0 - max_dev), 3)
    return {
        "source": source,
        "occurrences": int(len(samples)),
        "cadence": cadence,
        "confidence": round(float(confidence), 3),
        "amount_stability": amount_stability,
        "recent_dates": dates,
        "manual_category_count": int(
            (
                (samples["category"] == Category.SUBSCRIPTIONS)
                & (samples["category_source"] == CategorySource.MANUAL.value)
            ).sum()
        )
        if "category_source" in samples.columns
        else 0,
    }


def transaction_samples(samples: pd.DataFrame) -> list[SubscriptionTransactionSample]:
    out: list[SubscriptionTransactionSample] = []
    for row in samples.sort_values("booking_date", ascending=False).head(12).itertuples():
        booking_date = (
            row.booking_date.date()
            if hasattr(row.booking_date, "date")
            else row.booking_date
        )
        out.append(
            SubscriptionTransactionSample(
                id=int(row.transaction_id),
                booking_date=booking_date,
                merchant=str(row.merchant or ""),
                title=str(row.title or ""),
                amount=round(float(row.amount), 2),
                currency=str(row.currency or ""),
                amount_base=round(float(row.amount_base), 2),
                base_currency=str(row.base_currency or row.currency or ""),
                category=str(row.category) if row.category else None,
                category_source=str(row.category_source) if row.category_source else None,
            )
        )
    return out


def base_currency(samples: pd.DataFrame, fallback: str) -> str:
    if "base_currency" in samples.columns:
        currencies = [
            str(value)
            for value in samples["base_currency"].dropna().unique().tolist()
            if str(value)
        ]
        if currencies:
            return currencies[0]
    return fallback


def row_from_samples(
    *,
    merchant: str,
    merchant_key: str,
    currency: str,
    samples: pd.DataFrame,
    cadence: str,
    confidence: float,
    source: str,
    preference: SubscriptionPreference | None,
    as_of: date,
    user_decision: SubscriptionUserDecision = "suggested",
) -> SubscriptionReviewRow:
    ordered = samples.sort_values("booking_date")
    last_seen_raw = ordered["booking_date"].max()
    last_seen = last_seen_raw.date() if hasattr(last_seen_raw, "date") else last_seen_raw
    selected_base_currency = base_currency(samples, currency)
    base_amounts = [abs(float(value)) for value in samples["amount_base"].dropna().tolist()]
    original_amounts = [abs(float(value)) for value in samples["amount"].dropna().tolist()]
    median_base = float(pd.Series(base_amounts).median()) if base_amounts else 0.0
    median_original = float(pd.Series(original_amounts).median()) if original_amounts else 0.0
    ratio = monthly_ratio(cadence)
    previous_amount, current_amount, price_change_pct = price_change(samples)
    annual_impact = (
        round((current_amount - previous_amount) * ratio * 12, 2)
        if (
            price_change_pct is not None
            and previous_amount is not None
            and current_amount is not None
        )
        else None
    )
    next_expected_date = next_expected(last_seen, cadence)
    is_confirmed = bool(preference and preference.confirmed) or source == "category"
    display_name = (
        (preference.display_name if preference else None)
        or merchant
        or merchant_key.split("|")[0]
    )
    status = status_for(
        cadence=cadence,
        confidence=confidence,
        is_confirmed=is_confirmed,
        source=source,
        occurrences=len(samples),
        next_expected_date=next_expected_date,
        last_seen=last_seen,
        price_change_pct=price_change_pct,
        as_of=as_of,
    )
    return SubscriptionReviewRow(
        merchant=merchant,
        merchant_key=merchant_key,
        currency=currency,
        base_currency=selected_base_currency,
        cadence=cadence,
        median_amount=round(median_original, 2),
        occurrences=int(len(samples)),
        last_seen=last_seen,
        estimated_monthly_cost_original=round(median_original * ratio, 2),
        estimated_monthly_cost=round(median_base * ratio, 2),
        confidence=round(float(confidence), 3),
        status=status,
        source=source,
        next_expected_date=next_expected_date,
        previous_amount=previous_amount,
        current_amount=current_amount,
        price_change_pct=price_change_pct,
        price_change_annual_impact=annual_impact,
        evidence=sample_evidence(
            samples,
            source=source,
            cadence=cadence,
            confidence=confidence,
        ),
        is_confirmed=is_confirmed,
        user_decision=user_decision,
        display_name=display_name,
        transactions=transaction_samples(samples),
    )


def detected_subscription_row(
    sub,
    *,
    preference: SubscriptionPreference | None,
    user_decision: SubscriptionUserDecision = "suggested",
    as_of: date,
) -> SubscriptionReviewRow:
    cadence = (
        preference.cadence_override
        if preference and preference.cadence_override
        else sub.cadence
    )
    return row_from_samples(
        merchant=sub.merchant,
        merchant_key=sub.merchant_key,
        currency=sub.currency,
        samples=sub.samples,
        cadence=cadence,
        confidence=float(sub.confidence),
        source="detected",
        preference=preference,
        user_decision=user_decision,
        as_of=as_of,
    )


def category_subscription_rows(
    df: pd.DataFrame,
    *,
    preferences: dict[str, SubscriptionPreference],
    feedback_decisions: dict[str, str],
    detected_keys: set[str],
    as_of: date,
) -> list[SubscriptionReviewRow]:
    if df.empty:
        return []
    d = df[
        (df["category"] == Category.SUBSCRIPTIONS)
        & (df["category_source"] == CategorySource.MANUAL.value)
    ].copy()
    if d.empty:
        return []
    rows: list[SubscriptionReviewRow] = []
    for (merchant_norm, currency), group in d.groupby(
        ["merchant_norm", "currency"], dropna=False
    ):
        key = subscription_key(str(merchant_norm), str(currency or ""))
        if key in detected_keys:
            continue
        display = ""
        displays = group.sort_values("booking_date", ascending=False)[
            "merchant_display"
        ].fillna("").astype(str)
        for value in displays:
            if value.strip():
                display = value.strip()
                break
        cadence = infer_cadence(group)
        pref = preferences.get(key)
        if pref and pref.cadence_override:
            cadence = pref.cadence_override
        decision = user_decision(
            key,
            preferences=preferences,
            feedback_decisions=feedback_decisions,
        )
        if decision == "suggested":
            decision = "confirmed"
        rows.append(
            row_from_samples(
                merchant=display or str(merchant_norm),
                merchant_key=key,
                currency=str(currency or "").upper(),
                samples=group.reset_index(drop=True),
                cadence=cadence,
                confidence=1.0,
                source="category",
                preference=pref,
                user_decision=decision,
                as_of=as_of,
            )
        )
    return rows


def preference_only_rows(
    df: pd.DataFrame,
    *,
    preferences: dict[str, SubscriptionPreference],
    feedback_decisions: dict[str, str],
    existing_keys: set[str],
    as_of: date,
) -> list[SubscriptionReviewRow]:
    if df.empty:
        return []
    rows: list[SubscriptionReviewRow] = []
    for key, pref in preferences.items():
        if key in existing_keys:
            continue
        if "|" in key:
            merchant_norm, currency = key.rsplit("|", 1)
            group = df[
                (df["merchant_norm"] == merchant_norm)
                & (df["currency"].str.lower() == currency)
            ]
        else:
            merchant_norm = key
            group = df[df["merchant_norm"] == merchant_norm]
        if group.empty:
            continue
        cadence = pref.cadence_override or infer_cadence(group)
        rows.append(
            row_from_samples(
                merchant=pref.display_name or merchant_norm,
                merchant_key=key,
                currency=str(group["currency"].dropna().astype(str).iloc[0] or "").upper(),
                samples=group.reset_index(drop=True),
                cadence=cadence,
                confidence=1.0 if pref.confirmed else 0.5,
                source="confirmed" if pref.confirmed else "preference",
                preference=pref,
                user_decision=user_decision(
                    key,
                    preferences=preferences,
                    feedback_decisions=feedback_decisions,
                ),
                as_of=as_of,
            )
        )
    return rows


def overview_from_rows(rows: list[SubscriptionReviewRow], *, as_of: date) -> SubscriptionOverview:
    base = rows[0].base_currency if rows else "PLN"
    monthly_total = round(sum(row.estimated_monthly_cost for row in rows), 2)
    upcoming: list[SubscriptionUpcomingPayment] = []
    end = as_of + timedelta(days=UPCOMING_WINDOW_DAYS)
    for row in rows:
        if row.next_expected_date is None:
            continue
        if as_of <= row.next_expected_date <= end:
            upcoming.append(
                SubscriptionUpcomingPayment(
                    subscription_key=row.merchant_key,
                    display_name=row.display_name,
                    due_date=row.next_expected_date,
                    amount=row.median_amount,
                    currency=row.currency,
                    amount_base=row.estimated_monthly_cost
                    if row.cadence == "monthly"
                    else round(
                        row.estimated_monthly_cost
                        / max(monthly_ratio(row.cadence), 1e-9),
                        2,
                    ),
                    base_currency=row.base_currency,
                    status=row.status,
                )
            )
    upcoming.sort(key=lambda item: item.due_date)
    next_total = round(sum(item.amount_base for item in upcoming), 2)
    return SubscriptionOverview(
        monthly_total=monthly_total,
        yearly_total=round(monthly_total * 12, 2),
        next_30_days_count=len(upcoming),
        next_30_days_total=next_total,
        base_currency=base,
        upcoming=upcoming,
    )
