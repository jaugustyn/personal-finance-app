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

from finance.analytics.filters import is_expense_category_candidate
from finance.domain.category_mapping import map_source_category
from finance.domain.enums import Category, CategorySource, TransactionType
from finance.domain.models import Transaction
from finance.llm import client as llm_client
from finance.ml.classification.confidence import (
    max_prediction_confidence,
    top_prediction_confidences,
)
from finance.ml.classification.pipeline import add_feature_v2_columns
from finance.ml.classification.policy import (
    DEFAULT_POLICY,
    ClassificationDecision,
    ClassificationPolicy,
    decide_classification,
    recommended_action_for_decision,
)
from finance.profile.service import RULE_MODE_AUTO, effect_for_transaction
from finance.transactions.rules import explain_transaction_type

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
    top_predictions: list[dict[str, float | str]]
    recommended_action: str
    classification_decision: ClassificationDecision


def _unwrap_artifact(artifact: Any):
    pipe = artifact.get("pipeline") if isinstance(artifact, dict) else None
    if pipe is None or not hasattr(pipe, "predict"):
        raise ClassifierNotAvailable(
            f"Invalid classifier artifact at {LATEST_MODEL_PATH}; expected metadata dict."
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
    direction: str | None = None,
    is_transfer: bool = False,
    policy: ClassificationPolicy | None = None,
) -> PredictionResult:
    active_policy = policy or ClassificationPolicy(default_threshold=threshold)
    direction_value = direction or ("credit" if amount > 0 else "debit")
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
    top_predictions = top_prediction_confidences(pipe, X, k=3)
    decision = decide_classification(
        category=model_category,
        confidence=confidence,
        direction=direction_value,
        is_transfer=is_transfer,
        transaction_type=transaction_type,
        policy=active_policy,
    )
    recommended_action = recommended_action_for_decision(decision)

    if (
        use_llm_fallback
        and confidence is not None
        and confidence < decision.threshold_used
    ):
        fallback_category = _llm_fallback_category(merchant, title, amount, booking_date)
        if fallback_category is not None:
            fallback_decision = decide_classification(
                category=fallback_category,
                confidence=confidence,
                direction=direction_value,
                is_transfer=is_transfer,
                transaction_type=transaction_type,
                policy=active_policy,
            )
            return PredictionResult(
                category=fallback_category,
                confidence=confidence,
                source="llm_fallback",
                model_category=model_category,
                threshold=fallback_decision.threshold_used,
                fallback_used=True,
                top_predictions=top_predictions,
                recommended_action=recommended_action_for_decision(fallback_decision),
                classification_decision=fallback_decision,
            )

    return PredictionResult(
        category=model_category,
        confidence=confidence,
        source="model",
        model_category=model_category,
        threshold=decision.threshold_used,
        fallback_used=False,
        top_predictions=top_predictions,
        recommended_action=recommended_action,
        classification_decision=decision,
    )


def reclassify_unlabelled(
    session: Session,
    *,
    ids: list[int] | None = None,
    import_id: int | None = None,
    policy: ClassificationPolicy = DEFAULT_POLICY,
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
        tx_type_decision = explain_transaction_type(
            r.merchant,
            r.title,
            r.direction,
            raw_category=r.raw_category,
        )
        tx_type = TransactionType(tx_type_decision.result or TransactionType.PURCHASE.value)
        if personal and personal.transaction_type:
            tx_type = TransactionType(personal.transaction_type)
        current_type = str(r.transaction_type or "")
        if (
            r.transaction_type is None
            or current_type in {TransactionType.PURCHASE.value, TransactionType.OTHER.value}
            or (str(r.direction) == "credit" and current_type != TransactionType.SALARY.value)
        ):
            r.transaction_type = tx_type
        if personal and personal.is_transfer is not None:
            r.is_transfer = personal.is_transfer
        elif tx_type == TransactionType.OWN_TRANSFER:
            r.is_transfer = True

        category_candidate = is_expense_category_candidate(
            r.direction,
            r.is_transfer,
            r.transaction_type,
        )
        source_category = map_source_category(r.raw_category)
        if source_category is not None and category_candidate:
            session.execute(
                update(Transaction)
                .where(Transaction.id == r.id)
                .values(
                    category=source_category.value,
                    category_source=CategorySource.BANK.value,
                    category_predicted=None,
                    category_confidence=None,
                    category_predicted_source=None,
                    transaction_type=str(r.transaction_type),
                    is_transfer=bool(r.is_transfer),
                    category_suggestion_rejected=False,
                )
            )
            updated += 1
            continue

        if personal and personal.category and category_candidate:
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
        if not category_candidate:
            r.category_predicted = None
            r.category_confidence = None
            r.category_predicted_source = None
            continue
        result = predict_transaction(
            r.merchant,
            r.title,
            r.amount_base if r.amount_base is not None else r.amount,
            r.booking_date,
            use_llm_fallback=False,
            source=str(r.source or "unknown"),
            transaction_type=str(r.transaction_type or TransactionType.PURCHASE.value),
            direction=str(r.direction or "debit"),
            is_transfer=bool(r.is_transfer),
            policy=policy,
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
