"""Shared subscription review service used by API and LLM tools."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.domain.enums import Category, CategorySource
from finance.domain.models import MlFeedbackEvent, SubscriptionPreference, Transaction
from finance.ml.feedback import (
    EVENT_SUBSCRIPTION_CONFIRMED,
    EVENT_SUBSCRIPTION_REJECTED,
    EVENT_SUBSCRIPTION_RESTORED,
    FeedbackEventInput,
    record_feedback_event,
)
from finance.ml.subscriptions.detector import (
    CADENCES,
    detect_subscriptions,
    normalize_subscription_merchant,
)
from finance.transactions.merchants import (
    load_merchant_alias_maps,
    merchant_display_label,
    merchant_identity,
    merchant_key,
)

SubscriptionFeedbackAction = Literal["confirm"]
SubscriptionPreferenceAction = Literal[
    "confirm",
    "reject",
    "restore",
    "update",
]
SubscriptionUserDecision = Literal["suggested", "confirmed", "rejected"]

PRICE_CHANGE_RELATIVE_THRESHOLD = 0.08
PRICE_CHANGE_ABSOLUTE_THRESHOLD = 1.0
REVIEW_CONFIDENCE_THRESHOLD = 0.65
UPCOMING_WINDOW_DAYS = 30
ANNUAL_RENEWAL_WINDOW_DAYS = 90


@dataclass(frozen=True)
class SubscriptionTransactionSample:
    id: int
    booking_date: date
    merchant: str
    title: str
    amount: float
    currency: str
    amount_base: float
    base_currency: str
    category: str | None
    category_source: str | None


@dataclass(frozen=True)
class SubscriptionReviewRow:
    merchant: str
    merchant_key: str
    currency: str
    base_currency: str
    cadence: str
    median_amount: float
    occurrences: int
    last_seen: date
    estimated_monthly_cost_original: float
    estimated_monthly_cost: float
    confidence: float
    status: str
    source: str
    next_expected_date: date | None
    previous_amount: float | None
    current_amount: float | None
    price_change_pct: float | None
    price_change_annual_impact: float | None
    evidence: dict[str, object]
    is_confirmed: bool
    user_decision: SubscriptionUserDecision
    display_name: str
    transactions: list[SubscriptionTransactionSample]


@dataclass(frozen=True)
class SubscriptionUpcomingPayment:
    subscription_key: str
    display_name: str
    due_date: date
    amount: float
    currency: str
    amount_base: float
    base_currency: str
    status: str


@dataclass(frozen=True)
class SubscriptionOverview:
    monthly_total: float
    yearly_total: float
    next_30_days_count: int
    next_30_days_total: float
    base_currency: str
    upcoming: list[SubscriptionUpcomingPayment]


def _subscription_key(merchant_norm: str, currency: str | None) -> str:
    currency = str(currency or "").lower()
    return f"{merchant_norm}|{currency}" if currency else merchant_norm


def _transaction_frame(session: Session) -> pd.DataFrame:
    rows = session.execute(select(Transaction)).scalars().all()
    alias_map, label_map = load_merchant_alias_maps(session)
    items = []
    for row in rows:
        identity = merchant_identity(
            row.merchant,
            row.title,
            alias_map=alias_map,
            label_map=label_map,
        )
        merchant_norm = identity.canonical_key or normalize_subscription_merchant(
            row.merchant,
            row.title,
        )
        merchant_display = identity.display_label or merchant_display_label(
            row.merchant,
            row.title,
        )
        items.append(
            {
                "booking_date": row.booking_date,
                "transaction_id": row.id,
                "amount": float(row.amount),
                "amount_base": float(row.amount_base if row.amount_base is not None else row.amount),
                "direction": row.direction,
                "merchant": row.merchant or "",
                "title": row.title or "",
                "merchant_norm": merchant_norm,
                "merchant_display": merchant_display,
                "currency": row.currency or "",
                "base_currency": row.base_currency or row.currency or "",
                "category": row.category,
                "category_source": row.category_source,
                "is_transfer": row.is_transfer,
                "transaction_type": row.transaction_type,
            }
        )
    return pd.DataFrame(
        items
    )


def _load_preferences(session: Session) -> dict[str, SubscriptionPreference]:
    prefs = session.execute(select(SubscriptionPreference)).scalars().all()
    return {pref.subscription_key: pref for pref in prefs}


def _subscription_feedback_decisions(session: Session) -> dict[str, str]:
    rows = session.execute(
        select(MlFeedbackEvent.entity_key, MlFeedbackEvent.event_type).where(
            MlFeedbackEvent.event_type.in_(
                [
                    EVENT_SUBSCRIPTION_CONFIRMED,
                    EVENT_SUBSCRIPTION_REJECTED,
                    EVENT_SUBSCRIPTION_RESTORED,
                ]
            ),
            MlFeedbackEvent.entity_type == "subscription_merchant",
            MlFeedbackEvent.entity_key.is_not(None),
        ).order_by(MlFeedbackEvent.created_at.asc(), MlFeedbackEvent.id.asc())
    ).all()
    return {str(key): str(event_type) for key, event_type in rows if key}


def _user_decision(
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


def _monthly_ratio(cadence: str) -> float:
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


def _infer_cadence(samples: pd.DataFrame, *, fallback: str = "unknown") -> str:
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


def _next_expected(last_seen: date, cadence: str) -> date | None:
    days = _cadence_days(cadence)
    if not days:
        return None
    return last_seen + timedelta(days=days)


def _status_for(
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
    if price_change_pct is not None:
        if price_change_pct > 0:
            return "price_increased"
    if not is_confirmed and confidence < REVIEW_CONFIDENCE_THRESHOLD:
        return "needs_review"
    if source == "category" and occurrences < 2:
        return "needs_review"
    if not is_confirmed:
        return "new"
    return "active"


def _price_change(samples: pd.DataFrame) -> tuple[float | None, float | None, float | None]:
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
    if (
        abs(pct) < PRICE_CHANGE_RELATIVE_THRESHOLD
        or abs(current - previous) < PRICE_CHANGE_ABSOLUTE_THRESHOLD
    ):
        pct = None
    return previous, current, round(pct * 100, 2) if pct is not None else None


def _sample_evidence(
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


def _transaction_samples(samples: pd.DataFrame) -> list[SubscriptionTransactionSample]:
    out: list[SubscriptionTransactionSample] = []
    for row in samples.sort_values("booking_date", ascending=False).head(12).itertuples():
        booking_date = row.booking_date.date() if hasattr(row.booking_date, "date") else row.booking_date
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


def _base_currency(samples: pd.DataFrame, fallback: str) -> str:
    if "base_currency" in samples.columns:
        currencies = [
            str(value)
            for value in samples["base_currency"].dropna().unique().tolist()
            if str(value)
        ]
        if currencies:
            return currencies[0]
    return fallback


def _row_from_samples(
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
    base_currency = _base_currency(samples, currency)
    base_amounts = [abs(float(value)) for value in samples["amount_base"].dropna().tolist()]
    original_amounts = [abs(float(value)) for value in samples["amount"].dropna().tolist()]
    median_base = float(pd.Series(base_amounts).median()) if base_amounts else 0.0
    median_original = float(pd.Series(original_amounts).median()) if original_amounts else 0.0
    ratio = _monthly_ratio(cadence)
    previous_amount, current_amount, price_change_pct = _price_change(samples)
    annual_impact = (
        round((current_amount - previous_amount) * ratio * 12, 2)
        if price_change_pct is not None and previous_amount is not None and current_amount is not None
        else None
    )
    next_expected_date = _next_expected(last_seen, cadence)
    is_confirmed = bool(preference and preference.confirmed) or source == "category"
    display_name = (
        (preference.display_name if preference else None)
        or merchant
        or merchant_key.split("|")[0]
    )
    status = _status_for(
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
        base_currency=base_currency,
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
        evidence=_sample_evidence(
            samples,
            source=source,
            cadence=cadence,
            confidence=confidence,
        ),
        is_confirmed=is_confirmed,
        user_decision=user_decision,
        display_name=display_name,
        transactions=_transaction_samples(samples),
    )


def _to_row(
    sub,
    *,
    preference: SubscriptionPreference | None,
    user_decision: SubscriptionUserDecision = "suggested",
    as_of: date,
) -> SubscriptionReviewRow:
    cadence = preference.cadence_override if preference and preference.cadence_override else sub.cadence
    return _row_from_samples(
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


def _category_subscription_rows(
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
        key = _subscription_key(str(merchant_norm), str(currency or ""))
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
        cadence = _infer_cadence(group)
        pref = preferences.get(key)
        if pref and pref.cadence_override:
            cadence = pref.cadence_override
        user_decision = _user_decision(
            key,
            preferences=preferences,
            feedback_decisions=feedback_decisions,
        )
        if user_decision == "suggested":
            user_decision = "confirmed"
        rows.append(
            _row_from_samples(
                merchant=display or str(merchant_norm),
                merchant_key=key,
                currency=str(currency or "").upper(),
                samples=group.reset_index(drop=True),
                cadence=cadence,
                confidence=1.0,
                source="category",
                preference=pref,
                user_decision=user_decision,
                as_of=as_of,
            )
        )
    return rows


def _preference_only_rows(
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
        cadence = pref.cadence_override or _infer_cadence(group)
        rows.append(
            _row_from_samples(
                merchant=pref.display_name or merchant_norm,
                merchant_key=key,
                currency=str(group["currency"].dropna().astype(str).iloc[0] or "").upper(),
                samples=group.reset_index(drop=True),
                cadence=cadence,
                confidence=1.0 if pref.confirmed else 0.5,
                source="confirmed" if pref.confirmed else "preference",
                preference=pref,
                user_decision=_user_decision(
                    key,
                    preferences=preferences,
                    feedback_decisions=feedback_decisions,
                ),
                as_of=as_of,
            )
        )
    return rows


def list_subscription_rows(
    session: Session,
    *,
    min_occurrences: int = 2,
    amount_tol: float = 0.10,
    day_tol: int = 5,
    min_confidence: float = 0.0,
    include_rejected: bool = False,
    as_of: date | None = None,
) -> list[SubscriptionReviewRow]:
    as_of = as_of or date.today()
    df = _transaction_frame(session)
    if df.empty:
        return []
    preferences = _load_preferences(session)
    feedback_decisions = _subscription_feedback_decisions(session)
    def is_rejected(key: str) -> bool:
        return (
            _user_decision(
                key,
                preferences=preferences,
                feedback_decisions=feedback_decisions,
            )
            == "rejected"
        )

    active_preferences = {
        key: pref
        for key, pref in preferences.items()
        if include_rejected or not is_rejected(key)
    }
    subs = detect_subscriptions(
        df,
        min_occurrences=min_occurrences,
        amount_tol=amount_tol,
        day_tol=day_tol,
    )
    rows: list[SubscriptionReviewRow] = []
    for sub in subs:
        pref = preferences.get(sub.merchant_key)
        rejected = is_rejected(sub.merchant_key)
        if rejected and not include_rejected:
            continue
        row = _to_row(
            sub,
            preference=pref,
            user_decision="rejected" if rejected else _user_decision(
                sub.merchant_key,
                preferences=preferences,
                feedback_decisions=feedback_decisions,
            ),
            as_of=as_of,
        )
        if (
            row.source == "detected"
            and not row.is_confirmed
            and row.user_decision != "rejected"
            and row.confidence < min_confidence
        ):
            continue
        rows.append(row)
    detected_keys = {row.merchant_key for row in rows}
    rows.extend(
        row
        for row in _category_subscription_rows(
            df,
            preferences=active_preferences,
            feedback_decisions=feedback_decisions,
            detected_keys=detected_keys,
            as_of=as_of,
        )
        if include_rejected or not is_rejected(row.merchant_key)
    )
    existing_keys = {row.merchant_key for row in rows}
    rows.extend(
        _preference_only_rows(
            df,
            preferences=active_preferences,
            feedback_decisions=feedback_decisions,
            existing_keys=existing_keys,
            as_of=as_of,
        )
    )
    rows.sort(key=lambda row: row.estimated_monthly_cost, reverse=True)
    return rows


def subscription_overview(
    session: Session,
    *,
    as_of: date | None = None,
) -> SubscriptionOverview:
    as_of = as_of or date.today()
    rows = [
        row
        for row in list_subscription_rows(session, min_confidence=0.0, as_of=as_of)
        if row.status not in {"probably_cancelled", "paused_or_missing"}
    ]
    base_currency = rows[0].base_currency if rows else "PLN"
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
                    else round(row.estimated_monthly_cost / max(_monthly_ratio(row.cadence), 1e-9), 2),
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
        base_currency=base_currency,
        upcoming=upcoming,
    )


def upsert_subscription_preference(
    session: Session,
    *,
    subscription_key: str,
    action: SubscriptionPreferenceAction = "update",
    display_name: str | None = None,
    cadence_override: str | None = None,
) -> SubscriptionPreference:
    pref = session.execute(
        select(SubscriptionPreference).where(
            SubscriptionPreference.subscription_key == subscription_key
        )
    ).scalar_one_or_none()
    if pref is None:
        pref = SubscriptionPreference(subscription_key=subscription_key)
        session.add(pref)
    if display_name is not None:
        pref.display_name = display_name.strip() or None
    if cadence_override is not None:
        pref.cadence_override = cadence_override or None
    if action == "confirm":
        pref.confirmed = True
    elif action == "reject":
        pref.confirmed = False
        record_feedback_event(
            session,
            FeedbackEventInput(
                event_type=EVENT_SUBSCRIPTION_REJECTED,
                entity_type="subscription_merchant",
                entity_key=subscription_key,
                source="subscription_management",
            ),
        )
    elif action == "restore":
        pref.confirmed = False
        record_feedback_event(
            session,
            FeedbackEventInput(
                event_type=EVENT_SUBSCRIPTION_RESTORED,
                entity_type="subscription_merchant",
                entity_key=subscription_key,
                source="subscription_management",
            ),
        )
    elif action == "update":
        pass
    session.commit()
    session.refresh(pref)
    return pref


def record_subscription_feedback(
    session: Session,
    *,
    merchant: str,
    action: SubscriptionFeedbackAction,
    subscription_key: str | None = None,
) -> MlFeedbackEvent:
    normalized = normalize_subscription_merchant(merchant)
    event = record_feedback_event(
        session,
        FeedbackEventInput(
            event_type=EVENT_SUBSCRIPTION_CONFIRMED,
            entity_type="subscription_merchant",
            entity_key=subscription_key or normalized,
            source="subscription_detector",
        ),
    )
    if action == "confirm":
        keys = {subscription_key} if subscription_key else set()
        if not keys:
            alias_map, label_map = load_merchant_alias_maps(session)
            identity = merchant_identity(merchant, alias_map=alias_map, label_map=label_map)
            candidate_keys = {
                value
                for value in {
                    normalized,
                    identity.canonical_key,
                    merchant_key(merchant),
                }
                if value
            }
            df = _transaction_frame(session)
            if not df.empty and candidate_keys:
                display_keys = df["merchant_display"].fillna("").astype(str).map(
                    normalize_subscription_merchant
                )
                matches = df[
                    df["merchant_norm"].isin(candidate_keys)
                    | display_keys.isin(candidate_keys)
                ]
                for row in matches.itertuples():
                    keys.add(_subscription_key(str(row.merchant_norm), str(row.currency or "")))
            if not keys:
                keys.add(normalized)
        for key in keys:
            upsert_subscription_preference(
                session,
                subscription_key=key,
                action="confirm",
                display_name=merchant,
            )
    session.commit()
    session.refresh(event)
    return event
