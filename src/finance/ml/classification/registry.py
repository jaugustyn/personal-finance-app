"""Registry of estimators we compare for the thesis evaluation chapter."""
from __future__ import annotations

from collections.abc import Callable

from sklearn.base import BaseEstimator
from sklearn.calibration import CalibratedClassifierCV
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC

ESTIMATORS: dict[str, Callable[[], BaseEstimator]] = {
    "dummy_most_frequent": lambda: DummyClassifier(strategy="most_frequent"),
    "logreg": lambda: LogisticRegression(
        max_iter=2000, class_weight="balanced", C=1.0, n_jobs=None
    ),
    "linear_svc": lambda: LinearSVC(C=1.0, class_weight="balanced"),
    "linear_svc_calibrated": lambda: CalibratedClassifierCV(
        estimator=LinearSVC(C=1.0, class_weight="balanced"),
        method="sigmoid",
        cv=2,
    ),
    "random_forest": lambda: RandomForestClassifier(
        n_estimators=300, class_weight="balanced", n_jobs=-1, random_state=42
    ),
}
