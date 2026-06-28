"""Transaction service facade used by FastAPI routers."""
from finance.transactions.export import CSV_COLUMNS, export_csv_lines, safe_csv_value
from finance.transactions.mutations import (
    UNCHANGED,
    InvalidCategoryAssignment,
    accept_suggestions,
    bulk_categorize,
    bulk_delete,
    delete_transaction,
    reject_suggestions,
    restore_suggestions,
    update_annotations,
    update_category,
    update_transaction_type,
)
from finance.transactions.queries import (
    CategorySummary,
    FilterSummaryResult,
    MerchantGroupSummary,
    TransactionFilters,
    filter_summary,
    filtered_transactions_stmt,
    list_transactions,
    merchant_groups,
    summary_by_category,
)
from finance.transactions.review import review_summary

__all__ = [
    "CSV_COLUMNS",
    "CategorySummary",
    "FilterSummaryResult",
    "InvalidCategoryAssignment",
    "MerchantGroupSummary",
    "TransactionFilters",
    "UNCHANGED",
    "accept_suggestions",
    "bulk_categorize",
    "bulk_delete",
    "delete_transaction",
    "export_csv_lines",
    "filter_summary",
    "filtered_transactions_stmt",
    "list_transactions",
    "merchant_groups",
    "reject_suggestions",
    "restore_suggestions",
    "review_summary",
    "safe_csv_value",
    "summary_by_category",
    "update_annotations",
    "update_category",
    "update_transaction_type",
]
