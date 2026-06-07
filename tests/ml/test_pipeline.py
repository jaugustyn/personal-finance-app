"""Smoke tests for the classification pipeline."""
import pandas as pd
import pytest

from finance.ml.classification.pipeline import build_pipeline, build_pipeline_text
from finance.ml.classification.registry import ESTIMATORS


@pytest.fixture
def tiny_dataset() -> tuple[pd.DataFrame, pd.Series]:
    df = pd.DataFrame(
        {
            "text": [
                "CARREFOUR KRAKOW",
                "BIEDRONKA NIEPOLOMICE",
                "LIDL bochnia",
                "ORLEN STACJA",
                "SHELL paliwo",
                "ORANGE FLEX",
                "OPENAI",
            ],
            "abs_amount": [31.41, 62.13, 76.20, 200.97, 219.35, 350.0, 34.99],
            "day_of_week": [5, 3, 1, 4, 0, 2, 0],
        }
    )
    y = pd.Series(
        ["food", "food", "food", "transport", "transport", "subscriptions",
         "subscriptions"]
    )
    return df, y


def test_pipeline_fits_and_predicts(tiny_dataset) -> None:
    X, y = tiny_dataset
    pipe = build_pipeline(ESTIMATORS["logreg"]())
    pipe.fit(X, y)
    preds = pipe.predict(X)
    assert preds.shape == (len(X),)
    # On training data the pipeline should at least be able to memorise.
    assert (preds == y.values).mean() > 0.5


def test_text_only_pipeline_fits_without_numeric_features(tiny_dataset) -> None:
    X, y = tiny_dataset
    # Text-only pipeline must work even when numeric features are absent (HF rows).
    X_text = X[["text"]]
    pipe = build_pipeline_text(ESTIMATORS["logreg"]())
    pipe.fit(X_text, y)
    preds = pipe.predict(X_text)
    assert preds.shape == (len(X_text),)
    assert (preds == y.values).mean() > 0.5
