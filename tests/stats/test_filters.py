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
                "purchase",
                "purchase",
                "purchase",
                "purchase",
                "own_transfer",
                "refund",
                "bank_fee",
                "savings_investment",
            ],
        }
    )

    mask = expense_category_candidate_mask(df).tolist()

    assert mask == [True, False, False, True, False, False, True, True]


def test_is_expense_category_candidate_treats_false_string_as_not_transfer() -> None:
    assert is_expense_category_candidate("debit", "false", "purchase")
    assert not is_expense_category_candidate("debit", "true", "purchase")


def test_expense_category_candidate_mask_handles_training_frames_without_direction() -> None:
    df = pd.DataFrame(
        {
            "is_transfer": [False, True],
            "transaction_type": ["purchase", "purchase"],
        }
    )

    assert expense_category_candidate_mask(df).tolist() == [True, False]
