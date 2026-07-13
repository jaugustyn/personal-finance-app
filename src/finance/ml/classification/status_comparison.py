"""Small presentation helpers for registry-backed model recommendations."""
from __future__ import annotations

from typing import Any

from finance.ml.classification.constants import CONFIDENCE_RECOMMENDATION_THRESHOLD


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def recommend_model(
    comparison: list[dict[str, Any]],
    status: dict[str, Any],
    readiness: dict[str, Any],
) -> dict[str, Any]:
    """Recommend the best registered promotable candidate.

    Runtime recommendations use registry rows, never whichever JSON file is newest
    on disk.
    """
    candidates = [row for row in comparison if not row.get("skipped")]
    if candidates:
        selected = min(candidates, key=lambda row: int(row.get("rank") or 10**9))
        recommendation = {
            "model_id": selected["model_id"],
            "estimator": selected["estimator"],
            "feature_set": selected["feature_set"],
            "reason_code": "best_holdout_result",
            "action_codes": [],
            "warning_codes": [],
            "macro_f1": selected.get("macro_f1"),
            "weighted_f1": selected.get("weighted_f1"),
            "coverage_at_055": selected.get("coverage_at_055"),
            "accuracy_at_055": selected.get("accuracy_at_055"),
            "confidence_threshold": CONFIDENCE_RECOMMENDATION_THRESHOLD,
            "based_on_report": True,
        }
    else:
        recommendation = {
            "model_id": None,
            "estimator": None,
            "feature_set": None,
            "reason_code": "no_promotable_candidate",
            "action_codes": ["train_recommended"],
            "warning_codes": ["no_promotable_candidate"],
            "macro_f1": None,
            "weighted_f1": None,
            "coverage_at_055": None,
            "accuracy_at_055": None,
            "confidence_threshold": CONFIDENCE_RECOMMENDATION_THRESHOLD,
            "based_on_report": False,
        }

    for row in comparison:
        row["is_recommended"] = row.get("model_id") == recommendation["model_id"]

    current_matches = bool(
        recommendation["estimator"]
        and status.get("exists")
        and not status.get("load_error")
        and status.get("model_version_id") == recommendation["model_id"]
        and not status.get("compatibility_warnings")
    )
    if recommendation["estimator"]:
        recommendation["action_codes"].append(
            "current_matches_recommended" if current_matches else "activate_recommended"
        )
        recommendation["action_codes"].append("reclassify_after_training")

    if status.get("missing_categories"):
        recommendation["warning_codes"].append("missing_categories")
    if readiness.get("level") in {"insufficient", "minimum"}:
        recommendation["warning_codes"].append("limited_labels")
    if status.get("compatibility_warnings"):
        recommendation["warning_codes"].append("artifact_compatibility")

    recommendation["action_codes"] = list(
        dict.fromkeys(recommendation["action_codes"])
    )
    recommendation["warning_codes"] = list(
        dict.fromkeys(recommendation["warning_codes"])
    )
    return recommendation
