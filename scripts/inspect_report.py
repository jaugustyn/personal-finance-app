"""Inspect aggregate ML evidence reports without exposing private rows."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finance.ml.evidence import EVIDENCE_SECTIONS, validate_evidence_package  # noqa: E402

LATEST_REPORTS = {
    "classification": "latest_classification.json",
    "transaction_type": "latest_transaction_type_classification.json",
    "eda": "latest_eda.json",
    "forecasting": "latest_forecasting.json",
    "subscriptions": "latest_subscriptions.json",
    "anomaly": "latest_anomaly_summary.json",
    "evidence_package": "latest_evidence_package.json",
    "privacy": "privacy_check_latest.json",
}


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _fmt(value: object, digits: int = 3) -> str:
    return f"{value:.{digits}f}" if isinstance(value, float) else "n/a"


def _classification_path(reports_dir: Path) -> Path | None:
    latest = reports_dir / LATEST_REPORTS["classification"]
    if latest.exists():
        return latest
    reports = sorted(reports_dir.glob("classification_*.json"))
    return reports[-1] if reports else None


def _require_keys(report: dict[str, Any], keys: list[str], prefix: str) -> list[str]:
    return [f"{prefix}.{key} is required" for key in keys if key not in report]


def _validate_model_metrics(report: dict[str, Any], prefix: str) -> list[str]:
    errors: list[str] = []
    models = report.get("models")
    if not isinstance(models, dict):
        return [f"{prefix}.models must be an object"]
    for model_name in ("dummy_most_frequent", "linear_svc"):
        model = models.get(model_name)
        if not isinstance(model, dict):
            errors.append(f"{prefix}.models.{model_name} is required")
            continue
        errors.extend(
            _require_keys(
                model,
                ["macro_f1", "weighted_f1", "confusion_matrix"],
                f"{prefix}.models.{model_name}",
            )
        )
        if "confusion_matrix" in model and not isinstance(model["confusion_matrix"], list):
            errors.append(f"{prefix}.models.{model_name}.confusion_matrix must be a list")
    return errors


def _validate_category_section(report: dict[str, Any], prefix: str) -> list[str]:
    errors = _require_keys(
        report,
        ["models", "class_counts", "n_total_labelled", "n_classes"],
        prefix,
    )
    if report.get("report_type") == "classification_registry_snapshot":
        lifecycle = report.get("model_lifecycle")
        if not isinstance(lifecycle, dict) or not lifecycle.get("active_model_id"):
            errors.append(f"{prefix}.model_lifecycle.active_model_id is required")
        models = report.get("models")
        if isinstance(models, dict):
            for model_name, model in models.items():
                if not isinstance(model, dict):
                    errors.append(f"{prefix}.models.{model_name} must be an object")
                    continue
                errors.extend(
                    _require_keys(
                        model,
                        ["macro_f1", "weighted_f1", "confusion_matrix", "time", "merchant", "oof"],
                        f"{prefix}.models.{model_name}",
                    )
                )
    else:
        errors.extend(_validate_model_metrics(report, prefix))
    return errors


def _validate_transaction_type_section(report: dict[str, Any], prefix: str) -> list[str]:
    errors = _require_keys(
        report,
        ["label_source", "runtime_policy", "models", "class_counts"],
        prefix,
    )
    if report.get("label_source") != "confirmed_transaction_type":
        errors.append(f"{prefix}.label_source must be confirmed_transaction_type")
    if report.get("runtime_policy") != "evidence_only_rules_remain_source_of_truth":
        errors.append(
            f"{prefix}.runtime_policy must keep transaction-type ML evidence-only"
        )
    errors.extend(_validate_model_metrics(report, prefix))
    return errors


def _validate_forecasting_section(report: dict[str, Any], prefix: str) -> list[str]:
    errors = _require_keys(report, ["series"], prefix)
    if "series" in report and not isinstance(report["series"], list):
        errors.append(f"{prefix}.series must be a list")
    return errors


def _validate_anomaly_section(report: dict[str, Any], prefix: str) -> list[str]:
    return _require_keys(
        report,
        ["flagged", "precision_at_k", "precision_at_20", "precision_at_50"],
        prefix,
    )


def _validate_subscriptions_section(report: dict[str, Any], prefix: str) -> list[str]:
    errors = _require_keys(
        report,
        ["detector", "subscriptions_detected", "estimated_monthly_cost", "examples"],
        prefix,
    )
    if "examples" in report and not isinstance(report["examples"], list):
        errors.append(f"{prefix}.examples must be a list")
    return errors


def _validate_package_sections(package: dict[str, Any]) -> list[str]:
    errors = validate_evidence_package(package)
    sections = package.get("sections")
    if not isinstance(sections, dict):
        return errors
    validators = {
        "category_classification": _validate_category_section,
        "transaction_type_classification": _validate_transaction_type_section,
        "forecasting": _validate_forecasting_section,
        "anomaly_detection": _validate_anomaly_section,
        "subscriptions": _validate_subscriptions_section,
    }
    for section_name in EVIDENCE_SECTIONS:
        section = sections.get(section_name)
        if not isinstance(section, dict):
            errors.append(f"evidence_package.sections.{section_name} must be an object")
            continue
        errors.extend(
            validators[section_name](section, f"evidence_package.sections.{section_name}")
        )
    return errors


def _print_classification(report: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    print("Classification")
    print("  Report type:", report.get("report_type", "classification"))
    print("  Selected experiment:", report.get("selected_experiment", "unknown"))
    if "experiments" in report:
        print("  Experiments:", ", ".join(report["experiments"].keys()))
    external = report.get("external_data") or {}
    if external:
        print(
            "  External data:",
            "provided=" + str(external.get("provided", False)),
            "labelled=" + str(external.get("n_labelled", 0)),
        )
    print("  Total labelled:", report.get("n_total_labelled", "n/a"))
    print("  Classes:", report.get("n_classes", "n/a"), "| splits:", report.get("n_splits", "n/a"))

    models = report.get("models", {})
    linear = models.get("linear_svc", {})
    dummy = models.get("dummy_most_frequent", {})
    linear_macro = linear.get("macro_f1")
    dummy_macro = dummy.get("macro_f1")
    print("  linear_svc macro-F1:", _fmt(linear_macro))
    print("  linear_svc weighted-F1:", _fmt(linear.get("weighted_f1")))
    print("  dummy macro-F1:", _fmt(dummy_macro))
    if isinstance(linear_macro, float) and isinstance(dummy_macro, float):
        lift = linear_macro - dummy_macro
        print("  macro-F1 lift vs dummy:", _fmt(lift))
        if lift <= 0:
            warnings.append("linear_svc is not better than dummy_most_frequent")

    curve = linear.get("confidence_curve") or []
    tau_055 = next((row for row in curve if row.get("threshold") == 0.55), None)
    if tau_055:
        print(
            "  tau=0.55:",
            "coverage=" + _fmt(tau_055.get("coverage")),
            "accuracy=" + _fmt(tau_055.get("accuracy_on_covered")),
        )
    else:
        warnings.append("missing confidence curve row for tau=0.55")

    readiness = report.get("label_readiness") or {}
    if readiness:
        level = readiness.get("level", "unknown")
        total = readiness.get("total_labelled", 0)
        print("  Label readiness:", level, f"({total} confirmed)")
        print(
            "  Label targets:",
            f"minimum={readiness.get('minimum_total')}",
            f"recommended={readiness.get('recommended_total')}",
            f"ideal={readiness.get('ideal_total')}",
        )
        below_minimum = readiness.get("below_minimum_per_category") or []
        if below_minimum:
            print("  Below per-category minimum:", ", ".join(below_minimum))
        if level in {"insufficient", "minimum"}:
            warnings.append(
                "classification labels are below recommended thesis-quality target"
            )
    else:
        warnings.append("missing label readiness summary")

    print("  Class counts:")
    for cls, n in sorted(report.get("class_counts", {}).items(), key=lambda x: -x[1]):
        print(f"    {cls:18s} {n}")
    dropped = report.get("dropped_rare_classes", [])
    if dropped:
        print("  Dropped rare classes:", dropped)
    return warnings


def _print_eda(report: dict[str, Any]) -> None:
    print("\nEDA")
    print("  Rows:", report.get("n_rows", "n/a"))
    print("  Date range:", report.get("date_min"), "-", report.get("date_max"))
    print("  Transfers:", report.get("transfer_count", "n/a"))
    missing = report.get("missing_counts", {})
    if missing:
        print("  Missing:", ", ".join(f"{k}={v}" for k, v in missing.items()))


def _print_transaction_type(report: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    print("\nTransaction type classification")
    print("  Report type:", report.get("report_type", "transaction_type_classification"))
    print("  Label source:", report.get("label_source", "n/a"))
    print("  Runtime policy:", report.get("runtime_policy", "n/a"))
    if report.get("skipped"):
        reason = report.get("reason", "unknown")
        print("  Skipped:", reason)
        return [f"transaction_type classification skipped: {reason}"]
    print("  Total labels:", report.get("n_total_labelled", "n/a"))
    print("  Classes:", report.get("n_classes", "n/a"), "| splits:", report.get("n_splits", "n/a"))
    models = report.get("models", {})
    linear = models.get("linear_svc", {}) if isinstance(models, dict) else {}
    dummy = models.get("dummy_most_frequent", {}) if isinstance(models, dict) else {}
    print("  linear_svc macro-F1:", _fmt(linear.get("macro_f1")))
    print("  linear_svc weighted-F1:", _fmt(linear.get("weighted_f1")))
    print("  dummy macro-F1:", _fmt(dummy.get("macro_f1")))
    linear_macro = linear.get("macro_f1")
    dummy_macro = dummy.get("macro_f1")
    if isinstance(linear_macro, float) and isinstance(dummy_macro, float):
        lift = linear_macro - dummy_macro
        print("  macro-F1 lift vs dummy:", _fmt(lift))
        if lift <= 0:
            warnings.append("transaction_type linear_svc is not better than dummy")
    return warnings


def _print_forecasting(report: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    print("\nForecasting")
    series = report.get("series", [])
    print("  Horizon:", report.get("horizon", "n/a"))
    print("  Series:", len(series))
    best_rows = [row for row in series if row.get("best_model")]
    if not best_rows:
        warnings.append("forecasting has no evaluated series with best_model")
        print("  Best models: none")
        return warnings
    for row in best_rows[:8]:
        print(
            f"  {row.get('category') or 'all'}: {row.get('best_model')} "
            f"({row.get('n_months')} months)"
        )
    return warnings


def _print_subscriptions(report: dict[str, Any]) -> None:
    print("\nSubscriptions")
    print("  Detector:", report.get("detector", "n/a"))
    print("  Detected:", report.get("subscriptions_detected", 0))
    print("  Estimated monthly cost:", report.get("estimated_monthly_cost", 0.0))


def _print_anomaly(report: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    print("\nAnomaly review")
    print("  Flagged:", report.get("flagged", 0))
    print("  Reviewed:", report.get("reviewed_count", 0))
    print("  precision@20:", report.get("precision_at_20"))
    print("  precision@50:", report.get("precision_at_50"))
    if report.get("precision_at_20") is None:
        warnings.append("anomaly precision@20 not filled from private review")
    return warnings


def _print_privacy(report: dict[str, Any] | None) -> list[str]:
    print("\nPrivacy check")
    if report is None:
        print("  Missing privacy_check_latest.json")
        return ["missing privacy check"]
    print("  Raw values checked:", report.get("checked_raw_values", "n/a"))
    print("  Raw value leak count:", report.get("raw_value_leak_count", "n/a"))
    print("  Passed:", report.get("passed"))
    return [] if report.get("passed") is True else ["privacy check failed"]


def inspect_reports(
    reports_dir: Path,
    *,
    strict: bool = False,
    profile: str | None = None,
) -> int:
    errors: list[str] = []
    warnings: list[str] = []

    strict_files = strict or profile is not None
    if strict_files:
        missing = [
            filename
            for filename in [*LATEST_REPORTS.values(), "summary.md"]
            if not (reports_dir / filename).exists()
        ]
        if missing:
            errors.append("missing strict evidence files: " + ", ".join(missing))

    classification_path = _classification_path(reports_dir)
    if classification_path is None:
        print("No classification reports found. Run scripts/build_ml_evidence.py first.")
        return 1

    print("Report path:", classification_path)
    classification = _load_json(classification_path)
    if classification is None:
        print("Could not read classification report.")
        return 1
    warnings.extend(_print_classification(classification))

    transaction_type = _load_json(reports_dir / LATEST_REPORTS["transaction_type"])
    if transaction_type is not None:
        warnings.extend(_print_transaction_type(transaction_type))
    elif strict_files:
        errors.append("missing latest_transaction_type_classification.json")

    eda = _load_json(reports_dir / LATEST_REPORTS["eda"])
    if eda is not None:
        _print_eda(eda)
    elif strict_files:
        errors.append("missing latest_eda.json")

    forecasting = _load_json(reports_dir / LATEST_REPORTS["forecasting"])
    if forecasting is not None:
        warnings.extend(_print_forecasting(forecasting))
    elif strict_files:
        errors.append("missing latest_forecasting.json")

    subscriptions = _load_json(reports_dir / LATEST_REPORTS["subscriptions"])
    if subscriptions is not None:
        _print_subscriptions(subscriptions)
    elif strict_files:
        errors.append("missing latest_subscriptions.json")

    anomaly = _load_json(reports_dir / LATEST_REPORTS["anomaly"])
    if anomaly is not None:
        warnings.extend(_print_anomaly(anomaly))
    elif strict_files:
        errors.append("missing latest_anomaly_summary.json")

    privacy = _load_json(reports_dir / LATEST_REPORTS["privacy"])
    privacy_issues = _print_privacy(privacy)
    if privacy is None and not strict_files:
        warnings.extend(privacy_issues)
    else:
        errors.extend(privacy_issues)

    summary = reports_dir / "summary.md"
    print("\nSummary markdown:", "present" if summary.exists() else "missing")
    package = reports_dir / LATEST_REPORTS["evidence_package"]
    print("Evidence package:", "present" if package.exists() else "missing")
    evidence_package = _load_json(package)
    if strict_files:
        if evidence_package is None:
            errors.append("missing latest_evidence_package.json")
        else:
            errors.extend(_validate_package_sections(evidence_package))
            statuses = evidence_package.get("section_status", {})
            if profile == "classification-strict":
                if statuses.get("category_classification") not in {
                    "complete",
                    "thesis_ready",
                }:
                    errors.append(
                        "classification-strict requires complete category classification"
                    )
            elif profile == "thesis-strict":
                if statuses.get("category_classification") != "thesis_ready":
                    errors.append(
                        "thesis-strict requires thesis_ready category classification"
                    )
                incomplete = [
                    key
                    for key in EVIDENCE_SECTIONS
                    if statuses.get(key) not in {"complete", "thesis_ready"}
                ]
                if incomplete:
                    errors.append(
                        "thesis-strict has incomplete sections: " + ", ".join(incomplete)
                    )

    if warnings:
        print("\nWarnings:")
        for item in warnings:
            print("  -", item)
    if errors:
        print("\nErrors:")
        for item in errors:
            print("  -", item)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reports-dir", type=Path, default=Path("data/reports"))
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Require complete latest_* evidence files and passing privacy check.",
    )
    parser.add_argument(
        "--profile",
        choices=["classification-strict", "thesis-strict"],
        default=None,
        help="Apply the selected evidence-completeness profile.",
    )
    args = parser.parse_args(argv)
    return inspect_reports(args.reports_dir, strict=args.strict, profile=args.profile)


if __name__ == "__main__":
    raise SystemExit(main())
