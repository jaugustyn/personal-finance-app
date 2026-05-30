"""Inspect aggregate ML evidence reports without exposing private rows."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

LATEST_REPORTS = {
    "classification": "latest_classification.json",
    "eda": "latest_eda.json",
    "forecasting": "latest_forecasting.json",
    "anomaly": "latest_anomaly_summary.json",
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


def _print_classification(report: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    print("Classification")
    print("  Report type:", report.get("report_type", "classification"))
    print("  Selected experiment:", report.get("selected_experiment", "unknown"))
    if "experiments" in report:
        print("  Experiments:", ", ".join(report["experiments"].keys()))
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


def inspect_reports(reports_dir: Path, *, strict: bool) -> int:
    errors: list[str] = []
    warnings: list[str] = []

    if strict:
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

    eda = _load_json(reports_dir / LATEST_REPORTS["eda"])
    if eda is not None:
        _print_eda(eda)
    elif strict:
        errors.append("missing latest_eda.json")

    forecasting = _load_json(reports_dir / LATEST_REPORTS["forecasting"])
    if forecasting is not None:
        warnings.extend(_print_forecasting(forecasting))
    elif strict:
        errors.append("missing latest_forecasting.json")

    anomaly = _load_json(reports_dir / LATEST_REPORTS["anomaly"])
    if anomaly is not None:
        warnings.extend(_print_anomaly(anomaly))
    elif strict:
        errors.append("missing latest_anomaly_summary.json")

    privacy = _load_json(reports_dir / LATEST_REPORTS["privacy"])
    privacy_issues = _print_privacy(privacy)
    if privacy is None and not strict:
        warnings.extend(privacy_issues)
    else:
        errors.extend(privacy_issues)

    summary = reports_dir / "summary.md"
    print("\nSummary markdown:", "present" if summary.exists() else "missing")

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
    args = parser.parse_args(argv)
    return inspect_reports(args.reports_dir, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
