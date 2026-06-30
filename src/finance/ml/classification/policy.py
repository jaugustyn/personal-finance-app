"""Deterministic trust policy for category classification suggestions."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal

from finance.analytics.filters import is_expense_category_candidate
from finance.ml.classification.constants import (
    DEFAULT_ACCEPT_THRESHOLD,
    DEFAULT_REVIEW_FLOOR,
    OTHER_CATEGORY,
)

ClassificationDecisionAction = Literal["accept", "review", "manual", "not_applicable"]


@dataclass(frozen=True)
class ClassificationDecision:
    action: ClassificationDecisionAction
    reason_code: str
    threshold_used: float
    review_floor: float
    category: str | None
    confidence: float | None
    category_candidate: bool


@dataclass(frozen=True)
class ClassificationPolicy:
    default_threshold: float = DEFAULT_ACCEPT_THRESHOLD
    review_floor: float = DEFAULT_REVIEW_FLOOR
    per_category_thresholds: dict[str, float] | None = None
    allow_other_accept: bool = False

    def threshold_for(self, category: str | None) -> float:
        if not category:
            return self.default_threshold
        if self.per_category_thresholds and category in self.per_category_thresholds:
            return self.per_category_thresholds[category]
        return self.default_threshold


DEFAULT_POLICY = ClassificationPolicy()


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if 0.0 <= out <= 1.0 else None


def _policy_payload(report_or_policy: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(report_or_policy, dict):
        return {}
    payload = report_or_policy.get("confidence_policy")
    if isinstance(payload, dict):
        return payload
    return report_or_policy


def policy_from_report(
    report_or_policy: dict[str, Any] | None,
    *,
    fallback: ClassificationPolicy = DEFAULT_POLICY,
) -> ClassificationPolicy:
    """Build policy from a classification report or its confidence_policy block."""
    payload = _policy_payload(report_or_policy)
    default_threshold = _as_float(payload.get("default_threshold"))
    per_category: dict[str, float] = {}
    raw_per_category = payload.get("per_category")
    if isinstance(raw_per_category, dict):
        for category, info in raw_per_category.items():
            if not isinstance(info, dict):
                continue
            threshold = _as_float(info.get("threshold"))
            if threshold is not None:
                per_category[str(category)] = threshold

    return replace(
        fallback,
        default_threshold=(
            default_threshold
            if default_threshold is not None
            else fallback.default_threshold
        ),
        per_category_thresholds=per_category or fallback.per_category_thresholds,
    )


def decide_classification(
    *,
    category: str | None,
    confidence: float | None,
    direction: object,
    is_transfer: object,
    transaction_type: object,
    policy: ClassificationPolicy = DEFAULT_POLICY,
) -> ClassificationDecision:
    """Return the trust decision for a category prediction."""
    category_value = str(category) if category else None
    threshold = policy.threshold_for(category_value)
    review_floor = min(policy.review_floor, threshold)
    category_candidate = is_expense_category_candidate(
        direction,
        is_transfer,
        transaction_type,
    )
    if not category_candidate:
        return ClassificationDecision(
            action="not_applicable",
            reason_code="not_expense_category_candidate",
            threshold_used=threshold,
            review_floor=review_floor,
            category=category_value,
            confidence=confidence,
            category_candidate=False,
        )
    if not category_value:
        return ClassificationDecision(
            action="manual",
            reason_code="missing_prediction",
            threshold_used=threshold,
            review_floor=review_floor,
            category=None,
            confidence=confidence,
            category_candidate=True,
        )
    if confidence is None:
        return ClassificationDecision(
            action="manual",
            reason_code="missing_confidence",
            threshold_used=threshold,
            review_floor=review_floor,
            category=category_value,
            confidence=None,
            category_candidate=True,
        )
    if category_value == OTHER_CATEGORY and not policy.allow_other_accept:
        return ClassificationDecision(
            action="review",
            reason_code="other_requires_review",
            threshold_used=threshold,
            review_floor=review_floor,
            category=category_value,
            confidence=confidence,
            category_candidate=True,
        )
    if confidence >= threshold:
        return ClassificationDecision(
            action="accept",
            reason_code="confidence_at_or_above_threshold",
            threshold_used=threshold,
            review_floor=review_floor,
            category=category_value,
            confidence=confidence,
            category_candidate=True,
        )
    if confidence >= review_floor:
        return ClassificationDecision(
            action="review",
            reason_code="confidence_below_accept_threshold",
            threshold_used=threshold,
            review_floor=review_floor,
            category=category_value,
            confidence=confidence,
            category_candidate=True,
        )
    return ClassificationDecision(
        action="manual",
        reason_code="confidence_below_review_floor",
        threshold_used=threshold,
        review_floor=review_floor,
        category=category_value,
        confidence=confidence,
        category_candidate=True,
    )


def recommended_action_for_decision(decision: ClassificationDecision) -> str:
    """API action name derived from the classification decision."""
    if decision.action == "accept":
        return "accept_candidate"
    if decision.action == "not_applicable":
        return "not_category_candidate"
    if decision.action == "manual":
        return "needs_manual_label"
    return "review"


def review_priority_for_decision(decision: ClassificationDecision) -> int:
    """Lower value means the row should be reviewed earlier."""
    order = {
        "manual": 0,
        "review": 20,
        "accept": 40,
        "not_applicable": 90,
    }
    return order[decision.action]
