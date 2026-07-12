"""Evaluate the opt-in local Ollama fallback on the active frozen holdouts."""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finance.config import get_settings  # noqa: E402
from finance.db import SessionLocal  # noqa: E402
from finance.domain.enums import Category  # noqa: E402
from finance.llm.client import model_manifest  # noqa: E402
from finance.ml.classification.dataset import load_training_set  # noqa: E402
from finance.ml.classification.evaluation_sets import (  # noqa: E402
    current_evaluation_set,
    split_transaction_ids,
)
from finance.ml.classification.predict import (  # noqa: E402
    active_classification_policy,
    predict_transaction,
)

LABELS = sorted(item.value for item in Category)


def _evaluate_slice(frame, policy) -> dict[str, object]:
    truth: list[str] = []
    baseline: list[str] = []
    hybrid: list[str] = []
    covered_truth: list[str] = []
    covered_predicted: list[str] = []
    fallback_count = 0
    fallback_latencies: list[float] = []
    for row in frame.itertuples(index=False):
        amount = Decimal(str(-abs(float(row.abs_amount))))
        common = {
            "merchant": str(row.merchant or ""),
            "title": str(row.title or ""),
            "amount": amount,
            "booking_date": row.booking_date,
            "source": str(row.source or "unknown"),
            "transaction_type": str(row.transaction_type or "purchase"),
            "direction": "debit",
            "is_transfer": False,
            "policy": policy,
        }
        base = predict_transaction(**common, use_llm_fallback=False)
        started = time.perf_counter_ns()
        routed = predict_transaction(**common, use_llm_fallback=True)
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        truth.append(str(row.category))
        baseline.append(base.category)
        hybrid.append(routed.category)
        if routed.fallback_used:
            fallback_count += 1
            fallback_latencies.append(elapsed_ms)
        if (
            not base.fallback_used
            and base.confidence is not None
            and base.confidence >= base.threshold
            and base.category != Category.OTHER.value
        ):
            covered_truth.append(str(row.category))
            covered_predicted.append(base.category)
    base_macro = float(
        f1_score(truth, baseline, labels=LABELS, average="macro", zero_division=0)
    )
    hybrid_macro = float(
        f1_score(truth, hybrid, labels=LABELS, average="macro", zero_division=0)
    )
    covered_accuracy = (
        float(np.mean(np.asarray(covered_truth) == np.asarray(covered_predicted)))
        if covered_truth
        else None
    )
    return {
        "n": len(truth),
        "baseline_macro_f1": base_macro,
        "hybrid_macro_f1": hybrid_macro,
        "macro_f1_gain": hybrid_macro - base_macro,
        "fallback_count": fallback_count,
        "fallback_hit_rate": fallback_count / len(truth),
        "covered": len(covered_truth),
        "coverage": len(covered_truth) / len(truth),
        "covered_accuracy": covered_accuracy,
        "llm_latency_ms": {
            "median": float(np.median(fallback_latencies)) if fallback_latencies else None,
            "p95": float(np.percentile(fallback_latencies, 95)) if fallback_latencies else None,
            "p99": float(np.percentile(fallback_latencies, 99)) if fallback_latencies else None,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    if not get_settings().llm_fallback_enabled:
        raise SystemExit("Set LLM_FALLBACK_ENABLED=true for this explicit experiment.")
    with SessionLocal() as session:
        evaluation_set = current_evaluation_set(session)
        if evaluation_set is None:
            raise SystemExit("Freeze a private evaluation set before the LLM experiment.")
        split_ids = split_transaction_ids(session, evaluation_set.id)
        df = load_training_set(session)
    policy = active_classification_policy()
    slices = {
        name: _evaluate_slice(
            df[df["transaction_id"].astype(int).isin(ids)].reset_index(drop=True),
            policy,
        )
        for name, ids in split_ids.items()
    }
    def metric(item: dict[str, object], key: str) -> float | None:
        value = item.get(key)
        return float(value) if isinstance(value, int | float) else None

    gains = [metric(item, "macro_f1_gain") for item in slices.values()]
    no_regression = all(value is not None and value >= -0.01 for value in gains)
    improves_one = any(value is not None and value >= 0.01 for value in gains)
    covered_accuracy = all(
        (value := metric(item, "covered_accuracy")) is not None and value >= 0.90
        for item in slices.values()
    )
    hit_rate = all(
        (value := metric(item, "fallback_hit_rate")) is not None and value <= 0.10
        for item in slices.values()
    )
    report = {
        "report_type": "local_llm_fallback_experiment",
        "generated_at": datetime.now(UTC).isoformat(),
        "evaluation_set_id": evaluation_set.id,
        "model": model_manifest(),
        "environment": {"platform": platform.platform(), "python": platform.python_version()},
        "slices": slices,
        "gates": {
            "no_macro_regression_over_001": no_regression,
            "improves_one_holdout_by_001": improves_one,
            "covered_accuracy_at_least_090": covered_accuracy,
            "fallback_hit_rate_at_most_010": hit_rate,
            "passed": no_regression and improves_one and covered_accuracy and hit_rate,
        },
        "runtime_policy": "opt_in_suggestions_always_require_user_acceptance",
        "privacy_note": "Aggregate metrics only; prompts and transaction rows are not exported.",
    }
    output = args.output or Path("data/reports") / (
        "llm_fallback_" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + ".json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False),
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
