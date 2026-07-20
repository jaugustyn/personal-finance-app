"""Classifier prediction using a DB-registered immutable artifact."""
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
from finance.config import get_settings
from finance.currencies import amount_base_value
from finance.domain.category_mapping import map_source_category
from finance.domain.enums import (
    CATEGORY_VALUES,
    CategoryConfirmationMethod,
    CategorySource,
    TransactionType,
)
from finance.domain.models import MlModelVersion, Transaction
from finance.llm import client as llm_client
from finance.ml.classification.artifacts import artifact_sha256, require_runtime_artifact
from finance.ml.classification.confidence import predict_with_probabilities
from finance.ml.classification.policy import (
    DEFAULT_POLICY,
    ClassificationDecision,
    ClassificationPolicy,
    decide_classification,
    policy_from_report,
    recommended_action_for_decision,
)
from finance.ml.feedback import EVENT_AUTO_RULE_CATEGORY, record_transaction_feedback
from finance.profile.service import RULE_MODE_AUTO, effect_for_transaction
from finance.transactions.category_provenance import (
    bank_mapping_ref,
    model_version_ref,
    personal_rule_ref,
    system_rule_ref,
)
from finance.transactions.rules import rule_category_for_type
from finance.transactions.type_decision import effective_transaction_type

SYSTEM_CATEGORIES = CATEGORY_VALUES


class ClassifierNotAvailable(RuntimeError):
    """Raised when no persisted classifier can be loaded."""


@dataclass(frozen=True)
class PredictionResult:
    category: str
    confidence: float | None
    model_confidence: float | None
    source: str
    model_category: str
    threshold: float
    fallback_used: bool
    top_predictions: list[dict[str, float | str]]
    recommended_action: str
    classification_decision: ClassificationDecision


def _unwrap_artifact(artifact: Any):
    pipe = artifact.get("pipeline") if isinstance(artifact, dict) else None
    if pipe is None or not hasattr(pipe, "predict_proba"):
        raise ClassifierNotAvailable(
            "model_retrain_required: registered artifact does not contain a calibrated pipeline."
        )
    return pipe


@lru_cache(maxsize=8)
def load_registered_artifact(
    artifact_path: str,
    expected_sha256: str,
    expected_model_id: str,
) -> dict[str, Any]:
    """Load and validate the exact immutable artifact selected by the registry."""
    path = Path(artifact_path)
    if not path.exists() or artifact_sha256(path) != expected_sha256:
        raise ClassifierNotAvailable(
            "model_retrain_required: active artifact is missing or its checksum changed."
        )
    try:
        artifact = joblib.load(path)
        require_runtime_artifact(artifact)
    except ClassifierNotAvailable:
        raise
    except Exception as exc:
        raise ClassifierNotAvailable(
            "model_retrain_required: active artifact is damaged or incompatible."
        ) from exc
    if not isinstance(artifact, dict) or artifact.get("model_version_id") != expected_model_id:
        raise ClassifierNotAvailable(
            "model_retrain_required: active artifact identity does not match the registry."
        )
    if artifact.get("task", "category") != "category":
        raise ClassifierNotAvailable("model_retrain_required: artifact is not a category model.")
    _unwrap_artifact(artifact)
    return artifact


def require_registered_active_artifact(
    session: Session,
) -> dict[str, Any]:
    """Load the immutable artifact selected by the active DB registry row."""
    active = session.execute(
        select(MlModelVersion)
        .where(MlModelVersion.status == "active")
        .order_by(MlModelVersion.activated_at.desc())
    ).scalars().first()
    if active is None:
        raise ClassifierNotAvailable(
            "model_retrain_required: no model is registered as active in this database."
        )
    return load_registered_artifact(
        str(active.artifact_path),
        active.artifact_sha256,
        active.id,
    )


def active_classification_policy(
    *,
    session: Session | None = None,
    artifact: dict[str, Any] | None = None,
    fallback: ClassificationPolicy = DEFAULT_POLICY,
) -> ClassificationPolicy:
    try:
        selected = artifact
        if selected is None and session is not None:
            selected = require_registered_active_artifact(session)
        if selected is None:
            return fallback
        embedded = selected.get("confidence_policy")
    except ClassifierNotAvailable:
        return fallback
    return policy_from_report(
        embedded if isinstance(embedded, dict) else None,
        fallback=fallback,
    )


def _row_to_features(
    merchant: str,
    title: str,
    amount: Decimal,
    booking_date: date,
    *,
    source: str = "unknown",
    transaction_type: str = TransactionType.EXPENSE.value,
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
                "transaction_type": transaction_type or TransactionType.EXPENSE.value,
            }
        ]
    )
    return base


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
    use_llm_fallback: bool = False,
    source: str = "unknown",
    transaction_type: str = TransactionType.EXPENSE.value,
    direction: str | None = None,
    is_transfer: bool = False,
    policy: ClassificationPolicy | None = None,
    artifact: dict[str, Any] | None = None,
) -> PredictionResult:
    if artifact is None:
        raise ClassifierNotAvailable(
            "model_retrain_required: prediction requires the active registered artifact."
        )
    if policy is None:
        embedded = artifact.get("confidence_policy")
        active_policy = policy_from_report(
            embedded if isinstance(embedded, dict) else None,
            fallback=DEFAULT_POLICY,
        )
    else:
        active_policy = policy
    direction_value = direction or ("credit" if amount > 0 else "debit")
    pipe = _unwrap_artifact(artifact)
    X = _row_to_features(  # noqa: N806
        merchant,
        title,
        amount,
        booking_date,
        source=source,
        transaction_type=transaction_type,
    )
    prediction = predict_with_probabilities(pipe, X, k=3)
    if prediction is None:
        raise ClassifierNotAvailable(
            "model_retrain_required: active artifact cannot return calibrated probabilities."
        )
    model_category, confidence, top_predictions = prediction
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
        and get_settings().llm_fallback_enabled
        and confidence is not None
        and confidence < decision.threshold_used
    ):
        fallback_category = _llm_fallback_category(merchant, title, amount, booking_date)
        if fallback_category is not None:
            fallback_decision = decide_classification(
                category=fallback_category,
                confidence=None,
                direction=direction_value,
                is_transfer=is_transfer,
                transaction_type=transaction_type,
                policy=active_policy,
            )
            return PredictionResult(
                category=fallback_category,
                confidence=None,
                model_confidence=confidence,
                source="llm",
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
        model_confidence=confidence,
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
    registered_artifact: dict[str, Any] | None = None
    for r in rows:
        personal = effect_for_transaction(session, merchant=r.merchant, title=r.title)
        effective_type = effective_transaction_type(r)
        category_candidate = is_expense_category_candidate(
            r.direction,
            effective_type == TransactionType.OWN_TRANSFER.value,
            effective_type,
        )
        if personal and personal.category and category_candidate:
            ref = personal_rule_ref(personal.rule.id)
            if personal.mode == RULE_MODE_AUTO:
                session.execute(
                    update(Transaction)
                    .where(Transaction.id == r.id)
                    .values(
                        category=personal.category,
                        category_source=CategorySource.RULE.value,
                        category_confirmation_method=(
                            CategoryConfirmationMethod.PERSONAL_RULE_AUTO.value
                        ),
                        category_confirmed_at=None,
                        category_origin_ref=ref,
                        category_predicted=None,
                        category_confidence=None,
                        category_predicted_source=None,
                        category_predicted_ref=None,
                        category_suggestion_rejected=False,
                    )
                )
                record_transaction_feedback(
                    session,
                    r,
                    event_type=EVENT_AUTO_RULE_CATEGORY,
                    final_category=personal.category,
                    previous_category=None,
                    confirmation_method=(
                        CategoryConfirmationMethod.PERSONAL_RULE_AUTO.value
                    ),
                    origin_ref=ref,
                    source=CategorySource.RULE.value,
                )
            else:
                session.execute(
                    update(Transaction)
                    .where(Transaction.id == r.id)
                    .values(
                        category_predicted=personal.category,
                        category_confidence=personal.confidence,
                        category_predicted_source=CategorySource.RULE.value,
                        category_predicted_ref=ref,
                    )
                )
            updated += 1
            continue

        source_category = map_source_category(r.raw_category)
        if source_category is not None and category_candidate:
            session.execute(
                update(Transaction)
                .where(Transaction.id == r.id)
                .values(
                    category_predicted=source_category.value,
                    category_confidence=None,
                    category_predicted_source=CategorySource.BANK.value,
                    category_predicted_ref=bank_mapping_ref(r.source),
                    category_suggestion_rejected=False,
                )
            )
            updated += 1
            continue

        system_category = rule_category_for_type(TransactionType(effective_type))
        if system_category is not None and category_candidate:
            session.execute(
                update(Transaction)
                .where(Transaction.id == r.id)
                .values(
                    category_predicted=system_category.value,
                    category_confidence=None,
                    category_predicted_source=CategorySource.RULE.value,
                    category_predicted_ref=system_rule_ref(effective_type),
                    category_suggestion_rejected=False,
                )
            )
            updated += 1
            continue
        if not category_candidate:
            r.category_predicted = None
            r.category_confidence = None
            r.category_predicted_source = None
            r.category_predicted_ref = None
            continue
        base_amount = amount_base_value(r)
        if base_amount is None:
            r.category_predicted = None
            r.category_confidence = None
            r.category_predicted_source = None
            r.category_predicted_ref = None
            continue
        if registered_artifact is None:
            registered_artifact = require_registered_active_artifact(session)
        result = predict_transaction(
            r.merchant,
            r.title,
            base_amount,
            r.booking_date,
            use_llm_fallback=False,
            source=str(r.source or "unknown"),
            transaction_type=effective_type,
            direction=str(r.direction or "debit"),
            is_transfer=bool(r.is_transfer),
            policy=policy,
            artifact=registered_artifact,
        )
        version_id = registered_artifact.get("model_version_id")
        model_ref = model_version_ref(str(version_id) if version_id else None)
        session.execute(
            update(Transaction)
            .where(Transaction.id == r.id)
            .values(
                category_predicted=result.category,
                category_confidence=result.confidence,
                category_predicted_source=CategorySource.MODEL.value,
                category_predicted_ref=model_ref,
            )
        )
        updated += 1
    session.commit()
    return updated
