"""Classifier report comparison and model recommendation helpers."""
from __future__ import annotations

from typing import Any

from finance.ml.classification.constants import (
    CALIBRATED_ESTIMATORS,
    CONFIDENCE_RECOMMENDATION_THRESHOLD,
    DEFAULT_RECOMMENDED_ESTIMATOR,
    DEFAULT_RECOMMENDED_FEATURE_SET,
)


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def confidence_point(
    model_report: dict[str, Any],
    threshold: float = CONFIDENCE_RECOMMENDATION_THRESHOLD,
) -> tuple[float | None, float | None]:
    for point in model_report.get("confidence_curve") or []:
        if abs(float(point.get("threshold", -1.0)) - threshold) < 1e-9:
            return (
                as_float(point.get("coverage")),
                as_float(point.get("accuracy_on_covered")),
            )
    return None, None


def iter_model_reports(
    report: dict[str, Any] | None,
) -> list[tuple[str, str, dict[str, Any]]]:
    if not report:
        return []
    out: list[tuple[str, str, dict[str, Any]]] = []
    feature_variants = report.get("feature_variants")
    if isinstance(feature_variants, dict):
        for feature_set, feature_report in feature_variants.items():
            if not isinstance(feature_report, dict):
                continue
            models = feature_report.get("models") or {}
            if not isinstance(models, dict):
                continue
            for estimator, model_report in models.items():
                if isinstance(model_report, dict):
                    out.append((str(feature_set), str(estimator), model_report))
    if out:
        return out

    models = report.get("models") or {}
    if isinstance(models, dict):
        for estimator, model_report in models.items():
            if isinstance(model_report, dict):
                out.append(("baseline", str(estimator), model_report))
    return out


def recommended_feature_set(
    report: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    if not report:
        return None, None
    decision = report.get("feature_decision")
    if not isinstance(decision, dict):
        return None, None
    feature_set = decision.get("recommended_feature_set")
    raw_reason = decision.get("reason")
    reason = raw_reason if isinstance(raw_reason, str) else None
    if feature_set not in {"baseline", "feature_v2"}:
        return None, reason
    return str(feature_set), reason


def slice_macro_f1(
    report: dict[str, Any] | None,
    slice_name: str,
    estimator: str,
) -> float | None:
    if not report:
        return None
    validation = report.get("validation_slices")
    if not isinstance(validation, dict):
        return None
    slice_report = validation.get(slice_name)
    if not isinstance(slice_report, dict) or slice_report.get("skipped"):
        return None
    models = slice_report.get("models")
    if not isinstance(models, dict):
        return None
    model = models.get(estimator)
    if not isinstance(model, dict) or model.get("skipped"):
        return None
    return as_float(model.get("macro_f1"))


def stability_score(
    report: dict[str, Any] | None,
    estimator: str,
) -> tuple[float | None, float | None, float | None]:
    time_macro = slice_macro_f1(report, "time_holdout", estimator)
    group_macro = slice_macro_f1(report, "merchant_group_holdout", estimator)
    values = [value for value in (time_macro, group_macro) if value is not None]
    score = sum(values) / len(values) if values else None
    return time_macro, group_macro, score


def model_comparison(
    report: dict[str, Any] | None,
    status: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    current_estimator = status.get("estimator") if status else None
    current_feature_set = (status.get("feature_set") or "baseline") if status else None
    rows: list[dict[str, Any]] = []
    for feature_set, estimator, model_report in iter_model_reports(report):
        coverage, accuracy = confidence_point(model_report)
        time_macro, group_macro, stability = stability_score(report, estimator)
        rows.append(
            {
                "estimator": estimator,
                "feature_set": feature_set,
                "rank": None,
                "macro_f1": as_float(model_report.get("macro_f1")),
                "weighted_f1": as_float(model_report.get("weighted_f1")),
                "coverage_at_055": coverage,
                "accuracy_at_055": accuracy,
                "time_holdout_macro_f1": time_macro,
                "merchant_group_macro_f1": group_macro,
                "stability_score": stability,
                "confidence_note": model_report.get("confidence_note"),
                "skipped": bool(model_report.get("skipped")),
                "error": model_report.get("error"),
                "is_recommended": False,
                "is_current": (
                    estimator == current_estimator and feature_set == current_feature_set
                ),
            }
        )

    rows.sort(
        key=lambda row: (
            row["skipped"],
            -(row["stability_score"] or 0.0),
            -(row["macro_f1"] or 0.0),
            -(row["weighted_f1"] or 0.0),
            row["feature_set"],
            row["estimator"],
        )
    )
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
    return rows


def recommend_model(
    report: dict[str, Any] | None,
    comparison: list[dict[str, Any]],
    status: dict[str, Any],
    readiness: dict[str, Any],
) -> dict[str, Any]:
    recommendation: dict[str, Any]
    actionable = [
        row
        for row in comparison
        if not row["skipped"] and not str(row["estimator"]).startswith("dummy")
    ]
    target_feature_set, feature_reason = recommended_feature_set(report)

    if not actionable:
        recommendation = {
            "estimator": DEFAULT_RECOMMENDED_ESTIMATOR,
            "feature_set": target_feature_set or DEFAULT_RECOMMENDED_FEATURE_SET,
            "reason_code": "no_report",
            "action_codes": ["train_recommended"],
            "warning_codes": ["no_report"],
            "macro_f1": None,
            "weighted_f1": None,
            "coverage_at_055": None,
            "accuracy_at_055": None,
            "confidence_threshold": CONFIDENCE_RECOMMENDATION_THRESHOLD,
            "based_on_report": False,
            "feature_decision_reason": feature_reason,
        }
    else:
        pool = (
            [row for row in actionable if row["feature_set"] == target_feature_set]
            if target_feature_set
            else []
        )
        if not pool:
            pool = actionable

        best = max(
            pool,
            key=lambda row: (
                row["stability_score"] if row["stability_score"] is not None else -1.0,
                row["macro_f1"] or 0.0,
            ),
        )
        best_macro = best["macro_f1"] or 0.0
        calibrated_pool = [
            row
            for row in pool
            if row["estimator"] in CALIBRATED_ESTIMATORS
            and (row["macro_f1"] or 0.0) >= best_macro - 0.02
        ]
        if calibrated_pool:
            selected = max(
                calibrated_pool,
                key=lambda row: (
                    row["stability_score"]
                    if row["stability_score"] is not None
                    else -1.0,
                    row["macro_f1"] or 0.0,
                ),
            )
            reason_code = (
                "best_calibrated_macro_f1"
                if selected["estimator"] == best["estimator"]
                else "prefer_calibrated_close"
            )
        else:
            selected = best
            reason_code = "best_macro_f1"

        recommendation = {
            "estimator": selected["estimator"],
            "feature_set": selected["feature_set"],
            "reason_code": reason_code,
            "action_codes": [],
            "warning_codes": [],
            "macro_f1": selected["macro_f1"],
            "weighted_f1": selected["weighted_f1"],
            "coverage_at_055": selected["coverage_at_055"],
            "accuracy_at_055": selected["accuracy_at_055"],
            "confidence_threshold": CONFIDENCE_RECOMMENDATION_THRESHOLD,
            "based_on_report": True,
            "feature_decision_reason": feature_reason,
        }

    for row in comparison:
        row["is_recommended"] = (
            row["estimator"] == recommendation["estimator"]
            and row["feature_set"] == recommendation["feature_set"]
        )

    status_feature_set = status.get("feature_set") or "baseline"
    if (
        not status.get("exists")
        or status.get("load_error")
        or status.get("estimator") != recommendation["estimator"]
        or status_feature_set != recommendation["feature_set"]
        or status.get("compatibility_warnings")
    ):
        recommendation["action_codes"].append("train_recommended")
    else:
        recommendation["action_codes"].append("current_matches_recommended")

    recommendation["action_codes"].append("reclassify_after_training")

    if readiness.get("below_recommended_per_category"):
        recommendation["action_codes"].append("balance_categories")
    if status.get("missing_categories"):
        recommendation["warning_codes"].append("missing_categories")
    if readiness.get("level") in {"insufficient", "minimum"}:
        recommendation["warning_codes"].append("limited_labels")
    if status.get("compatibility_warnings"):
        recommendation["warning_codes"].append("artifact_compatibility")
    if not report:
        recommendation["warning_codes"].append("no_report")

    recommendation["action_codes"] = list(dict.fromkeys(recommendation["action_codes"]))
    recommendation["warning_codes"] = list(dict.fromkeys(recommendation["warning_codes"]))
    return recommendation
