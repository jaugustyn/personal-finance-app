from __future__ import annotations

import pandas as pd

from finance.analytics.filters import (
    expense_category_candidate_mask,
    is_expense_category_candidate,
)


def test_expense_category_candidate_mask_matches_runtime_semantics() -> None:
    df = pd.DataFrame(
        {
            "direction": [
                "debit",
                "credit",
                "debit",
                "debit",
                "debit",
                "debit",
                "debit",
                "debit",
            ],
            "is_transfer": [False, False, True, "false", False, False, False, False],
            "transaction_type": [
                "expense",
                "expense",
                "expense",
                "expense",
                "own_transfer",
                "refund",
                "expense",
                "asset_allocation",
            ],
        }
    )

    mask = expense_category_candidate_mask(df).tolist()

    assert mask == [True, False, False, True, False, False, True, False]


def test_is_expense_category_candidate_treats_false_string_as_not_transfer() -> None:
    assert is_expense_category_candidate("debit", "false", "expense")
    assert not is_expense_category_candidate("debit", "true", "expense")


def test_expense_category_candidate_mask_handles_training_frames_without_direction() -> None:
    df = pd.DataFrame(
        {
            "is_transfer": [False, True],
            "transaction_type": ["expense", "expense"],
        }
    )

    assert expense_category_candidate_mask(df).tolist() == [True, False]
