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
from finance.ml.classification.train import (  # noqa: E402
    _load_from_files,
    _load_synthetic,
    build_evidence_report,
)
from finance.ml.evidence import (  # noqa: E402
    build_anomaly_review,
    build_eda_summary,
    build_forecasting_evidence,
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
    classification: dict[str, Any],
    forecasting: dict[str, Any],
    anomaly: dict[str, Any],
    privacy: dict[str, Any],
) -> None:
    linear = classification["models"].get("linear_svc", {})
    dummy = classification["models"].get("dummy_most_frequent", {})
    feature_decision = classification.get("feature_decision", {})
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

    content = f"""# ML Evidence Summary

Generated: `{ts}`

## Classification

Selected experiment: `{classification.get('selected_experiment')}`

{_model_table(classification)}

LinearSVC macro-F1 lift vs dummy: `{lift}`

Feature-set recommendation: `{feature_decision.get('recommended_feature_set', 'baseline')}`

Reason: {feature_decision.get('reason', 'n/a')}

## Forecasting

{chr(10).join(forecast_lines)}

## Anomaly Review

- Flagged in private review set: `{anomaly.get('flagged', 0)}`
- Reviewed rows: `{anomaly.get('reviewed_count', 0)}`
- precision@20: `{anomaly.get('precision_at_20')}`
- precision@50: `{anomaly.get('precision_at_50')}`

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
        df = _load_from_files(list(args.from_files))

    synth = _load_synthetic(args.augment) if args.augment else None
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    classification = build_evidence_report(df, augmented_df=synth)
    eda = build_eda_summary(df)
    forecasting = build_forecasting_evidence(df)

    review = build_anomaly_review(df, top_n=args.anomaly_top_n)
    anomaly_summary = review.public_summary
    review_for_precision = review.private_rows
    if args.review_file is not None and args.review_file.exists():
        review_for_precision = pd.read_csv(args.review_file)
    anomaly_summary = _apply_precision_review(anomaly_summary, review_for_precision)

    privacy = _privacy_check([classification, eda, forecasting, anomaly_summary], df)
    if not privacy["passed"]:
        raise SystemExit(
            "Public evidence payload may contain raw merchant/title values. "
            f"Leak count: {privacy['raw_value_leak_count']}."
        )

    reports = {
        f"classification_{ts}.json": classification,
        f"eda_{ts}.json": eda,
        f"forecasting_{ts}.json": forecasting,
        f"anomaly_summary_{ts}.json": anomaly_summary,
        "privacy_check_latest.json": privacy,
    }
    written: dict[str, Path] = {}
    for filename, payload in reports.items():
        out = args.reports_dir / filename
        _write_json(out, payload)
        written[filename] = out

    _copy_latest(written[f"classification_{ts}.json"], "latest_classification.json")
    _copy_latest(written[f"eda_{ts}.json"], "latest_eda.json")
    _copy_latest(written[f"forecasting_{ts}.json"], "latest_forecasting.json")
    _copy_latest(written[f"anomaly_summary_{ts}.json"], "latest_anomaly_summary.json")

    args.private_dir.mkdir(parents=True, exist_ok=True)
    review_path = args.private_dir / f"anomaly_review_{ts}.csv"
    review.private_rows.to_csv(review_path, index=False)
    shutil.copyfile(review_path, args.private_dir / "latest_anomaly_review.csv")

    _write_summary_markdown(
        args.reports_dir / "summary.md",
        ts=ts,
        classification=classification,
        forecasting=forecasting,
        anomaly=anomaly_summary,
        privacy=privacy,
    )

    print(f"Wrote aggregate reports to {args.reports_dir}")
    print(f"Wrote private anomaly review to {args.private_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
