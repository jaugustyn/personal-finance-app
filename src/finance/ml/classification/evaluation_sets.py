"""Versioned private holdout creation and invalidation."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from uuid import uuid4

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.domain.enums import Category
from finance.domain.models import MlEvaluationMember, MlEvaluationSet
from finance.ml.classification.dataset import load_training_set
from finance.transactions.merchants import merchant_canonical_key

ONTOLOGY_VERSION = "category_v1"
THESIS_MIN_TOTAL = 800
THESIS_MIN_PER_CATEGORY = 50
THESIS_MIN_MONTHS = 12
THESIS_MIN_DATE_SPAN_DAYS = 365
HOLDOUT_FRACTION = 0.20
HOLDOUT_MIN_PER_CATEGORY = 5
HOLDOUT_RANDOM_STATE = 42


class EvaluationSetError(ValueError):
    """Raised when a private evaluation set cannot be frozen safely."""


def dataset_fingerprint(df: pd.DataFrame) -> str:
    """Hash label identity without serialising private transaction text."""
    if df.empty:
        return hashlib.sha256(b"").hexdigest()
    rows = []
    for row in df.sort_values("transaction_id").itertuples(index=False):
        confirmed = getattr(row, "category_confirmed_at", None)
        isoformat = getattr(confirmed, "isoformat", None)
        confirmed_value = isoformat() if callable(isoformat) else str(confirmed)
        rows.append(
            (
                int(row.transaction_id),
                str(row.category),
                confirmed_value,
            )
        )
    payload = json.dumps(rows, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def current_evaluation_set(session: Session) -> MlEvaluationSet | None:
    return session.execute(
        select(MlEvaluationSet)
        .where(MlEvaluationSet.status == "active")
        .order_by(MlEvaluationSet.created_at.desc())
    ).scalars().first()


def evaluation_members(
    session: Session,
    evaluation_set_id: str,
) -> list[MlEvaluationMember]:
    return list(
        session.execute(
            select(MlEvaluationMember).where(
                MlEvaluationMember.evaluation_set_id == evaluation_set_id
            )
        ).scalars()
    )


def split_transaction_ids(session: Session, evaluation_set_id: str) -> dict[str, set[int]]:
    out: dict[str, set[int]] = {"time": set(), "merchant": set()}
    for member in evaluation_members(session, evaluation_set_id):
        if member.transaction_id is not None:
            out.setdefault(member.split, set()).add(int(member.transaction_id))
    return out


def excluded_training_ids(session: Session) -> set[int]:
    current = current_evaluation_set(session)
    if current is None:
        return set()
    split_ids = split_transaction_ids(session, current.id)
    return set().union(*split_ids.values())


def thesis_data_readiness(df: pd.DataFrame) -> dict[str, object]:
    categories = [item.value for item in Category]
    counts = df["category"].astype(str).value_counts().to_dict() if not df.empty else {}
    category_counts = {category: int(counts.get(category, 0)) for category in categories}
    dates = (
        pd.to_datetime(df["booking_date"], errors="coerce").dropna()
        if "booking_date" in df.columns
        else pd.Series([], dtype="datetime64[ns]")
    )
    months = int(dates.dt.to_period("M").nunique()) if not dates.empty else 0
    date_span_days = int((dates.max() - dates.min()).days) if len(dates) > 1 else 0
    failures: list[str] = []
    if len(df) < THESIS_MIN_TOTAL:
        failures.append("total_below_800")
    if any(count < THESIS_MIN_PER_CATEGORY for count in category_counts.values()):
        failures.append("category_below_50")
    if months < THESIS_MIN_MONTHS:
        failures.append("fewer_than_12_calendar_months")
    if date_span_days < THESIS_MIN_DATE_SPAN_DAYS:
        failures.append("date_span_below_365_days")
    return {
        "ready": not failures,
        "total": int(len(df)),
        "category_counts": category_counts,
        "calendar_months": months,
        "date_span_days": date_span_days,
        "failures": failures,
    }


def _support(frame: pd.DataFrame) -> dict[str, int]:
    counts = frame["category"].astype(str).value_counts().to_dict()
    return {item.value: int(counts.get(item.value, 0)) for item in Category}


def _has_holdout_support(frame: pd.DataFrame) -> bool:
    return all(count >= HOLDOUT_MIN_PER_CATEGORY for count in _support(frame).values())


def _time_holdout(df: pd.DataFrame) -> pd.DataFrame:
    ordered = df.sort_values(["booking_date", "transaction_id"], kind="stable")
    size = max(1, math.ceil(len(ordered) * HOLDOUT_FRACTION))
    holdout = ordered.tail(size).copy()
    if not _has_holdout_support(holdout):
        raise EvaluationSetError(
            "Time holdout does not contain at least 5 examples of every category."
        )
    return holdout


def _merchant_holdout(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["merchant_group"] = [
        merchant_canonical_key(str(merchant or ""), str(title or ""))
        or f"missing:{transaction_id}"
        for merchant, title, transaction_id in zip(
            work["merchant"], work["title"], work["transaction_id"], strict=False
        )
    ]
    splitter = StratifiedGroupKFold(
        n_splits=5,
        shuffle=True,
        random_state=HOLDOUT_RANDOM_STATE,
    )
    candidates: list[tuple[float, int, np.ndarray]] = []
    placeholder = np.zeros(len(work))
    for fold_index, (_, test_idx) in enumerate(
        splitter.split(placeholder, work["category"].astype(str), work["merchant_group"])
    ):
        candidate = work.iloc[test_idx]
        if _has_holdout_support(candidate):
            distance = abs((len(candidate) / len(work)) - HOLDOUT_FRACTION)
            candidates.append((distance, fold_index, test_idx))
    if not candidates:
        raise EvaluationSetError(
            "Merchant holdout does not contain at least 5 examples of every category."
        )
    _, _, selected = min(candidates, key=lambda item: (item[0], item[1]))
    return work.iloc[selected].copy()


def freeze_evaluation_set(session: Session) -> MlEvaluationSet:
    if current_evaluation_set(session) is not None:
        raise EvaluationSetError("An active evaluation set already exists.")
    df = load_training_set(session)
    readiness = thesis_data_readiness(df)
    if not readiness["ready"]:
        raw_failures = readiness.get("failures", [])
        failures = (
            [str(item) for item in raw_failures]
            if isinstance(raw_failures, list)
            else [str(raw_failures)]
        )
        raise EvaluationSetError(
            "Dataset is not thesis-data-ready: " + ", ".join(failures)
        )
    time_holdout = _time_holdout(df)
    merchant_holdout = _merchant_holdout(df)
    evaluation_set = MlEvaluationSet(
        id=str(uuid4()),
        status="active",
        ontology_version=ONTOLOGY_VERSION,
        dataset_fingerprint=dataset_fingerprint(df),
        config={
            "fraction": HOLDOUT_FRACTION,
            "min_per_category": HOLDOUT_MIN_PER_CATEGORY,
            "random_state": HOLDOUT_RANDOM_STATE,
            "time_support": _support(time_holdout),
            "merchant_support": _support(merchant_holdout),
        },
    )
    session.add(evaluation_set)
    session.flush()
    for split, frame in (("time", time_holdout), ("merchant", merchant_holdout)):
        for row in frame.itertuples(index=False):
            merchant_key = merchant_canonical_key(
                str(row.merchant or ""), str(row.title or "")
            )
            session.add(
                MlEvaluationMember(
                    evaluation_set_id=evaluation_set.id,
                    transaction_id=int(row.transaction_id),
                    split=split,
                    category=str(row.category),
                    booking_date=row.booking_date,
                    merchant_hash=hashlib.sha256(merchant_key.encode()).hexdigest(),
                )
            )
    session.commit()
    session.refresh(evaluation_set)
    return evaluation_set


def invalidate_for_label_change(
    session: Session,
    transaction_id: int,
    *,
    reason: str = "frozen_label_changed",
) -> bool:
    evaluation_set = current_evaluation_set(session)
    if evaluation_set is None:
        return False
    member_exists = session.execute(
        select(MlEvaluationMember.id)
        .where(MlEvaluationMember.evaluation_set_id == evaluation_set.id)
        .where(MlEvaluationMember.transaction_id == transaction_id)
        .limit(1)
    ).scalar_one_or_none()
    if member_exists is None:
        return False
    evaluation_set.status = "invalidated"
    evaluation_set.invalidated_at = datetime.now(UTC)
    evaluation_set.invalidation_reason = reason
    return True


def evaluation_set_summary(session: Session) -> dict[str, object]:
    evaluation_set = current_evaluation_set(session)
    if evaluation_set is None:
        readiness = thesis_data_readiness(load_training_set(session))
        return {"active": False, "data_readiness": readiness}
    ids = split_transaction_ids(session, evaluation_set.id)
    return {
        "active": True,
        "id": evaluation_set.id,
        "status": evaluation_set.status,
        "ontology_version": evaluation_set.ontology_version,
        "dataset_fingerprint": evaluation_set.dataset_fingerprint,
        "created_at": evaluation_set.created_at.isoformat(),
        "config": evaluation_set.config,
        "time_count": len(ids["time"]),
        "merchant_count": len(ids["merchant"]),
        "excluded_training_count": len(ids["time"] | ids["merchant"]),
    }
