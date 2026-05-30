"""GET endpoints for transactions: listing and basic aggregations."""
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from finance.db import get_session
from finance.transactions import service as tx_service

router = APIRouter(prefix="/transactions", tags=["transactions"])


class TransactionRow(BaseModel):
    id: int
    booking_date: date
    amount: Decimal
    currency: str
    direction: str
    merchant: str
    title: str
    category: str | None
    category_source: str | None = None
    category_predicted: str | None
    category_confidence: float | None
    category_predicted_source: str | None = None
    category_suggestion_rejected: bool = False
    transaction_type: str = "purchase"
    source: str
    is_transfer: bool = False
    import_id: int | None = None

    model_config = {"from_attributes": True}


class CategorySum(BaseModel):
    category: str | None
    total_debit: Decimal
    total_credit: Decimal
    count: int


CategoryState = Literal[
    "all",
    "categorized",
    "uncategorized",
    "suggested",
    "needs_review",
    "rejected",
]


@router.get("", response_model=list[TransactionRow])
def list_transactions(
    session: Session = Depends(get_session),
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    date_from: date | None = None,
    date_to: date | None = None,
    include_transfers: bool = Query(default=True),
    import_id: int | None = None,
    merchant: str | None = None,
    category_state: CategoryState = Query(default="all"),
    has_suggestion: bool | None = Query(default=None),
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    max_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    transaction_type: str | None = None,
    review_priority: bool = Query(default=False),
) -> list[TransactionRow]:
    filters = tx_service.TransactionFilters(
        date_from=date_from,
        date_to=date_to,
        include_transfers=include_transfers,
        import_id=import_id,
        merchant=merchant,
        category_state=category_state,
        has_suggestion=has_suggestion,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        transaction_type=transaction_type,
        review_priority=review_priority,
    )
    rows = tx_service.list_transactions(session, filters, limit=limit, offset=offset)
    return [TransactionRow.model_validate(r) for r in rows]


@router.get("/export.csv")
def export_csv(
    session: Session = Depends(get_session),
    date_from: date | None = None,
    date_to: date | None = None,
    include_transfers: bool = Query(default=True),
    import_id: int | None = None,
    merchant: str | None = None,
    category_state: CategoryState = Query(default="all"),
    has_suggestion: bool | None = Query(default=None),
    min_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    max_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    transaction_type: str | None = None,
    review_priority: bool = Query(default=False),
) -> StreamingResponse:
    """Stream all matching transactions as CSV (no row limit)."""
    filters = tx_service.TransactionFilters(
        date_from=date_from,
        date_to=date_to,
        include_transfers=include_transfers,
        import_id=import_id,
        merchant=merchant,
        category_state=category_state,
        has_suggestion=has_suggestion,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        transaction_type=transaction_type,
        review_priority=review_priority,
    )
    headers = {"Content-Disposition": 'attachment; filename="transactions.csv"'}
    return StreamingResponse(
        tx_service.export_csv_lines(session, filters),
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )


@router.get("/summary/by-category", response_model=list[CategorySum])
def summary_by_category(
    session: Session = Depends(get_session),
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[CategorySum]:
    rows = tx_service.summary_by_category(session, date_from=date_from, date_to=date_to)
    return [
        CategorySum(
            category=r.category,
            total_debit=r.total_debit,
            total_credit=r.total_credit,
            count=r.count,
        )
        for r in rows
    ]


class MerchantGroup(BaseModel):
    merchant: str
    count: int
    total_debit: Decimal
    total_credit: Decimal
    common_category: str | None
    sample_titles: list[str]


@router.get("/groups", response_model=list[MerchantGroup])
def merchant_groups(
    session: Session = Depends(get_session),
    only_uncategorized: bool = Query(default=True),
    min_count: int = Query(default=2, ge=1, le=100),
    limit: int = Query(default=50, le=500),
) -> list[MerchantGroup]:
    """Group transactions by merchant for bulk categorisation.

    Returned groups are sorted by ``count`` descending so the user sees the
    biggest savings first when bulk-assigning categories.
    """
    rows = tx_service.merchant_groups(
        session,
        only_uncategorized=only_uncategorized,
        min_count=min_count,
        limit=limit,
    )
    return [MerchantGroup(**r.__dict__) for r in rows]


class CategoryUpdate(BaseModel):
    category: str | None  # None clears the manual label.
    remember_rule: bool = False


@router.patch("/{tx_id}/category", response_model=TransactionRow)
def update_category(
    tx_id: int,
    payload: CategoryUpdate,
    session: Session = Depends(get_session),
) -> TransactionRow:
    """Manual override of a transaction category (active learning)."""
    tx = tx_service.update_category(
        session,
        tx_id,
        payload.category,
        remember_rule=payload.remember_rule,
    )
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return TransactionRow.model_validate(tx)


class BulkCategorize(BaseModel):
    ids: list[int] | None = None
    merchant: str | None = None
    category: str | None  # None clears
    mark_transfer: bool | None = None


class BulkResult(BaseModel):
    affected: int


@router.post("/bulk/categorize", response_model=BulkResult)
def bulk_categorize(
    payload: BulkCategorize, session: Session = Depends(get_session)
) -> BulkResult:
    """Apply a category (and/or transfer flag) to many transactions at once.

    Selection by ``ids`` and/or ``merchant`` (combined with AND when both set).
    """
    if not payload.ids and not payload.merchant:
        raise HTTPException(
            status_code=422, detail="Provide ids or merchant for bulk update."
        )
    affected = tx_service.bulk_categorize(
        session,
        ids=payload.ids,
        merchant=payload.merchant,
        category=payload.category,
        mark_transfer=payload.mark_transfer,
    )
    return BulkResult(affected=affected)


class AcceptSuggestions(BaseModel):
    ids: list[int] | None = None
    min_confidence: float = Field(default=0.75, ge=0.0, le=1.0)


class RejectSuggestions(BaseModel):
    ids: list[int] | None = None


@router.post("/bulk/accept-suggestions", response_model=BulkResult)
def accept_suggestions(
    payload: AcceptSuggestions,
    session: Session = Depends(get_session),
) -> BulkResult:
    affected = tx_service.accept_suggestions(
        session,
        ids=payload.ids,
        min_confidence=payload.min_confidence,
    )
    return BulkResult(affected=affected)


@router.post("/bulk/reject-suggestions", response_model=BulkResult)
def reject_suggestions(
    payload: RejectSuggestions,
    session: Session = Depends(get_session),
) -> BulkResult:
    affected = tx_service.reject_suggestions(session, ids=payload.ids)
    return BulkResult(affected=affected)


class BulkDelete(BaseModel):
    ids: list[int] = Field(default_factory=list)


@router.post("/bulk/delete", response_model=BulkResult)
def bulk_delete(
    payload: BulkDelete, session: Session = Depends(get_session)
) -> BulkResult:
    return BulkResult(affected=tx_service.bulk_delete(session, payload.ids))


@router.delete("/{tx_id}", status_code=204)
def delete_transaction(
    tx_id: int, session: Session = Depends(get_session)
) -> None:
    deleted = tx_service.delete_transaction(session, tx_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Transaction not found")

