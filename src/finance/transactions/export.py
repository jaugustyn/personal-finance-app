"""CSV export helpers for transactions."""
from __future__ import annotations

import csv
import io
from collections.abc import Iterator

from sqlalchemy.orm import Session

from finance.transactions.queries import filtered_transactions_stmt, matching_transactions
from finance.transactions.types import TransactionFilters

CSV_COLUMNS = [
    "id",
    "booking_date",
    "amount",
    "currency",
    "direction",
    "merchant",
    "title",
    "category",
    "category_source",
    "category_predicted",
    "category_confidence",
    "category_predicted_source",
    "category_suggestion_rejected",
    "transaction_type",
    "source",
    "is_transfer",
    "import_id",
]

_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def safe_csv_value(value: object) -> object:
    if isinstance(value, str) and value and value[0] in _DANGEROUS_PREFIXES:
        return "'" + value
    return value


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
        else session.execute(filtered_transactions_stmt(filters)).scalars()
    )
    for tx in rows:
        writer.writerow([safe_csv_value(getattr(tx, c)) for c in CSV_COLUMNS])
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
