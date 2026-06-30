"""Final fitting helpers for category classifier artifacts."""
from __future__ import annotations

import pandas as pd

from finance.ml.classification.constants import DEFAULT_FEATURE_SET, FEATURE_SETS
from finance.ml.classification.evaluation import (
    _filter_rare_classes,
    filter_category_training_rows,
)
from finance.ml.classification.exceptions import (
    InsufficientClassSupport,
    UnknownEstimator,
    UnknownFeatureSet,
)
from finance.ml.classification.pipeline import (
    build_pipeline,
    build_pipeline_v2,
    to_features,
    to_features_v2,
)
from finance.ml.classification.registry import ESTIMATORS


def _feature_builder(feature_set: str):
    if feature_set == "baseline":
        return build_pipeline, to_features
    if feature_set == "feature_v2":
        return build_pipeline_v2, to_features_v2
    raise UnknownFeatureSet(
        f"Unknown feature_set: {feature_set}. Choose: {sorted(FEATURE_SETS)}"
    )


def fit_final(
    df: pd.DataFrame,
    estimator_name: str,
    *,
    feature_set: str = DEFAULT_FEATURE_SET,
):
    """Fit the selected estimator on all valid confirmed category labels."""
    if estimator_name not in ESTIMATORS:
        raise UnknownEstimator(
            f"Unknown estimator: {estimator_name}. Choose: {list(ESTIMATORS)}"
        )
    df = filter_category_training_rows(df)
    df, _ = _filter_rare_classes(df)
    if df.empty or df["category"].astype(str).nunique() < 2:
        raise InsufficientClassSupport(
            "At least two category classes with sufficient support are required."
        )
    pipeline_builder, feature_selector = _feature_builder(feature_set)
    X = feature_selector(df)  # noqa: N806
    y = df["category"].astype(str)
    pipe = pipeline_builder(ESTIMATORS[estimator_name]())
    pipe.fit(X, y)
    return pipe
