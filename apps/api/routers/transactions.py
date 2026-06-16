"""GET endpoints for transactions: listing and basic aggregations."""
from datetime import date
from decimal import Decimal
from typing import Any, Literal

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
    subcategory: str | None = None
    category_source: str | None = None
    category_predicted: str | None
    category_confidence: float | None
    category_predicted_source: str | None = None
    category_suggestion_rejected: bool = False
    transaction_type: str = "purchase"
    source: str
    is_transfer: bool = False
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
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
    search: str | None = None,
    direction: Literal["debit", "credit"] | None = None,
    category: str | None = None,
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
        search=search,
        direction=direction,
        category=category,
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
    search: str | None = None,
    direction: Literal["debit", "credit"] | None = None,
    category: str | None = None,
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
        search=search,
        direction=direction,
        category=category,
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


class ReviewCounts(BaseModel):
    uncategorized: int
    no_suggestion: int
    low_confidence: int
    ready_to_accept: int
    rejected: int
    categorized: int


class RareClass(BaseModel):
    category: str
    count: int


class RecurringMerchant(BaseModel):
    merchant: str
    count: int


class ReviewSummary(BaseModel):
    counts: ReviewCounts
    rare_classes: list[RareClass]
    recurring_unruled: list[RecurringMerchant]
    feedback_quality: dict[str, Any] = Field(default_factory=dict)
    confusion_hotspots: list[dict[str, Any]] = Field(default_factory=list)
    anomaly_feedback: dict[str, Any] = Field(default_factory=dict)
    subscription_feedback: dict[str, Any] = Field(default_factory=dict)
    confidence_threshold: float
    rare_class_threshold: int


@router.get("/review-summary", response_model=ReviewSummary)
def review_summary(
    session: Session = Depends(get_session),
    rare_class_threshold: int = Query(default=40, ge=1, le=1000),
    recurring_min_count: int = Query(default=3, ge=1, le=100),
    recurring_limit: int = Query(default=10, ge=1, le=100),
) -> ReviewSummary:
    """Data-quality buckets that most improve ML training data (Review Center)."""
    data = tx_service.review_summary(
        session,
        rare_class_threshold=rare_class_threshold,
        recurring_min_count=recurring_min_count,
        recurring_limit=recurring_limit,
    )
    return ReviewSummary(
        counts=ReviewCounts(**data["counts"].__dict__),
        rare_classes=[RareClass(**r.__dict__) for r in data["rare_classes"]],
        recurring_unruled=[
            RecurringMerchant(**r.__dict__) for r in data["recurring_unruled"]
        ],
        feedback_quality=data["feedback_quality"],
        confusion_hotspots=data["confusion_hotspots"],
        anomaly_feedback=data["anomaly_feedback"],
        subscription_feedback=data["subscription_feedback"],
        confidence_threshold=data["confidence_threshold"],
        rare_class_threshold=data["rare_class_threshold"],
    )


class CategoryUpdate(BaseModel):
    category: str | None  # None clears the manual label.
    subcategory: str | None = None  # optional refinement within the group.
    remember_rule: bool = False


@router.patch("/{tx_id}/category", response_model=TransactionRow)
def update_category(
    tx_id: int,
    payload: CategoryUpdate,
    session: Session = Depends(get_session),
) -> TransactionRow:
    """Manual override of a transaction category (active learning)."""
    try:
        tx = tx_service.update_category(
            session,
            tx_id,
            payload.category,
            subcategory=payload.subcategory,
            remember_rule=payload.remember_rule,
        )
    except tx_service.InvalidCategoryAssignment as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return TransactionRow.model_validate(tx)


class TypeUpdate(BaseModel):
    transaction_type: str


@router.patch("/{tx_id}/type", response_model=TransactionRow)
def update_type(
    tx_id: int,
    payload: TypeUpdate,
    session: Session = Depends(get_session),
) -> TransactionRow:
    """Manual override of a transaction type (e.g. mark a personal transfer)."""
    tx = tx_service.update_transaction_type(
        session, tx_id, payload.transaction_type
    )
    if tx is None:
        raise HTTPException(
            status_code=404, detail="Transaction not found or invalid type"
        )
    return TransactionRow.model_validate(tx)


class AnnotationUpdate(BaseModel):
    notes: str | None = None  # omitted leaves unchanged; null/empty clears
    tags: list[str] | None = None  # None leaves tags unchanged


@router.patch("/{tx_id}/annotations", response_model=TransactionRow)
def update_annotations(
    tx_id: int,
    payload: AnnotationUpdate,
    session: Session = Depends(get_session),
) -> TransactionRow:
    """Set user notes and/or tags on a transaction (curation metadata)."""
    fields = payload.model_fields_set
    tx = tx_service.update_annotations(
        session,
        tx_id,
        notes=payload.notes if "notes" in fields else tx_service.UNCHANGED,
        tags=payload.tags if "tags" in fields else tx_service.UNCHANGED,
    )
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return TransactionRow.model_validate(tx)


class BulkCategorize(BaseModel):
    ids: list[int] | None = None
    merchant: str | None = None
    category: str | None = None  # explicit null clears
    mark_transfer: bool | None = None
    transaction_type: str | None = None


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
    try:
        affected = tx_service.bulk_categorize(
            session,
            ids=payload.ids,
            merchant=payload.merchant,
            category=(
                payload.category
                if "category" in payload.model_fields_set
                else tx_service.UNCHANGED
            ),
            mark_transfer=payload.mark_transfer,
            transaction_type=payload.transaction_type,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="Invalid transaction type.",
        ) from exc
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


@router.post("/bulk/restore-suggestions", response_model=BulkResult)
def restore_suggestions(
    payload: RejectSuggestions,
    session: Session = Depends(get_session),
) -> BulkResult:
    affected = tx_service.restore_suggestions(session, ids=payload.ids)
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
