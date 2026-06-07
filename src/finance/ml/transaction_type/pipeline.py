"""Sklearn pipeline for transaction-type evidence experiments."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

REQUIRED_COLUMNS = ["text", "abs_amount", "direction", "source"]


class _AmountLogTransform(BaseEstimator, TransformerMixin):
    """log1p(abs(amount)) transform for a one-column numeric feature."""

    def fit(self, X, y=None):  # noqa: D401, N803
        return self

    def transform(self, X):  # noqa: N803
        arr = np.asarray(X, dtype=float).reshape(-1, 1)
        return np.log1p(np.abs(arr))


def _text_features() -> FeatureUnion:
    return FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    analyzer="word",
                    ngram_range=(1, 2),
                    min_df=1,
                    lowercase=True,
                    sublinear_tf=True,
                ),
            ),
            (
                "char",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=1,
                    lowercase=True,
                    sublinear_tf=True,
                ),
            ),
        ]
    )


def _amount_features() -> Pipeline:
    return Pipeline(
        [("log1p_abs", _AmountLogTransform()), ("scale", StandardScaler())]
    )


def build_pipeline(estimator: BaseEstimator) -> Pipeline:
    features = ColumnTransformer(
        transformers=[
            ("text", _text_features(), "text"),
            ("amount", _amount_features(), ["abs_amount"]),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                ["direction", "source"],
            ),
        ],
        remainder="drop",
        sparse_threshold=1.0,
    )
    return Pipeline([("features", features), ("clf", estimator)])


def to_features(df: pd.DataFrame) -> pd.DataFrame:
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required transaction-type features: {sorted(missing)}")
    return df[REQUIRED_COLUMNS]
