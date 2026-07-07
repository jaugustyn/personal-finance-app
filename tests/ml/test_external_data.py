from __future__ import annotations

import pandas as pd

from finance.domain.enums import TransactionDirection, TransactionType
from finance.ml.classification.external import (
    KAGGLE_PERSONAL_FINANCE_SOURCE,
    load_kaggle_personal_finance,
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
