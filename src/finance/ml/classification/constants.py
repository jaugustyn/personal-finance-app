"""Shared constants for category-classification runtime and evidence code."""
from __future__ import annotations

from pathlib import Path

REPORTS_DIR = Path("data/reports")

DEFAULT_ACCEPT_THRESHOLD = 0.55
DEFAULT_REVIEW_FLOOR = 0.25
OTHER_CATEGORY = "other"

MINIMUM_LABELLED_ROWS = 300
MODEL_MIN_CLASS_SUPPORT = 10
RECOMMENDED_LABELLED_ROWS = 800
IDEAL_LABELLED_ROWS = 2000
# Class balance remains diagnostic. Technical readiness is gated by total labels;
# the evaluator separately enforces only the support mathematically required by CV.
RECOMMENDED_PER_CATEGORY = 50
STRONG_PER_CATEGORY = 100

CONFIDENCE_RECOMMENDATION_THRESHOLD = DEFAULT_ACCEPT_THRESHOLD
RETRAIN_LABEL_GROWTH_THRESHOLD = 0.20
RETRAIN_FEEDBACK_EVENTS_THRESHOLD = 25
RETRAIN_REJECTION_RATE_THRESHOLD = 0.35
RETRAIN_REJECTION_MIN_EVENTS = 10
