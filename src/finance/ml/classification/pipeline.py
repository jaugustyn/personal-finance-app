"""Build the supervised classification pipeline.

Features:
- text (merchant + title) → two parallel TF-IDF vectorizers (word + char_wb)
  to handle Polish merchant noise (uppercase, abbreviations, BLIK refs).
- numeric:
    * abs_amount_log: log1p(|amount|), helps separate small "kawa" vs large
      "Allegro" vs huge "wynagrodzenie" rows.
    * day_of_week: 0..6 one-hot.

The pipeline is a single sklearn `Pipeline` so it can be persisted with joblib
and loaded by the API without any custom unpickling code.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from finance.transactions.normalization import normalize_merchant

REQUIRED_COLUMNS = ["text", "abs_amount", "day_of_week"]
FEATURE_V2_COLUMNS = [
    "text",
    "merchant_norm",
    "abs_amount",
    "amount_bucket",
    "day_of_week",
    "month",
    "transaction_type",
    "source",
]


class _AmountLogTransform(BaseEstimator, TransformerMixin):
    """log1p(|amount|) on a (n,1) column. Pickle-safe — top-level class."""

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


def _numeric_features() -> Pipeline:
    return Pipeline(
        [("log1p_abs", _AmountLogTransform()), ("scale", StandardScaler())]
    )


def build_pipeline(estimator: BaseEstimator) -> Pipeline:
    """Build the full TF-IDF + numeric → estimator pipeline."""
    features = ColumnTransformer(
        transformers=[
            ("text", _text_features(), "text"),
            ("amount", _numeric_features(), ["abs_amount"]),
            (
                "dow",
                OneHotEncoder(categories=[list(range(7))], handle_unknown="ignore"),
                ["day_of_week"],
            ),
        ],
        remainder="drop",
        sparse_threshold=1.0,
    )
    return Pipeline([("features", features), ("clf", estimator)])


def build_pipeline_v2(estimator: BaseEstimator) -> Pipeline:
    """Experimental feature set for evidence comparison, not runtime default."""
    features = ColumnTransformer(
        transformers=[
            ("text", _text_features(), "text"),
            (
                "merchant_norm",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    min_df=1,
                    lowercase=True,
                    sublinear_tf=True,
                ),
                "merchant_norm",
            ),
            ("amount", _numeric_features(), ["abs_amount"]),
            (
                "categorical",
                OneHotEncoder(handle_unknown="ignore"),
                ["amount_bucket", "month", "transaction_type", "source"],
            ),
            (
                "dow",
                OneHotEncoder(categories=[list(range(7))], handle_unknown="ignore"),
                ["day_of_week"],
            ),
        ],
        remainder="drop",
        sparse_threshold=1.0,
    )
    return Pipeline([("features", features), ("clf", estimator)])


def add_feature_v2_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    merchant = out["merchant"] if "merchant" in out.columns else out["text"]
    out["merchant_norm"] = merchant.fillna("").map(normalize_merchant)
    out["transaction_type"] = out.get("transaction_type", "purchase")
    out["transaction_type"] = out["transaction_type"].fillna("purchase").astype(str)
    out["source"] = out.get("source", "unknown")
    out["source"] = out["source"].fillna("unknown").astype(str)
    if "booking_date" in out.columns:
        month = pd.to_datetime(out["booking_date"], errors="coerce").dt.month.fillna(0)
        out["month"] = month.astype(int)
    else:
        out["month"] = 0
    amount = out["abs_amount"].astype(float).abs()
    out["amount_bucket"] = pd.cut(
        amount,
        bins=[-0.01, 20, 100, 500, 2000, float("inf")],
        labels=["micro", "small", "medium", "large", "very_large"],
    ).astype(str)
    return out


def to_features(df: pd.DataFrame) -> pd.DataFrame:
    """Validate and select the columns the pipeline expects."""
    missing = set(REQUIRED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Missing required feature columns: {sorted(missing)}")
    return df[REQUIRED_COLUMNS]


def to_features_v2(df: pd.DataFrame) -> pd.DataFrame:
    enriched = add_feature_v2_columns(df)
    missing = set(FEATURE_V2_COLUMNS) - set(enriched.columns)
    if missing:
        raise ValueError(f"Missing required feature-v2 columns: {sorted(missing)}")
    return enriched[FEATURE_V2_COLUMNS]
