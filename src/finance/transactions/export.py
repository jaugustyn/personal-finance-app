"""CSV export helpers for transactions."""
from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterator

from sqlalchemy.orm import Session, selectinload

from finance.domain.models import Transaction
from finance.transactions.queries import filtered_transactions_stmt, matching_transactions
from finance.transactions.types import TransactionFilters

CSV_COLUMNS = [
    "id",
    "account_id",
    "account_name",
    "booking_date",
    "booking_datetime",
    "amount",
    "currency",
    "amount_base",
    "base_currency",
    "fx_rate",
    "fx_rate_date",
    "fx_rate_source",
    "direction",
    "merchant",
    "title",
    "raw_category",
    "raw_transaction_type",
    "category",
    "subcategory",
    "category_source",
    "category_confirmation_method",
    "category_confirmed_at",
    "category_origin_ref",
    "category_predicted",
    "category_confidence",
    "category_predicted_source",
    "category_predicted_ref",
    "category_suggestion_rejected",
    "transaction_type",
    "transaction_type_source",
    "transaction_type_confirmation_method",
    "transaction_type_confirmed_at",
    "transaction_type_origin_ref",
    "transaction_type_predicted",
    "transaction_type_confidence",
    "transaction_type_predicted_source",
    "transaction_type_predicted_ref",
    "source",
    "external_id",
    "is_transfer",
    "notes",
    "tags",
    "import_id",
]

_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_csv_value(value: object) -> object:
    if isinstance(value, str) and value and value[0] in _DANGEROUS_PREFIXES:
        return "'" + value
    return value


def _column_value(transaction: object, column: str) -> object:
    value = getattr(transaction, column)
    if column == "tags":
        value = json.dumps(value or [], ensure_ascii=False, separators=(",", ":"))
    return safe_csv_value(value)


def export_csv_lines(session: Session, filters: TransactionFilters) -> Iterator[str]:
    """Stream matching transactions as CSV lines with formula injection escaping."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    yield buf.getvalue()
    buf.seek(0)
    buf.truncate(0)
    rows = (
        matching_transactions(session, filters)
        if filters.merchant_canonical_key
        else session.execute(
            filtered_transactions_stmt(filters).options(selectinload(Transaction.account))
        ).scalars()
    )
    for tx in rows:
        writer.writerow([_column_value(tx, column) for column in CSV_COLUMNS])
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
