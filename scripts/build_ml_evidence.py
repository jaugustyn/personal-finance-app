"""Build aggregate ML evidence reports from local private data.

Outputs are split intentionally:
- ``data/reports``: aggregate JSON safe to reference in docs.
- ``data/private``: row-level anomaly review CSV, never commit.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finance.db import SessionLocal  # noqa: E402
from finance.domain.models import Transaction  # noqa: E402
from finance.ml.classification.external import load_kaggle_personal_finance  # noqa: E402
from finance.ml.classification.train import (  # noqa: E402
    _load_from_files,
    _load_synthetic,
    build_evidence_report,
)
from finance.ml.evidence import (  # noqa: E402
    build_anomaly_review,
    build_eda_summary,
    build_evidence_package,
    build_forecasting_evidence,
    build_subscription_evidence,
)
from finance.ml.transaction_type.train import (  # noqa: E402
    build_evidence_report as build_transaction_type_evidence_report,
)


def _safe_db_error(exc: SQLAlchemyError, database_url: str | None) -> str:
    message = str(exc)
    if not database_url:
        return message
    try:
        url = make_url(database_url)
        safe_url = url.render_as_string(hide_password=True)
        if url.password:
            message = message.replace(url.password, "***")
        message = message.replace(database_url, safe_url)
    except Exception:
        message = message.replace(database_url, "<database-url>")
    return message


def _load_all_from_db(session: Session) -> pd.DataFrame:
    rows = session.execute(
        select(
            Transaction.booking_date,
            Transaction.amount,
            Transaction.direction,
            Transaction.merchant,
            Transaction.title,
            Transaction.raw_category,
            Transaction.category,
            Transaction.category_source,
            Transaction.category_predicted,
            Transaction.category_predicted_source,
            Transaction.source,
            Transaction.is_transfer,
            Transaction.transaction_type,
        )
    ).all()
    df = pd.DataFrame(
        rows,
        columns=[
            "booking_date",
            "amount",
            "direction",
            "merchant",
            "title",
            "raw_category",
            "category",
            "category_source",
            "category_predicted",
            "category_predicted_source",
            "source",
            "is_transfer",
            "transaction_type",
        ],
    )
    if df.empty:
        return df
    df["abs_amount"] = df["amount"].abs().astype(float)
    df["day_of_week"] = pd.to_datetime(df["booking_date"]).dt.dayofweek
    df["text"] = (df["merchant"].fillna("") + " " + df["title"].fillna("")).str.strip()
    return df


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _copy_latest(src: Path, latest_name: str) -> Path:
    dst = src.with_name(latest_name)
    shutil.copyfile(src, dst)
    return dst


def _truthy_review(value: object) -> bool | None:
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "tak", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "nie", "no", "n"}:
        return False
    return None


def _apply_precision_review(summary: dict[str, Any], review_df: pd.DataFrame) -> dict[str, Any]:
    if review_df.empty or "is_relevant" not in review_df.columns:
        return summary

    labels = [_truthy_review(v) for v in review_df["is_relevant"].tolist()]
    reviewed = [v for v in labels if v is not None]
    summary["reviewed_count"] = len(reviewed)
    for k in (20, 50):
        top = labels[:k]
        labelled_top = [v for v in top if v is not None]
        key = f"precision_at_{k}"
        summary[key] = (
            float(sum(1 for v in labelled_top if v) / len(labelled_top))
            if labelled_top
            else None
        )
    summary["precision_at_k"] = summary.get("precision_at_20")
    if reviewed:
        summary["precision_note"] = (
            "Computed from private anomaly review labels in is_relevant column."
        )
    return summary


def _raw_values(df: pd.DataFrame) -> set[str]:
    values: set[str] = set()
    for col in ("merchant", "title", "text"):
        if col not in df.columns:
            continue
        for value in df[col].dropna().astype(str):
            clean = " ".join(value.strip().split())
            if len(clean) >= 4:
                values.add(clean)
    return values


def _privacy_check(public_payloads: list[dict[str, Any]], df: pd.DataFrame) -> dict[str, Any]:
    raw = _raw_values(df)
    blob = json.dumps(public_payloads, ensure_ascii=False)
    leaked = [value for value in raw if value and value in blob]
    return {
        "checked_raw_values": len(raw),
        "raw_value_leak_count": len(leaked),
        "passed": len(leaked) == 0,
    }


def _model_table(report: dict[str, Any]) -> str:
    lines = ["| Model | Macro-F1 | Weighted-F1 |", "|---|---:|---:|"]
    for name, info in report["models"].items():
        lines.append(
            f"| `{name}` | {info['macro_f1']:.3f} | {info['weighted_f1']:.3f} |"
        )
    return "\n".join(lines)


def _write_summary_markdown(
    path: Path,
    *,
    ts: str,
    source: str,
    schema_version: str,
    classification: dict[str, Any],
    transaction_type: dict[str, Any],
    forecasting: dict[str, Any],
    anomaly: dict[str, Any],
    subscriptions: dict[str, Any],
    privacy: dict[str, Any],
) -> None:
    linear = classification["models"].get("linear_svc", {})
    dummy = classification["models"].get("dummy_most_frequent", {})
    feature_decision = classification.get("feature_decision", {})
    label_readiness = classification.get("label_readiness", {})
    external_data = classification.get("external_data", {})
    linear_macro = linear.get("macro_f1")
    dummy_macro = dummy.get("macro_f1")
    lift = (
        f"{linear_macro - dummy_macro:.3f}"
        if isinstance(linear_macro, float) and isinstance(dummy_macro, float)
        else "n/a"
    )
    forecast_lines = []
    for item in forecasting.get("series", []):
        if item.get("best_model"):
            forecast_lines.append(
                f"- `{item.get('category') or 'all'}`: {item['best_model']} "
                f"({item['n_months']} months)"
            )
    if not forecast_lines:
        forecast_lines.append("- Not enough monthly data for walk-forward CV.")
    tx_models = transaction_type.get("models", {})
    tx_linear = tx_models.get("linear_svc", {}) if isinstance(tx_models, dict) else {}
    tx_dummy = tx_models.get("dummy_most_frequent", {}) if isinstance(tx_models, dict) else {}
    tx_linear_macro = tx_linear.get("macro_f1")
    tx_dummy_macro = tx_dummy.get("macro_f1")
    tx_lift = (
        f"{tx_linear_macro - tx_dummy_macro:.3f}"
        if isinstance(tx_linear_macro, float) and isinstance(tx_dummy_macro, float)
        else "n/a"
    )
    tx_runtime_policy = transaction_type.get(
        "runtime_policy",
        "evidence_only_rules_remain_source_of_truth",
    )

    content = f"""# ML Evidence Summary

Generated: `{ts}`

Source: `{source}`

Evidence package schema: `{schema_version}`

## Category Classification

Selected experiment: `{classification.get('selected_experiment')}`

{_model_table(classification)}

LinearSVC macro-F1 lift vs dummy: `{lift}`

Feature-set recommendation: `{feature_decision.get('recommended_feature_set', 'baseline')}`

Reason: {feature_decision.get('reason', 'n/a')}

## Label Readiness

- Level: `{label_readiness.get('level', 'unknown')}`
- Confirmed labels: `{label_readiness.get('total_labelled', 0)}` \
  (minimum `{label_readiness.get('minimum_total', 300)}`, recommended \
  `{label_readiness.get('recommended_total', 800)}`, ideal \
  `{label_readiness.get('ideal_total', 2000)}`)
- Per-category minimum: `{label_readiness.get('minimum_per_category', 20)}`
- Below minimum: `{', '.join(label_readiness.get('below_minimum_per_category', [])) or 'none'}`
- Date span: `{label_readiness.get('date_span_months')}` months

External data provided: `{external_data.get('provided', False)}`

## Transaction Type Classification

Task: `{transaction_type.get('classification_task', 'multiclass_transaction_type')}`

Label source: `{transaction_type.get('label_source', 'silver_transaction_type')}`

Runtime policy: `{tx_runtime_policy}`

Total silver labels: `{transaction_type.get('n_total_labelled', 0)}`

Classes: `{transaction_type.get('n_classes', 0)}`

LinearSVC macro-F1 lift vs dummy: `{tx_lift}`

## Forecasting

{chr(10).join(forecast_lines)}

## Anomaly Detection

- Flagged in private review set: `{anomaly.get('flagged', 0)}`
- Reviewed rows: `{anomaly.get('reviewed_count', 0)}`
- precision@20: `{anomaly.get('precision_at_20')}`
- precision@50: `{anomaly.get('precision_at_50')}`

## Subscriptions

- Detector: `{subscriptions.get('detector', 'cadence_amount_heuristic')}`
- Detected subscriptions: `{subscriptions.get('subscriptions_detected', 0)}`
- Estimated monthly cost: `{subscriptions.get('estimated_monthly_cost', 0.0)}`

## LLM / RAG Narrative

Hard financial facts are computed by deterministic tools and SQL-backed
analytics. The local LLM may route, summarize and phrase recommendations in
Polish; it is not used as vector-only RAG for counting facts.

## Privacy Check

- Raw values checked: `{privacy['checked_raw_values']}`
- Raw value leak count in public JSON: `{privacy['raw_value_leak_count']}`
- Passed: `{privacy['passed']}`
"""
    path.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--from-db", action="store_true")
    source.add_argument("--from-files", nargs="+", type=Path)
    parser.add_argument(
        "--database-url",
        default=None,
        help="Optional SQLAlchemy URL for --from-db; credentials are masked in errors.",
    )
    parser.add_argument("--augment", type=Path, default=None)
    parser.add_argument(
        "--external-kaggle",
        type=Path,
        default=None,
        help=(
            "Optional Kaggle Personal_Finance_Dataset.csv. Included only as "
            "external_only and real_plus_external experiments."
        ),
    )
    parser.add_argument("--reports-dir", type=Path, default=Path("data/reports"))
    parser.add_argument("--private-dir", type=Path, default=Path("data/private"))
    parser.add_argument("--anomaly-top-n", type=int, default=20)
    parser.add_argument(
        "--review-file",
        type=Path,
        default=None,
        help="Optional private anomaly_review CSV with is_relevant labels.",
    )
    args = parser.parse_args(argv)

    if args.from_db:
        source_name = "db"
        engine = None
        try:
            if args.database_url:
                engine = create_engine(args.database_url)
                SessionMaker = sessionmaker(bind=engine)
                with SessionMaker() as session:
                    df = _load_all_from_db(session)
            else:
                with SessionLocal() as session:
                    df = _load_all_from_db(session)
        except SQLAlchemyError as exc:
            details = _safe_db_error(exc, args.database_url)
            raise SystemExit(f"Could not load transactions from local DB: {details}") from None
        finally:
            if engine is not None:
                engine.dispose()
    else:
        source_name = "files"
        df = _load_from_files(list(args.from_files))

    synth = _load_synthetic(args.augment) if args.augment else None
    external = (
        load_kaggle_personal_finance(args.external_kaggle)
        if args.external_kaggle
        else None
    )
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    classification = build_evidence_report(
        df,
        augmented_df=synth,
        external_df=external,
    )
    eda = build_eda_summary(df)
    forecasting = build_forecasting_evidence(df)
    transaction_type = build_transaction_type_evidence_report(df)
    subscriptions = build_subscription_evidence(df)

    review = build_anomaly_review(df, top_n=args.anomaly_top_n)
    anomaly_summary = review.public_summary
    review_for_precision = review.private_rows
    if args.review_file is not None and args.review_file.exists():
        review_for_precision = pd.read_csv(args.review_file)
    anomaly_summary = _apply_precision_review(anomaly_summary, review_for_precision)

    evidence_package = build_evidence_package(
        generated_at=ts,
        source=source_name,
        category_classification=classification,
        transaction_type_classification=transaction_type,
        forecasting=forecasting,
        anomaly_detection=anomaly_summary,
        subscriptions=subscriptions,
    )
    privacy = _privacy_check(
        [
            classification,
            transaction_type,
            eda,
            forecasting,
            anomaly_summary,
            subscriptions,
            evidence_package,
        ],
        df,
    )
    evidence_package["privacy_check"] = privacy
    if not privacy["passed"]:
        raise SystemExit(
            "Public evidence payload may contain raw merchant/title values. "
            f"Leak count: {privacy['raw_value_leak_count']}."
        )

    reports = {
        f"classification_{ts}.json": classification,
        f"transaction_type_classification_{ts}.json": transaction_type,
        f"eda_{ts}.json": eda,
        f"forecasting_{ts}.json": forecasting,
        f"anomaly_summary_{ts}.json": anomaly_summary,
        f"subscriptions_{ts}.json": subscriptions,
        f"evidence_package_{ts}.json": evidence_package,
        "privacy_check_latest.json": privacy,
    }
    written: dict[str, Path] = {}
    for filename, payload in reports.items():
        out = args.reports_dir / filename
        _write_json(out, payload)
        written[filename] = out

    _copy_latest(written[f"classification_{ts}.json"], "latest_classification.json")
    _copy_latest(
        written[f"transaction_type_classification_{ts}.json"],
        "latest_transaction_type_classification.json",
    )
    _copy_latest(written[f"eda_{ts}.json"], "latest_eda.json")
    _copy_latest(written[f"forecasting_{ts}.json"], "latest_forecasting.json")
    _copy_latest(written[f"anomaly_summary_{ts}.json"], "latest_anomaly_summary.json")
    _copy_latest(written[f"subscriptions_{ts}.json"], "latest_subscriptions.json")
    _copy_latest(written[f"evidence_package_{ts}.json"], "latest_evidence_package.json")

    args.private_dir.mkdir(parents=True, exist_ok=True)
    review_path = args.private_dir / f"anomaly_review_{ts}.csv"
    review.private_rows.to_csv(review_path, index=False)
    shutil.copyfile(review_path, args.private_dir / "latest_anomaly_review.csv")

    _write_summary_markdown(
        args.reports_dir / "summary.md",
        ts=ts,
        source=source_name,
        schema_version=str(evidence_package["schema_version"]),
        classification=classification,
        transaction_type=transaction_type,
        forecasting=forecasting,
        anomaly=anomaly_summary,
        subscriptions=subscriptions,
        privacy=privacy,
    )

    print(f"Wrote aggregate reports to {args.reports_dir}")
    print(f"Wrote private anomaly review to {args.private_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
