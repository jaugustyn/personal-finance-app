"""Offline category-classification evidence CLI.

Runtime models are created only through the DB-backed ``POST /ml/retrain`` workflow.
This module keeps file loading helpers used by the aggregate evidence generator.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from finance.domain.enums import BankSource
from finance.ingestion import get_parser
from finance.ml.classification.constants import REPORTS_DIR
from finance.ml.classification.dataset import dtos_to_dataframe, load_training_set
from finance.ml.classification.external import load_kaggle_personal_finance
from finance.ml.classification.reports import build_evidence_report


def _load_from_files(paths: list[Path]) -> pd.DataFrame:
    """Parse bank files; without provenance their categories are not gold labels."""
    all_dtos = []
    for path in paths:
        parser = get_parser(_guess_source(path))
        with path.open("rb") as handle:
            all_dtos.extend(parser.parse(handle, filename=path.name))
    return dtos_to_dataframe(all_dtos)


def _guess_source(path: Path) -> BankSource:
    name = path.name.lower()
    if "pekao" in name or "pekaosa" in name:
        return BankSource.PEKAO
    if "revolut" in name or "account-statement" in name:
        return BankSource.REVOLUT
    raise ValueError(f"Cannot infer source for {path}")


def _load_synthetic(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"text", "abs_amount", "day_of_week", "category"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Synthetic CSV missing columns: {missing}")
    df["source"] = df["source"].fillna("synthetic") if "source" in df else "synthetic"
    return df


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--from-files", nargs="+", type=Path)
    source.add_argument("--from-db", action="store_true")
    parser.add_argument("--augment", type=Path, default=None)
    parser.add_argument("--external-kaggle", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.from_db:
        from finance.db import SessionLocal

        with SessionLocal() as session:
            frame = load_training_set(session)
    else:
        frame = _load_from_files(list(args.from_files))

    synthetic = _load_synthetic(args.augment) if args.augment else None
    external = (
        load_kaggle_personal_finance(args.external_kaggle)
        if args.external_kaggle
        else None
    )
    report = build_evidence_report(
        frame,
        augmented_df=synthetic,
        external_df=external,
    )
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = REPORTS_DIR / f"classification_{timestamp}.json"
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    print(f"Category evidence -> {output}")
    if report.get("skipped"):
        print(f"Evaluation skipped: {report.get('reason')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
