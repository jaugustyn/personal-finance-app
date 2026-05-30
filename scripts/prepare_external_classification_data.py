"""Normalize supported public external datasets for local ML experiments.

The output is intended for local experiments under ``data/processed``. Raw
external files and generated normalized datasets should stay gitignored.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finance.ml.classification.external import load_kaggle_personal_finance  # noqa: E402

DEFAULT_KAGGLE_INPUT = Path(
    "data/external/kaggle_personal_finance_data/Personal_Finance_Dataset.csv"
)
DEFAULT_OUTPUT = Path("data/processed/external_kaggle_personal_finance_classification.csv")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        choices=["kaggle-personal-finance"],
        default="kaggle-personal-finance",
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_KAGGLE_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--include-unlabelled",
        action="store_true",
        help="Keep rows such as salary that are transaction-type examples, not category labels.",
    )
    args = parser.parse_args()

    if args.source != "kaggle-personal-finance":
        raise ValueError(f"Unsupported source: {args.source}")

    df = load_kaggle_personal_finance(
        args.input,
        include_unlabelled=args.include_unlabelled,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)

    summary = {
        "source": args.source,
        "input": str(args.input),
        "output": str(args.output),
        "rows": int(len(df)),
        "labelled_rows": int(df["category"].notna().sum()),
        "class_counts": df["category"].value_counts(dropna=False).to_dict(),
        "transaction_type_counts": df["transaction_type"].value_counts().to_dict(),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
