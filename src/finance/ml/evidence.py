"""Aggregate-only ML evidence helpers for thesis reports.

These helpers intentionally avoid exporting raw merchants/titles. They produce
safe summaries for documentation and keep row-level review data local.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from finance.ml.anomaly.detector import detect_anomalies
from finance.ml.forecasting.pipeline import build_monthly_series, evaluate_walk_forward
from finance.ml.subscriptions.detector import detect_subscriptions

EVIDENCE_SCHEMA_VERSION = "2.0"
EVIDENCE_SECTIONS = (
    "category_classification",
    "transaction_type_classification",
    "forecasting",
    "anomaly_detection",
    "subscriptions",
)
EVIDENCE_SEMANTIC_NOTE = (
    "transaction_type models money-flow semantics; category models expense "
    "budget taxonomy. Hard financial facts for LLM answers are computed by "
    "deterministic tools, not vector-only retrieval."
)


def _split_reasons(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def _prepared(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    if d.empty:
        return d
    d["booking_date"] = pd.to_datetime(d["booking_date"])
    if "abs_amount" not in d.columns:
        d["abs_amount"] = d["amount"].abs().astype(float)
    else:
        d["abs_amount"] = d["abs_amount"].astype(float)
    if "is_transfer" not in d.columns:
        d["is_transfer"] = False
    return d


def build_eda_summary(df: pd.DataFrame, *, top_n: int = 10) -> dict[str, Any]:
    """Return privacy-preserving EDA aggregates for visualisation reports."""
    d = _prepared(df)
    if d.empty:
        return {
            "n_rows": 0,
            "date_min": None,
            "date_max": None,
            "missing_counts": {},
            "direction_counts": {},
            "category_counts": {},
            "transfer_count": 0,
            "monthly_cashflow": [],
            "top_merchants": [],
        }

    missing_cols = [
        c for c in ("booking_date", "amount", "abs_amount", "merchant", "title", "category")
        if c in d.columns
    ]
    category = (
        d["category"].fillna("(missing)")
        if "category" in d.columns
        else pd.Series([], dtype=str)
    )
    direction = d["direction"] if "direction" in d.columns else pd.Series([], dtype=str)

    monthly = (
        d.assign(month=d["booking_date"].dt.to_period("M").astype(str))
        .groupby(["month", "direction"], dropna=False)["abs_amount"]
        .sum()
        .unstack(fill_value=0)
        .reset_index()
    )
    for col in ("credit", "debit"):
        if col not in monthly.columns:
            monthly[col] = 0.0
    monthly["net"] = monthly["credit"].astype(float) - monthly["debit"].astype(float)

    merchant_col = d["merchant"].fillna("(missing)").astype(str)
    debit_mask = (
        d["direction"] == "debit"
        if "direction" in d.columns
        else pd.Series(True, index=d.index)
    )
    merchant_totals = (
        d[debit_mask]
        .assign(_merchant=merchant_col)
        .groupby("_merchant")["abs_amount"]
        .agg(["sum", "count"])
        .sort_values("sum", ascending=False)
        .head(top_n)
        .reset_index()
    )
    top_merchants = [
        {
            "merchant_alias": f"merchant_{idx + 1:02d}",
            "amount": float(row["sum"]),
            "count": int(row["count"]),
        }
        for idx, row in merchant_totals.iterrows()
    ]

    return {
        "n_rows": int(len(d)),
        "date_min": d["booking_date"].min().date().isoformat(),
        "date_max": d["booking_date"].max().date().isoformat(),
        "missing_counts": {c: int(d[c].isna().sum()) for c in missing_cols},
        "direction_counts": {str(k): int(v) for k, v in direction.value_counts().items()},
        "category_counts": {str(k): int(v) for k, v in category.value_counts().items()},
        "transfer_count": int(d["is_transfer"].fillna(False).sum()),
        "monthly_cashflow": [
            {
                "month": str(row["month"]),
                "income": float(row["credit"]),
                "expenses": float(row["debit"]),
                "net": float(row["net"]),
            }
            for _, row in monthly.sort_values("month").iterrows()
        ],
        "top_merchants": top_merchants,
    }


def build_forecasting_evidence(
    df: pd.DataFrame,
    *,
    categories: list[str | None] | None = None,
    horizon: int = 1,
    min_train: int = 4,
) -> dict[str, Any]:
    """Evaluate forecasting models per category with walk-forward CV."""
    d = _prepared(df)
    if d.empty:
        return {"series": []}

    if categories is None:
        observed = sorted(c for c in d["category"].dropna().astype(str).unique())
        categories = [None, *observed]

    out = []
    for category in categories:
        series = build_monthly_series(d, category=category, direction="debit")
        cv = evaluate_walk_forward(series, horizon=horizon, min_train=min_train)
        best = min(cv.keys(), key=lambda k: cv[k]["rmse"]) if cv else None
        out.append(
            {
                "category": category,
                "n_months": int(len(series)),
                "total": float(series.sum()),
                "best_model": best,
                "models": cv,
            }
        )
    return {
        "horizon": horizon,
        "min_train": min_train,
        "series": out,
    }


@dataclass
class AnomalyReview:
    private_rows: pd.DataFrame
    public_summary: dict[str, Any]


def build_anomaly_review(df: pd.DataFrame, *, top_n: int = 20) -> AnomalyReview:
    """Prepare private row-level anomaly review and public aggregate summary."""
    d = _prepared(df)
    if d.empty:
        empty = pd.DataFrame()
        return AnomalyReview(
            private_rows=empty,
            public_summary={
                "top_n": top_n,
                "flagged": 0,
                "reason_counts": {},
                "examples": [],
                "precision_at_k": None,
                "precision_at_20": None,
                "precision_at_50": None,
                "reviewed_count": 0,
                "precision_note": "Fill after manual private review of private_rows.",
            },
        )

    scored = detect_anomalies(d, direction="debit").df
    flagged = (
        scored[scored["anomaly"] & (scored["anomaly_type"].fillna("") != "model_only")]
        .sort_values(["priority_score", "severity"], ascending=False)
        .head(top_n)
    )
    private_rows = flagged[
        ["booking_date", "merchant", "title", "amount", "category", "severity", "reasons"]
    ].copy()
    private_rows["booking_date"] = pd.to_datetime(private_rows["booking_date"]).dt.date.astype(str)
    private_rows["is_relevant"] = ""
    private_rows["review_note"] = ""

    reason_counts: dict[str, int] = {}
    for raw in flagged["reasons"].fillna(""):
        for reason in _split_reasons(raw):
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

    examples = []
    for idx, row in flagged.head(5).reset_index(drop=True).iterrows():
        examples.append(
            {
                "transaction_alias": f"anomaly_{idx + 1:02d}",
                "category": row.get("category"),
                "severity": float(row.get("severity", 0.0)),
                "reasons": _split_reasons(row.get("reasons")),
            }
        )

    return AnomalyReview(
        private_rows=private_rows,
        public_summary={
            "top_n": top_n,
            "flagged": int(len(flagged)),
            "reason_counts": reason_counts,
            "examples": examples,
            "precision_at_k": None,
            "precision_at_20": None,
            "precision_at_50": None,
            "reviewed_count": 0,
            "precision_note": "Fill after manual private review of private_rows.",
        },
    )


def build_subscription_evidence(df: pd.DataFrame, *, top_n: int = 10) -> dict[str, Any]:
    """Return privacy-preserving aggregate evidence for subscription detection."""
    d = _prepared(df)
    if d.empty:
        return {
            "detector": "cadence_amount_heuristic",
            "subscriptions_detected": 0,
            "estimated_monthly_cost": 0.0,
            "cadence_counts": {},
            "confidence_summary": {},
            "examples": [],
        }

    subs = detect_subscriptions(d)
    cadence_counts: dict[str, int] = {}
    confidences: list[float] = []
    monthly_cost = 0.0
    examples: list[dict[str, Any]] = []
    for idx, sub in enumerate(subs):
        cadence_counts[sub.cadence] = cadence_counts.get(sub.cadence, 0) + 1
        confidences.append(float(sub.confidence))
        monthly_cost += float(sub.estimated_monthly_cost)
        if len(examples) < top_n:
            examples.append(
                {
                    "subscription_alias": f"subscription_{idx + 1:02d}",
                    "cadence": sub.cadence,
                    "occurrences": int(sub.occurrences),
                    "confidence": float(sub.confidence),
                    "estimated_monthly_cost": float(sub.estimated_monthly_cost),
                }
            )

    confidence_summary = {
        "min": min(confidences) if confidences else None,
        "mean": sum(confidences) / len(confidences) if confidences else None,
        "max": max(confidences) if confidences else None,
    }
    return {
        "detector": "cadence_amount_heuristic",
        "subscriptions_detected": int(len(subs)),
        "estimated_monthly_cost": float(round(monthly_cost, 2)),
        "cadence_counts": cadence_counts,
        "confidence_summary": confidence_summary,
        "examples": examples,
        "privacy_note": "Merchant names are replaced with stable aliases in public evidence.",
    }


def build_evidence_package(
    *,
    generated_at: str,
    source: str,
    category_classification: dict[str, Any],
    transaction_type_classification: dict[str, Any],
    forecasting: dict[str, Any],
    anomaly_detection: dict[str, Any],
    subscriptions: dict[str, Any],
    privacy_check: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the stable public evidence package artifact."""
    if source not in {"db", "files"}:
        raise ValueError("source must be 'db' or 'files'")
    return {
        "report_type": "ml_evidence_package",
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "generated_at": generated_at,
        "source": source,
        "sections": {
            "category_classification": category_classification,
            "transaction_type_classification": transaction_type_classification,
            "forecasting": forecasting,
            "anomaly_detection": anomaly_detection,
            "subscriptions": subscriptions,
        },
        "semantic_note": EVIDENCE_SEMANTIC_NOTE,
        "privacy_check": privacy_check or {},
    }


def validate_evidence_package(package: dict[str, Any]) -> list[str]:
    """Return structural validation errors for the stable evidence package."""
    errors: list[str] = []
    if package.get("report_type") != "ml_evidence_package":
        errors.append("evidence_package.report_type must be ml_evidence_package")
    if package.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        errors.append(f"evidence_package.schema_version must be {EVIDENCE_SCHEMA_VERSION}")
    if not package.get("generated_at"):
        errors.append("evidence_package.generated_at is required")
    if package.get("source") not in {"db", "files"}:
        errors.append("evidence_package.source must be db or files")
    sections = package.get("sections")
    if not isinstance(sections, dict):
        errors.append("evidence_package.sections must be an object")
        sections = {}
    for key in EVIDENCE_SECTIONS:
        if key not in sections:
            errors.append(f"evidence_package.sections.{key} is required")
    if not package.get("semantic_note"):
        errors.append("evidence_package.semantic_note is required")
    privacy = package.get("privacy_check")
    if not isinstance(privacy, dict):
        errors.append("evidence_package.privacy_check must be an object")
    elif privacy.get("passed") is not True:
        errors.append("evidence_package.privacy_check.passed must be true")
    return errors
