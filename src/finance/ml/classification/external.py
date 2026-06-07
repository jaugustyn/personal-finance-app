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


# --- HuggingFace mitulshah/transaction-categorization integration ---
# English, machine-generated dataset used as a TEXT-ONLY benchmark only. It never
# replaces real manually confirmed Polish labels and has no amount/date columns.
HF_TRANSACTION_SOURCE = "external_hf_transaction_categorization"

# Strict mapping: only unambiguous classes survive; everything else is dropped on
# purpose ("better to drop than to poison training"). HF has no clean source for
# our ``subscriptions`` or ``savings`` classes, so those stay real-data only.
HF_CATEGORY_MAP: dict[str, str] = {
    "Food & Dining": Category.FOOD.value,
    "Transportation": Category.TRANSPORT.value,
    "Healthcare & Medical": Category.HEALTH.value,
    "Entertainment & Recreation": Category.ENTERTAINMENT.value,
    "Utilities & Services": Category.HOUSING.value,
    "Shopping & Retail": Category.SHOPPING.value,
    # Dropped: Financial Services, Income, Government & Legal, Charity & Donations.
}

HF_REQUIRED_COLUMNS = {"transaction_description", "category"}


def map_hf_category(raw_category: str | None) -> str | None:
    """Map HF classes to the thesis expense-category taxonomy."""
    if raw_category is None:
        return None
    return HF_CATEGORY_MAP.get(str(raw_category).strip())


def _read_parquet(path: str | Path) -> pd.DataFrame:
    try:
        return pd.read_parquet(path)
    except ImportError as exc:  # no pyarrow/fastparquet engine installed
        raise ImportError(
            "Reading the HF parquet requires a parquet engine. Install it with "
            "`pip install -e \".[experiments]\"` or `pip install pyarrow`."
        ) from exc


def load_hf_transaction_categorization(
    path: str | Path,
    *,
    per_class: int = 2000,
    seed: int = 42,
    countries: list[str] | None = None,
) -> pd.DataFrame:
    """Load HF parquet as classifier-ready rows.

    HF has no amount/date, so ``abs_amount`` and ``day_of_week`` are NaN — these
    rows are only usable with the text-only pipeline. Unmapped categories are
    dropped. Each kept class is stratified-subsampled to at most ``per_class``
    rows with a fixed ``seed`` for reproducibility.

    Returned columns: text, abs_amount (NaN), day_of_week (NaN), category,
    merchant, title, source, country, currency, raw_category.
    """
    df = _read_parquet(path)
    missing = HF_REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"HF parquet missing columns: {sorted(missing)}")
    if countries is not None:
        df = df[df["country"].isin(countries)]

    raw_category = df["category"].fillna("").astype(str).str.strip()
    description = df["transaction_description"].fillna("").astype(str).str.strip()
    df = df.assign(
        text=description,
        abs_amount=float("nan"),
        day_of_week=float("nan"),
        category=raw_category.map(map_hf_category),
        merchant=description,
        title="",
        source=HF_TRANSACTION_SOURCE,
        country=df["country"] if "country" in df.columns else "",
        currency=df["currency"] if "currency" in df.columns else "",
        raw_category=raw_category,
    )
    df = df[df["category"].notna() & (df["text"].str.len() > 0)]

    groups = [
        group.sample(n=per_class, random_state=seed)
        if len(group) > per_class
        else group
        for _, group in df.groupby("category", sort=True)
    ]
    cols = [
        "text",
        "abs_amount",
        "day_of_week",
        "category",
        "merchant",
        "title",
        "source",
        "country",
        "currency",
        "raw_category",
    ]
    out = pd.concat(groups, ignore_index=True) if groups else df.iloc[0:0]
    return out[cols].reset_index(drop=True)


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
        return TransactionType.SAVINGS_INVESTMENT.value
    return (
        TransactionType.PURCHASE.value
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
