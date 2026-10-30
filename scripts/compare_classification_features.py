"""Compare baseline and feature_v2 locally without modifying the model registry."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finance.db import SessionLocal  # noqa: E402
from finance.ml.classification.dataset import load_training_set  # noqa: E402
from finance.ml.classification.evaluation_sets import (  # noqa: E402
    current_evaluation_set,
    split_transaction_ids,
    validate_evaluation_set,
)
from finance.ml.classification.feature_comparison import compare_features  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-db", action="store_true", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    with SessionLocal() as session:
        evaluation_set = current_evaluation_set(session)
        if evaluation_set is None:
            parser.error("Freeze an evaluation set before comparing features.")
        df = load_training_set(session)
        if not validate_evaluation_set(session, evaluation_set, df):
            # Validation can mark the in-memory row invalid; this tool is read-only.
            session.rollback()
            parser.error("The frozen evaluation set is invalid; review and freeze a new set.")
        evaluation_set_id = evaluation_set.id
        split_ids = split_transaction_ids(session, evaluation_set_id)
    report = compare_features(
        df,
        split_ids=split_ids,
        data_source="confirmed_local",
        evaluation_set_id=evaluation_set_id,
    )
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    output = args.output or Path("data/reports") / f"feature_comparison_{timestamp}.json"
    payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8")
    print(f"Feature comparison written to {output}; evaluation role: development_validation.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
