"""Unit tests for deterministic classification trust policy."""
from __future__ import annotations

import pytest

from finance.ml.classification.policy import (
    ClassificationPolicy,
    decide_classification,
    policy_from_report,
)


def _decide(
    *,
    category: str | None = "food",
    confidence: float | None = 0.8,
    direction: str = "debit",
    is_transfer: bool = False,
    transaction_type: str = "purchase",
    policy: ClassificationPolicy | None = None,
):
    return decide_classification(
        category=category,
        confidence=confidence,
        direction=direction,
        is_transfer=is_transfer,
        transaction_type=transaction_type,
        policy=policy or ClassificationPolicy(default_threshold=0.55),
    )


def test_high_confidence_expense_prediction_is_accepted() -> None:
    decision = _decide(confidence=0.91)

    assert decision.action == "accept"
    assert decision.reason_code == "confidence_at_or_above_threshold"
    assert decision.threshold_used == 0.55
    assert decision.category_candidate is True


def test_medium_confidence_expense_prediction_requires_review() -> None:
    decision = _decide(confidence=0.40)

    assert decision.action == "review"
    assert decision.reason_code == "confidence_below_accept_threshold"


def test_low_confidence_expense_prediction_requires_manual_label() -> None:
    decision = _decide(confidence=0.10)

    assert decision.action == "manual"
    assert decision.reason_code == "confidence_below_review_floor"


@pytest.mark.parametrize(
    ("direction", "is_transfer", "transaction_type"),
    [
        ("credit", False, "income"),
        ("debit", True, "purchase"),
        ("debit", False, "person_transfer"),
    ],
)
def test_non_expense_candidates_are_not_applicable(
    direction: str,
    is_transfer: bool,
    transaction_type: str,
) -> None:
    decision = _decide(
        direction=direction,
        is_transfer=is_transfer,
        transaction_type=transaction_type,
    )

    assert decision.action == "not_applicable"
    assert decision.reason_code == "not_expense_category_candidate"
    assert decision.category_candidate is False


def test_other_category_is_never_auto_accepted_by_default() -> None:
    decision = _decide(category="other", confidence=0.99)

    assert decision.action == "review"
    assert decision.reason_code == "other_requires_review"


def test_missing_confidence_requires_manual_label() -> None:
    decision = _decide(confidence=None)

    assert decision.action == "manual"
    assert decision.reason_code == "missing_confidence"


def test_category_threshold_from_report_overrides_default() -> None:
    policy = policy_from_report(
        {
            "confidence_policy": {
                "default_threshold": 0.55,
                "per_category": {
                    "food": {"threshold": 0.90},
                    "transport": {"threshold": 0.70},
                },
            }
        }
    )

    decision = _decide(category="food", confidence=0.80, policy=policy)

    assert decision.action == "review"
    assert decision.threshold_used == 0.90
