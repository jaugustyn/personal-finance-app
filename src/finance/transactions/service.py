"""Transaction service facade used by FastAPI routers."""
from finance.transactions.export import CSV_COLUMNS, export_csv_lines, safe_csv_value
from finance.transactions.mutations import (
    accept_suggestions,
    bulk_categorize,
    bulk_delete,
    delete_transaction,
    reject_suggestions,
    update_category,
)
from finance.transactions.queries import (
    CategorySummary,
    MerchantGroupSummary,
    TransactionFilters,
    filtered_transactions_stmt,
    list_transactions,
    merchant_groups,
    summary_by_category,
)

__all__ = [
    "CSV_COLUMNS",
    "CategorySummary",
    "MerchantGroupSummary",
    "TransactionFilters",
    "accept_suggestions",
    "bulk_categorize",
    "bulk_delete",
    "delete_transaction",
    "export_csv_lines",
    "filtered_transactions_stmt",
    "list_transactions",
    "merchant_groups",
    "reject_suggestions",
    "safe_csv_value",
    "summary_by_category",
    "update_category",
]
