"""Load public external datasets into the local classification schema.

External datasets are used for experiments and benchmarks only. They should not
silently become ground truth for the user's real transactions.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from finance.domain.enums import Category, TransactionDirection, TransactionType

KAGGLE_PERSONAL_FINANCE_SOURCE = "external_kaggle_personal_finance"

KAGGLE_PERSONAL_FINANCE_CATEGORY_MAP: dict[str, str | None] = {
    "Food & Drink": Category.FOOD.value,
    "Travel": Category.TRANSPORT.value,
    "Health & Fitness": Category.HEALTH.value,
    "Entertainment": Category.ENTERTAINMENT.value,
    "Rent": Category.HOUSING.value,
    "Utilities": Category.HOUSING.value,
    "Investment": Category.SAVINGS.value,
    "Shopping": Category.SHOPPING.value,
    "Other": Category.OTHER.value,
    "Salary": None,
}

KAGGLE_REQUIRED_COLUMNS = {
    "Date",
    "Transaction Description",
    "Category",
    "Amount",
    "Type",
}


def map_kaggle_personal_finance_category(raw_category: str | None) -> str | None:
    """Map Kaggle's synthetic category labels to the thesis expense taxonomy."""
    if raw_category is None:
        return None
    return KAGGLE_PERSONAL_FINANCE_CATEGORY_MAP.get(str(raw_category).strip())


def infer_kaggle_transaction_type(raw_category: str | None, tx_type: str | None) -> str:
    category = str(raw_category or "").strip()
    kind = str(tx_type or "").strip().lower()
    if category == "Salary" or (kind == "income" and category.lower() == "salary"):
        return TransactionType.SALARY.value
    if category == "Investment":
        return TransactionType.ASSET_ALLOCATION.value
    return (
        TransactionType.EXPENSE.value
        if kind == "expense"
        else TransactionType.OTHER.value
    )


def load_kaggle_personal_finance(
    path: str | Path,
    *,
    include_unlabelled: bool = False,
) -> pd.DataFrame:
    """Load Kaggle ``Personal_Finance_Dataset.csv`` as classifier-ready rows.

    Returned columns match ``finance.ml.classification.dataset.load_training_set``:
    ``text``, ``abs_amount``, ``day_of_week``, ``category`` and metadata used by
    feature-v2/evidence. Salary rows are kept only when ``include_unlabelled`` is
    true, because they are transaction-type examples rather than expense-category
    labels.
    """
    raw = pd.read_csv(path)
    missing = KAGGLE_REQUIRED_COLUMNS - set(raw.columns)
    if missing:
        raise ValueError(
            f"Kaggle personal finance CSV missing columns: {sorted(missing)}"
        )

    booking_date = pd.to_datetime(raw["Date"], errors="coerce")
    amount = pd.to_numeric(raw["Amount"], errors="coerce")
    description = raw["Transaction Description"].fillna("").astype(str).str.strip()
    raw_category = raw["Category"].fillna("").astype(str).str.strip()
    raw_type = raw["Type"].fillna("").astype(str).str.strip()
    category = raw_category.map(map_kaggle_personal_finance_category)
    income_non_investment = (raw_type.str.lower() == "income") & (
        raw_category != "Investment"
    )
    category = category.mask(income_non_investment)

    out = pd.DataFrame(
        {
            "text": description,
            "abs_amount": amount.abs(),
            "day_of_week": booking_date.dt.weekday,
            "category": category,
            "merchant": description,
            "title": "",
            "source": KAGGLE_PERSONAL_FINANCE_SOURCE,
            "booking_date": booking_date.dt.date,
            "raw_category": raw_category,
            "direction": raw_type.str.lower().map(
                {
                    "income": TransactionDirection.CREDIT.value,
                    "expense": TransactionDirection.DEBIT.value,
                }
            ),
            "is_transfer": False,
            "transaction_type": [
                infer_kaggle_transaction_type(category, kind)
                for category, kind in zip(raw_category, raw_type, strict=False)
            ],
        }
    )
    out = out.dropna(subset=["booking_date", "abs_amount", "day_of_week"])
    out = out[out["text"].str.len() > 0]
    if not include_unlabelled:
        out = out[out["category"].notna()]
    return out.reset_index(drop=True)
