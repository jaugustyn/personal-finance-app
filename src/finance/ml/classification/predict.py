"""Lazy-loaded classifier from data/models/classifier_latest.joblib."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from finance.domain.enums import Category, CategorySource, TransactionType
from finance.domain.models import Transaction
from finance.llm import client as llm_client
from finance.ml.classification.confidence import max_prediction_confidence
from finance.ml.classification.pipeline import add_feature_v2_columns
from finance.profile.service import RULE_MODE_AUTO, effect_for_transaction
from finance.transactions.rules import detect_transaction_type, is_category_suggestion_candidate

LATEST_MODEL_PATH = Path("data/models/classifier_latest.joblib")
DEFAULT_THRESHOLD = 0.55
SYSTEM_CATEGORIES = {category.value for category in Category}


class ClassifierNotAvailable(RuntimeError):
    """Raised when no persisted classifier can be loaded."""


@dataclass(frozen=True)
class PredictionResult:
    category: str
    confidence: float | None
    source: str
    model_category: str
    threshold: float
    fallback_used: bool


def _unwrap_artifact(artifact: Any):
    """Support both old Pipeline artifacts and new metadata dict artifacts."""
    pipe = artifact.get("pipeline") if isinstance(artifact, dict) else artifact
    if pipe is None or not hasattr(pipe, "predict"):
        raise ClassifierNotAvailable(
            f"Invalid classifier artifact at {LATEST_MODEL_PATH}; expected sklearn Pipeline."
        )
    return pipe


@lru_cache(maxsize=1)
def get_classifier():
    if not LATEST_MODEL_PATH.exists():
        raise ClassifierNotAvailable(
            f"No model at {LATEST_MODEL_PATH}. "
            "Run `python -m finance.ml.classification.train ... --persist linear_svc`."
        )
    return _unwrap_artifact(joblib.load(LATEST_MODEL_PATH))


def _row_to_features(
    merchant: str,
    title: str,
    amount: Decimal,
    booking_date: date,
    *,
    source: str = "unknown",
    transaction_type: str = TransactionType.PURCHASE.value,
) -> pd.DataFrame:
    base = pd.DataFrame(
        [
            {
                "text": f"{merchant} {title}".strip(),
                "merchant": merchant,
                "title": title,
                "abs_amount": float(abs(amount)),
                "day_of_week": booking_date.weekday(),
                "booking_date": booking_date,
                "source": source or "unknown",
                "transaction_type": transaction_type or TransactionType.PURCHASE.value,
            }
        ]
    )
    return add_feature_v2_columns(base)


def predict_one(merchant: str, title: str, amount: Decimal, booking_date: date) -> str:
    return predict_transaction(merchant, title, amount, booking_date).category


def _extract_category_from_llm(content: str | None) -> str | None:
    if not content:
        return None
    clean = content.strip().lower().strip("`'\" .")
    if clean in SYSTEM_CATEGORIES:
        return clean
    tokens = re.findall(r"[a-z_]+", clean)
    matches = {token for token in tokens if token in SYSTEM_CATEGORIES}
    return next(iter(matches)) if len(matches) == 1 else None


def _llm_fallback_category(
    merchant: str,
    title: str,
    amount: Decimal,
    booking_date: date,
) -> str | None:
    if not llm_client.is_available():
        return None
    prompt = (
        "Sklasyfikuj transakcję do dokładnie jednej kategorii: "
        f"{', '.join(sorted(SYSTEM_CATEGORIES))}. "
        "Zwróć wyłącznie identyfikator kategorii, bez komentarza.\n"
        f"merchant={merchant!r}\n"
        f"title={title!r}\n"
        f"amount={amount}\n"
        f"booking_date={booking_date.isoformat()}"
    )
    try:
        msg = llm_client.chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Jesteś klasyfikatorem transakcji. "
                        "Nie zgaduj poza podanymi kategoriami."
                    ),
                },
                {"role": "user", "content": prompt},
            ]
        )
    except llm_client.OllamaUnavailable:
        return None
    return _extract_category_from_llm(msg.get("content") if isinstance(msg, dict) else None)


def predict_transaction(
    merchant: str,
    title: str,
    amount: Decimal,
    booking_date: date,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    use_llm_fallback: bool = False,
    source: str = "unknown",
    transaction_type: str = TransactionType.PURCHASE.value,
) -> PredictionResult:
    pipe = get_classifier()
    X = _row_to_features(  # noqa: N806
        merchant,
        title,
        amount,
        booking_date,
        source=source,
        transaction_type=transaction_type,
    )
    model_category = str(pipe.predict(X)[0])
    confidence = max_prediction_confidence(pipe, X)

    if (
        use_llm_fallback
        and confidence is not None
        and confidence < threshold
    ):
        fallback_category = _llm_fallback_category(merchant, title, amount, booking_date)
        if fallback_category is not None:
            return PredictionResult(
                category=fallback_category,
                confidence=confidence,
                source="llm_fallback",
                model_category=model_category,
                threshold=threshold,
                fallback_used=True,
            )

    return PredictionResult(
        category=model_category,
        confidence=confidence,
        source="model",
        model_category=model_category,
        threshold=threshold,
        fallback_used=False,
    )


def reclassify_unlabelled(
    session: Session,
    *,
    ids: list[int] | None = None,
    import_id: int | None = None,
) -> int:
    """Run the model on rows without `category` and store predictions in
    `category_predicted`. Returns number of rows updated."""
    stmt = select(Transaction).where(Transaction.category.is_(None))
    stmt = stmt.where(Transaction.category_suggestion_rejected.is_(False))
    if ids:
        stmt = stmt.where(Transaction.id.in_(ids))
    if import_id is not None:
        stmt = stmt.where(Transaction.import_id == import_id)
    rows = session.execute(stmt).scalars().all()
    if not rows:
        return 0
    updated = 0
    for r in rows:
        personal = effect_for_transaction(session, merchant=r.merchant, title=r.title)
        tx_type = detect_transaction_type(
            r.merchant,
            r.title,
            r.direction,
            raw_category=r.raw_category,
        )
        if personal and personal.transaction_type:
            tx_type = TransactionType(personal.transaction_type)
        if (
            r.transaction_type is None
            or str(r.transaction_type) == TransactionType.PURCHASE.value
        ):
            r.transaction_type = tx_type
        if personal and personal.is_transfer is not None:
            r.is_transfer = personal.is_transfer
        elif tx_type == TransactionType.OWN_TRANSFER:
            r.is_transfer = True
        if personal and personal.category:
            if personal.mode == RULE_MODE_AUTO:
                session.execute(
                    update(Transaction)
                    .where(Transaction.id == r.id)
                    .values(
                        category=personal.category,
                        category_source=CategorySource.RULE.value,
                        category_predicted=None,
                        category_confidence=None,
                        category_predicted_source=None,
                        transaction_type=str(r.transaction_type),
                        is_transfer=bool(r.is_transfer),
                        category_suggestion_rejected=False,
                    )
                )
            else:
                session.execute(
                    update(Transaction)
                    .where(Transaction.id == r.id)
                    .values(
                        category_predicted=personal.category,
                        category_confidence=personal.confidence,
                        category_predicted_source=CategorySource.RULE.value,
                        transaction_type=str(r.transaction_type),
                        is_transfer=bool(r.is_transfer),
                    )
                )
            updated += 1
            continue
        if not is_category_suggestion_candidate(r.transaction_type):
            r.category_predicted = None
            r.category_confidence = None
            r.category_predicted_source = None
            continue
        result = predict_transaction(
            r.merchant,
            r.title,
            r.amount,
            r.booking_date,
            use_llm_fallback=False,
            source=str(r.source or "unknown"),
            transaction_type=str(r.transaction_type or TransactionType.PURCHASE.value),
        )
        session.execute(
            update(Transaction)
            .where(Transaction.id == r.id)
            .values(
                category_predicted=result.category,
                category_confidence=result.confidence,
                category_predicted_source=CategorySource.MODEL.value,
                transaction_type=str(r.transaction_type),
            )
        )
        updated += 1
    session.commit()
    return updated
