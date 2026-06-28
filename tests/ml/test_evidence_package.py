from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import scripts.build_ml_evidence as build_ml_evidence
import scripts.inspect_report as inspect_report
from finance.ml.evidence import (
    EVIDENCE_SCHEMA_VERSION,
    AnomalyReview,
    build_evidence_package,
    validate_evidence_package,
)


def _model() -> dict[str, object]:
    return {
        "macro_f1": 0.5,
        "weighted_f1": 0.6,
        "confusion_matrix": [[2, 0], [1, 1]],
        "confidence_curve": [
            {
                "threshold": 0.55,
                "coverage": 1.0,
                "accuracy_on_covered": 0.75,
                "covered": 4,
            }
        ],
    }


def _classification() -> dict[str, object]:
    return {
        "report_type": "classification_evidence",
        "selected_experiment": "real_only",
        "models": {
            "dummy_most_frequent": _model(),
            "linear_svc": _model(),
        },
        "class_counts": {"food": 4, "transport": 4},
        "n_total_labelled": 8,
        "n_classes": 2,
        "n_splits": 2,
        "label_readiness": {
            "level": "minimum",
            "total_labelled": 8,
            "minimum_total": 300,
            "recommended_total": 800,
            "ideal_total": 2000,
            "minimum_per_category": 20,
            "below_minimum_per_category": ["food", "transport"],
            "date_span_months": 2,
        },
    }


def _transaction_type() -> dict[str, object]:
    return {
        "report_type": "transaction_type_classification_evidence",
        "classification_task": "multiclass_transaction_type",
        "label_source": "silver_transaction_type",
        "runtime_policy": "evidence_only_rules_remain_source_of_truth",
        "models": {
            "dummy_most_frequent": _model(),
            "linear_svc": _model(),
        },
        "class_counts": {"purchase": 4, "salary": 4},
        "n_total_labelled": 8,
        "n_classes": 2,
        "n_splits": 2,
    }


def _forecasting() -> dict[str, object]:
    return {
        "horizon": 1,
        "series": [
            {
                "category": None,
                "n_months": 4,
                "best_model": "naive",
                "models": {"naive": {"rmse": 1.0}},
            }
        ],
    }


def _anomaly() -> dict[str, object]:
    return {
        "top_n": 5,
        "flagged": 0,
        "reason_counts": {},
        "examples": [],
        "precision_at_k": None,
        "precision_at_20": None,
        "precision_at_50": None,
        "reviewed_count": 0,
    }


def _subscriptions() -> dict[str, object]:
    return {
        "detector": "cadence_amount_heuristic",
        "subscriptions_detected": 0,
        "estimated_monthly_cost": 0.0,
        "examples": [],
    }


def _privacy(*, passed: bool = True) -> dict[str, object]:
    return {
        "checked_raw_values": 2,
        "raw_value_leak_count": 0 if passed else 1,
        "passed": passed,
    }


def _package(*, privacy_passed: bool = True) -> dict[str, object]:
    return build_evidence_package(
        generated_at="20260605T120000Z",
        source="files",
        category_classification=_classification(),
        transaction_type_classification=_transaction_type(),
        forecasting=_forecasting(),
        anomaly_detection=_anomaly(),
        subscriptions=_subscriptions(),
        privacy_check=_privacy(passed=privacy_passed),
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_report_set(reports_dir: Path, package: dict[str, object]) -> None:
    reports_dir.mkdir()
    sections = package["sections"]
    assert isinstance(sections, dict)
    _write_json(
        reports_dir / "latest_classification.json",
        sections.get("category_classification", _classification()),
    )
    _write_json(
        reports_dir / "latest_transaction_type_classification.json",
        sections.get("transaction_type_classification", _transaction_type()),
    )
    _write_json(reports_dir / "latest_eda.json", {"n_rows": 0})
    _write_json(reports_dir / "latest_forecasting.json", sections.get("forecasting", _forecasting()))
    _write_json(
        reports_dir / "latest_anomaly_summary.json",
        sections.get("anomaly_detection", _anomaly()),
    )
    _write_json(
        reports_dir / "latest_subscriptions.json",
        sections.get("subscriptions", _subscriptions()),
    )
    _write_json(reports_dir / "latest_evidence_package.json", package)
    _write_json(reports_dir / "privacy_check_latest.json", package["privacy_check"])
    (reports_dir / "summary.md").write_text("# Summary", encoding="utf-8")


def test_build_evidence_package_has_stable_schema_and_sections() -> None:
    package = _package()

    assert package["schema_version"] == EVIDENCE_SCHEMA_VERSION
    assert package["source"] == "files"
    assert set(package["sections"]) == {
        "category_classification",
        "transaction_type_classification",
        "forecasting",
        "anomaly_detection",
        "subscriptions",
    }
    assert package["privacy_check"]["passed"] is True
    assert validate_evidence_package(package) == []


def test_build_ml_evidence_cli_writes_latest_files_without_external_services(
    monkeypatch,
    tmp_path: Path,
) -> None:
    reports_dir = tmp_path / "reports"
    private_dir = tmp_path / "private"
    df = pd.DataFrame(
        [
            {
                "booking_date": "2026-01-01",
                "amount": -10.0,
                "merchant": "Private Merchant",
                "title": "Private Title",
            }
        ]
    )

    monkeypatch.setattr(build_ml_evidence, "_load_from_files", lambda paths: df)
    monkeypatch.setattr(build_ml_evidence, "build_evidence_report", lambda *args, **kwargs: _classification())
    monkeypatch.setattr(
        build_ml_evidence,
        "build_transaction_type_evidence_report",
        lambda *args, **kwargs: _transaction_type(),
    )
    monkeypatch.setattr(build_ml_evidence, "build_eda_summary", lambda *args, **kwargs: {"n_rows": 1})
    monkeypatch.setattr(
        build_ml_evidence,
        "build_forecasting_evidence",
        lambda *args, **kwargs: _forecasting(),
    )
    monkeypatch.setattr(
        build_ml_evidence,
        "build_subscription_evidence",
        lambda *args, **kwargs: _subscriptions(),
    )
    monkeypatch.setattr(
        build_ml_evidence,
        "build_anomaly_review",
        lambda *args, **kwargs: AnomalyReview(
            private_rows=pd.DataFrame(),
            public_summary=_anomaly(),
        ),
    )

    result = build_ml_evidence.main(
        [
            "--from-files",
            str(tmp_path / "pekao.csv"),
            "--reports-dir",
            str(reports_dir),
            "--private-dir",
            str(private_dir),
        ]
    )

    assert result == 0
    for filename in [
        "latest_classification.json",
        "latest_transaction_type_classification.json",
        "latest_eda.json",
        "latest_forecasting.json",
        "latest_anomaly_summary.json",
        "latest_subscriptions.json",
        "latest_evidence_package.json",
        "privacy_check_latest.json",
        "summary.md",
    ]:
        assert (reports_dir / filename).exists()

    package = json.loads((reports_dir / "latest_evidence_package.json").read_text())
    assert package["schema_version"] == "2.0"
    assert package["source"] == "files"
    assert package["privacy_check"]["passed"] is True
    summary = (reports_dir / "summary.md").read_text(encoding="utf-8")
    assert "## Category Classification" in summary
    assert "## LLM / RAG Narrative" in summary
    assert "Private Merchant" not in str(package)


def test_inspect_report_strict_validates_complete_package(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    _write_report_set(reports_dir, _package())

    assert inspect_report.inspect_reports(reports_dir, strict=True) == 0


def test_inspect_report_strict_fails_when_package_section_is_missing(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    package = _package()
    sections = package["sections"]
    assert isinstance(sections, dict)
    sections.pop("subscriptions")
    _write_report_set(reports_dir, package)

    assert inspect_report.inspect_reports(reports_dir, strict=True) == 1


def test_inspect_report_strict_fails_when_privacy_check_fails(tmp_path: Path) -> None:
    reports_dir = tmp_path / "reports"
    _write_report_set(reports_dir, _package(privacy_passed=False))

    assert inspect_report.inspect_reports(reports_dir, strict=True) == 1
