"""Report builders for category-classification evidence."""
from __future__ import annotations

import pandas as pd

from finance.ml.classification.evaluation import (
    EVIDENCE_THRESHOLD,
    TARGET_THRESHOLD_ACCURACY,
    _best_non_dummy,
    _feature_decision,
    build_label_readiness,
    build_validation_slices,
    evaluate,
    evaluate_feature_v2,
)


def build_evidence_report(
    real_df: pd.DataFrame,
    *,
    augmented_df: pd.DataFrame | None = None,
    external_df: pd.DataFrame | None = None,
    n_splits: int = 5,
    seed: int = 42,
) -> dict:
    """Build thesis-oriented report: real-only plus optional extra datasets."""
    label_readiness = build_label_readiness(real_df)
    experiments = {
        "real_only": evaluate(real_df, n_splits=n_splits, seed=seed),
    }
    external_summary: dict[str, object] = {"provided": external_df is not None}
    if external_df is not None:
        external_labelled = external_df[external_df["category"].notna()].reset_index(
            drop=True
        )
        external_summary.update(
            {
                "n_rows": int(len(external_df)),
                "n_labelled": int(len(external_labelled)),
                "class_counts": external_labelled["category"].value_counts().to_dict(),
            }
        )
        if not external_labelled.empty:
            experiments["external_only"] = evaluate(
                external_labelled,
                n_splits=n_splits,
                seed=seed,
            )
            experiments["real_plus_external"] = evaluate(
                pd.concat([real_df, external_labelled], ignore_index=True, sort=False),
                n_splits=n_splits,
                seed=seed,
            )

    feature_variants = {
        "baseline": experiments["real_only"],
        "feature_v2": evaluate_feature_v2(real_df, n_splits=n_splits, seed=seed),
    }
    feature_decision = _feature_decision(
        feature_variants["baseline"],
        feature_variants["feature_v2"],
    )
    validation_slices = build_validation_slices(real_df, seed=seed)
    selected = "real_only"
    if augmented_df is not None:
        combined = pd.concat([real_df, augmented_df], ignore_index=True, sort=False)
        experiments["augmented"] = evaluate(combined, n_splits=n_splits, seed=seed)

    report = dict(experiments[selected])
    best_model = _best_non_dummy(experiments["real_only"])
    best_report = (
        experiments["real_only"]["models"].get(best_model, {})
        if best_model is not None
        else {}
    )
    report.update(
        {
            "report_type": "classification_evidence",
            "selected_experiment": selected,
            "selected_experiment_note": (
                "real_only is the primary quality signal. Augmented/external "
                "experiments are reported separately and do not replace real labels."
            ),
            "experiments": experiments,
            "feature_variants": feature_variants,
            "feature_decision": feature_decision,
            "validation_slices": validation_slices,
            "confusion_hotspots": best_report.get("confusion_hotspots", []),
            "confidence_policy": {
                "source_model": best_model,
                "default_threshold": EVIDENCE_THRESHOLD,
                "target_accuracy": TARGET_THRESHOLD_ACCURACY,
                "per_category": best_report.get(
                    "recommended_thresholds_by_category",
                    {},
                ),
            },
            "feature_v2_note": (
                "Experimental comparison only. Runtime classifier_latest remains "
                "on the baseline feature set until reviewed."
            ),
            "label_readiness": label_readiness,
            "external_data": external_summary,
            "external_data_note": (
                "External public/synthetic datasets are reported as separate "
                "experiments. They do not replace real manually confirmed labels."
            ),
            "target_macro_f1": 0.75,
            "privacy_note": (
                "Report contains aggregate metrics only. Raw bank exports and "
                "model artifacts stay in gitignored data/raw, data/private and data/models."
            ),
        }
    )
    return report
