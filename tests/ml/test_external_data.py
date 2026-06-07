from __future__ import annotations

import pandas as pd

from finance.domain.enums import TransactionDirection, TransactionType
from finance.ml.classification import external
from finance.ml.classification.external import (
    HF_TRANSACTION_SOURCE,
    KAGGLE_PERSONAL_FINANCE_SOURCE,
    load_hf_transaction_categorization,
    load_kaggle_personal_finance,
    map_hf_category,
    map_kaggle_personal_finance_category,
)


def test_kaggle_category_mapping() -> None:
    assert map_kaggle_personal_finance_category("Food & Drink") == "food"
    assert map_kaggle_personal_finance_category("Travel") == "transport"
    assert map_kaggle_personal_finance_category("Rent") == "housing"
    assert map_kaggle_personal_finance_category("Shopping") == "shopping"
    assert map_kaggle_personal_finance_category("Salary") is None
    assert map_kaggle_personal_finance_category("Unknown") is None


def test_load_kaggle_personal_finance_maps_to_classifier_schema(tmp_path) -> None:
    csv_path = tmp_path / "Personal_Finance_Dataset.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Date,Transaction Description,Category,Amount,Type",
                "2024-01-01,Grocery Store,Food & Drink,42.50,Expense",
                "2024-01-02,Monthly Rent,Rent,1500,Expense",
                "2024-01-03,Salary Payment,Salary,5000,Income",
                "2024-01-04,Broker Transfer,Investment,200,Expense",
                "2024-01-05,Misc Income,Other,300,Income",
            ]
        ),
        encoding="utf-8",
    )

    df = load_kaggle_personal_finance(csv_path)

    assert list(df["category"]) == ["food", "housing", "savings"]
    assert set(df["source"]) == {KAGGLE_PERSONAL_FINANCE_SOURCE}
    assert set(df["direction"]) == {TransactionDirection.DEBIT.value}
    assert list(df["transaction_type"]) == [
        TransactionType.PURCHASE.value,
        TransactionType.PURCHASE.value,
        TransactionType.SAVINGS_INVESTMENT.value,
    ]
    assert set(["text", "abs_amount", "day_of_week", "category"]).issubset(df.columns)
    assert df["abs_amount"].tolist() == [42.5, 1500.0, 200.0]


def test_load_kaggle_personal_finance_can_keep_unlabelled_type_rows(tmp_path) -> None:
    csv_path = tmp_path / "Personal_Finance_Dataset.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Date,Transaction Description,Category,Amount,Type",
                "2024-01-03,Salary Payment,Salary,5000,Income",
            ]
        ),
        encoding="utf-8",
    )

    df = load_kaggle_personal_finance(csv_path, include_unlabelled=True)

    assert len(df) == 1
    assert pd.isna(df.iloc[0]["category"])
    assert df.iloc[0]["direction"] == TransactionDirection.CREDIT.value
    assert df.iloc[0]["transaction_type"] == TransactionType.SALARY.value


def test_hf_category_mapping_is_strict() -> None:
    assert map_hf_category("Food & Dining") == "food"
    assert map_hf_category("Transportation") == "transport"
    assert map_hf_category("Healthcare & Medical") == "health"
    assert map_hf_category("Shopping & Retail") == "shopping"
    # Unsupported classes are dropped on purpose.
    assert map_hf_category("Income") is None
    assert map_hf_category(None) is None


def test_load_hf_drops_unmapped_and_subsamples(monkeypatch) -> None:
    raw = pd.DataFrame(
        {
            "transaction_description": [
                "UBER TRIP", "LYFT RIDE", "BOLT RIDE",  # transport
                "MCDONALDS", "STARBUCKS",               # food
                "AMAZON ORDER",                         # shopping
                "",                                     # empty text -> dropped
            ],
            "category": [
                "Transportation", "Transportation", "Transportation",
                "Food & Dining", "Food & Dining",
                "Shopping & Retail",
                "Food & Dining",
            ],
            "country": ["US"] * 7,
            "currency": ["USD"] * 7,
        }
    )
    monkeypatch.setattr(external, "_read_parquet", lambda _: raw)

    df = load_hf_transaction_categorization("ignored.parquet", per_class=2, seed=0)

    assert set(df["category"]) == {"transport", "food", "shopping"}
    assert (df["category"] == "transport").sum() == 2  # subsampled from 3
    assert (df["category"] == "food").sum() == 2
    assert (df["category"] == "shopping").sum() == 1
    assert set(df["source"]) == {HF_TRANSACTION_SOURCE}
    # HF has no amount/date -> NaN, only usable text-only.
    assert df["abs_amount"].isna().all()
    assert df["day_of_week"].isna().all()
    assert (df["text"].str.len() > 0).all()


def test_load_hf_missing_columns_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        external, "_read_parquet", lambda _: pd.DataFrame({"category": ["Food & Dining"]})
    )
    try:
        load_hf_transaction_categorization("ignored.parquet")
    except ValueError as exc:
        assert "transaction_description" in str(exc)
    else:  # pragma: no cover - guard
        raise AssertionError("expected ValueError for missing columns")
