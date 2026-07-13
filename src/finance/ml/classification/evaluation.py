"""Gold-label filtering and readiness summaries for category classification."""
from __future__ import annotations

import pandas as pd

from finance.analytics.filters import expense_category_candidate_mask
from finance.domain.enums import (
    CATEGORY_CONFIRMATION_METHOD_VALUES,
    CATEGORY_VALUES,
    Category,
)
from finance.ml.classification.constants import (
    IDEAL_LABELLED_ROWS,
    MINIMUM_LABELLED_ROWS,
    RECOMMENDED_LABELLED_ROWS,
    RECOMMENDED_PER_CATEGORY,
    STRONG_PER_CATEGORY,
)


def filter_category_training_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Keep confirmed system-category labels for real expense transactions."""
    required = {
        "category",
        "category_confirmation_method",
        "category_confirmed_at",
    }
    if not required.issubset(df.columns):
        return df.iloc[0:0].copy().reset_index(drop=True)
    out = df[df["category"].notna()].copy()
    out = out[out["category"].astype(str).isin(CATEGORY_VALUES)]
    out = out[
        out["category_confirmation_method"].isin(CATEGORY_CONFIRMATION_METHOD_VALUES)
        & out["category_confirmed_at"].notna()
    ]
    out = out[expense_category_candidate_mask(out)]
    return out.reset_index(drop=True)


def build_label_readiness(df: pd.DataFrame) -> dict[str, object]:
    """Summarise gold-label volume; split feasibility is reported separately."""
    labelled = filter_category_training_rows(df)
    counts = (
        labelled["category"].astype(str).value_counts().to_dict()
        if not labelled.empty
        else {}
    )
    category_counts = {
        category.value: int(counts.get(category.value, 0)) for category in Category
    }
    total = int(len(labelled))
    below_recommended = [
        category
        for category, count in category_counts.items()
        if count < RECOMMENDED_PER_CATEGORY
    ]

    date_span_months = None
    date_span_days = 0
    calendar_months = 0
    if "booking_date" in labelled.columns and not labelled.empty:
        dates = pd.to_datetime(labelled["booking_date"], errors="coerce").dropna()
        if not dates.empty:
            calendar_months = int(dates.dt.to_period("M").nunique())
            date_span_days = int((dates.max() - dates.min()).days) if len(dates) > 1 else 0
            date_span_months = int(
                (dates.max().year - dates.min().year) * 12
                + dates.max().month
                - dates.min().month
                + 1
            )

    technical_ready = total >= MINIMUM_LABELLED_ROWS
    thesis_data_ready = (
        total >= RECOMMENDED_LABELLED_ROWS
        and not below_recommended
        and calendar_months >= 12
        and date_span_days >= 365
    )
    level = (
        "thesis_data_ready"
        if thesis_data_ready
        else "technical_ready"
        if technical_ready
        else "insufficient"
    )
    return {
        "level": level,
        "total_labelled": total,
        "minimum_total": MINIMUM_LABELLED_ROWS,
        "recommended_total": RECOMMENDED_LABELLED_ROWS,
        "ideal_total": IDEAL_LABELLED_ROWS,
        "minimum_per_category": 0,
        "recommended_per_category": RECOMMENDED_PER_CATEGORY,
        "strong_per_category": STRONG_PER_CATEGORY,
        "category_counts": category_counts,
        "below_minimum_per_category": [],
        "below_recommended_per_category": below_recommended,
        "date_span_months": date_span_months,
        "calendar_months": calendar_months,
        "date_span_days": date_span_days,
        "technical_ready": technical_ready,
        "thesis_data_ready": thesis_data_ready,
        "recommended_history_months": "12+",
        "training_labels_source": (
            "manual or accepted_suggestion expense categories with confirmation date"
        ),
        "category_predicted_is_ground_truth": False,
        "language_note": (
            "Real Polish bank labels are the primary quality signal; external "
            "datasets remain separate experiments."
        ),
        "next_review_priority": [
            "unlabelled expense-like rows",
            "low-confidence suggestions",
            "classes below model support",
            "frequent merchants with repeated mistakes",
        ],
    }
