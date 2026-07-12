"""GET endpoints for transactions: listing and basic aggregations."""
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from apps.api.dependencies.transactions import TransactionFilterParams, enum_value
from apps.api.errors import conflict, not_found, validation_error
from apps.api.schemas.transactions import (
    AcceptSuggestions,
    AnnotationUpdate,
    BulkCategorize,
    BulkDelete,
    BulkResult,
    CategorySum,
    CategoryUpdate,
    ClassificationDecisionResponse,
    FilterSummaryResponse,
    MerchantGroup,
    RareClass,
    RecurringMerchant,
    RejectSuggestions,
    ReviewCounts,
    ReviewSummary,
    TransactionRow,
    TypeUpdate,
)
from finance.db import get_session
from finance.ml.classification.policy import (
    ClassificationPolicy,
    decide_classification,
)
from finance.ml.classification.predict import active_classification_policy
from finance.transactions import service as tx_service
from finance.transactions.merchants import load_merchant_alias_maps, merchant_identity
from finance.transactions.type_decision import (
    effective_transaction_type,
    transaction_type_is_provisional,
    transaction_type_needs_review,
)
from finance.transactions.type_service import TransactionTypeService

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _classification_policy(session: Session) -> ClassificationPolicy:
    return active_classification_policy(session=session)


def _classification_decision(tx: Any, policy: ClassificationPolicy):
    return decide_classification(
        category=tx.category_predicted,
        confidence=tx.category_confidence,
        direction=tx.direction,
        is_transfer=tx.is_transfer,
        transaction_type=effective_transaction_type(tx),
        policy=policy,
    )


def _transaction_row(
    tx: Any,
    policy: ClassificationPolicy,
    *,
    alias_map: dict[str, str] | None = None,
    label_map: dict[str, str] | None = None,
) -> TransactionRow:
    row = TransactionRow.model_validate(tx)
    identity = merchant_identity(
        tx.merchant,
        tx.title,
        alias_map=alias_map,
        label_map=label_map,
    )
    row.merchant_raw = tx.merchant
    row.merchant_display = identity.display_label
    row.merchant_canonical_key = identity.canonical_key or None
    row.merchant_alias_key = identity.alias_key or None
    row.transaction_type_effective = effective_transaction_type(tx)
    row.transaction_type_is_provisional = transaction_type_is_provisional(tx)
    row.transaction_type_needs_review = transaction_type_needs_review(tx)
    row.classification_decision = ClassificationDecisionResponse(
        **_classification_decision(tx, policy).__dict__,
    )
    return row


def _transaction_response(session: Session, tx: Any) -> TransactionRow:
    policy = _classification_policy(session)
    alias_map, label_map = load_merchant_alias_maps(session)
    return _transaction_row(tx, policy, alias_map=alias_map, label_map=label_map)


@router.get("", response_model=list[TransactionRow])
def list_transactions(
    session: Session = Depends(get_session),
    filters: TransactionFilterParams = Depends(),
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
) -> list[TransactionRow]:
    policy = _classification_policy(session)
    rows = tx_service.list_transactions(
        session,
        filters.to_filters(),
        limit=limit,
        offset=offset,
        policy=policy,
    )
    alias_map, label_map = load_merchant_alias_maps(session)
    return [
        _transaction_row(r, policy, alias_map=alias_map, label_map=label_map)
        for r in rows
    ]


@router.get("/export.csv")
def export_csv(
    session: Session = Depends(get_session),
    filters: TransactionFilterParams = Depends(),
) -> StreamingResponse:
    """Stream all matching transactions as CSV (no row limit)."""
    headers = {"Content-Disposition": 'attachment; filename="transactions.csv"'}
    return StreamingResponse(
        tx_service.export_csv_lines(session, filters.to_filters()),
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


@router.get("/filter-summary", response_model=FilterSummaryResponse)
def filter_summary(
    session: Session = Depends(get_session),
    filters: TransactionFilterParams = Depends(),
) -> FilterSummaryResponse:
    """Lightweight count + income/expenses/net for the current filter set."""
    result = tx_service.filter_summary(session, filters.to_filters())
    return FilterSummaryResponse(
        count=result.count,
        total_income=result.total_income,
        total_expenses=result.total_expenses,
        net=result.net,
    )


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


@router.get("/review-summary", response_model=ReviewSummary)
def review_summary(
    session: Session = Depends(get_session),
    rare_class_threshold: int = Query(default=40, ge=1, le=1000),
    recurring_min_count: int = Query(default=3, ge=1, le=100),
    recurring_limit: int = Query(default=10, ge=1, le=100),
) -> ReviewSummary:
    """Data-quality buckets that most improve ML training data (Review Center)."""
    policy = _classification_policy(session)
    data = tx_service.review_summary(
        session,
        policy=policy,
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
        transaction_type_quality=data["transaction_type_quality"],
        confidence_threshold=data["confidence_threshold"],
        rare_class_threshold=data["rare_class_threshold"],
    )


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
        raise validation_error(str(exc)) from exc
    if tx is None:
        raise not_found("Transaction not found")
    return _transaction_response(session, tx)


@router.patch("/{tx_id}/type", response_model=TransactionRow)
def update_type(
    tx_id: int,
    payload: TypeUpdate,
    session: Session = Depends(get_session),
) -> TransactionRow:
    """Manual override of a transaction type (e.g. mark a personal transfer)."""
    try:
        tx = tx_service.update_transaction_type(
            session,
            tx_id,
            payload.transaction_type.value,
            allow_direction_mismatch=payload.allow_direction_mismatch,
        )
    except tx_service.TransactionTypeDirectionMismatch as exc:
        raise conflict(
            {
                "code": "transaction_type_direction_mismatch",
                "message": str(exc),
            }
        ) from exc
    if tx is None:
        raise not_found("Transaction not found or invalid type")
    return _transaction_response(session, tx)


@router.post("/{tx_id}/type-suggestion/accept", response_model=TransactionRow)
def accept_type_suggestion(
    tx_id: int,
    session: Session = Depends(get_session),
) -> TransactionRow:
    tx = TransactionTypeService(session).accept_suggestion(tx_id)
    if tx is None:
        raise not_found("Provisional transaction type not found")
    return _transaction_response(session, tx)


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
        raise not_found("Transaction not found")
    return _transaction_response(session, tx)


@router.post("/bulk/categorize", response_model=BulkResult)
def bulk_categorize(
    payload: BulkCategorize, session: Session = Depends(get_session)
) -> BulkResult:
    """Apply a category (and/or transfer flag) to many transactions at once.

    Selection by ``ids`` and/or ``merchant`` (combined with AND when both set).
    """
    if not payload.ids and not payload.merchant and not payload.merchant_canonical_key:
        raise validation_error(
            "Provide ids, merchant or merchant_canonical_key for bulk update."
        )
    try:
        affected = tx_service.bulk_categorize(
            session,
            ids=payload.ids,
            merchant=payload.merchant,
            merchant_canonical_key=payload.merchant_canonical_key,
            category=(
                payload.category
                if "category" in payload.model_fields_set
                else tx_service.UNCHANGED
            ),
            mark_transfer=payload.mark_transfer,
            transaction_type=enum_value(payload.transaction_type),
            allow_direction_mismatch=payload.allow_direction_mismatch,
        )
    except tx_service.TransactionTypeDirectionMismatch as exc:
        raise conflict(
            {
                "code": "transaction_type_direction_mismatch",
                "message": str(exc),
            }
        ) from exc
    except ValueError as exc:
        raise validation_error("Invalid transaction type.") from exc
    return BulkResult(affected=affected)


@router.post("/bulk/accept-suggestions", response_model=BulkResult)
def accept_suggestions(
    payload: AcceptSuggestions,
    session: Session = Depends(get_session),
) -> BulkResult:
    policy = _classification_policy(session)
    affected = tx_service.accept_suggestions(
        session,
        ids=payload.ids,
        min_confidence=payload.min_confidence,
        policy=policy,
        manual=payload.manual,
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


@router.post("/bulk/type-suggestions/accept", response_model=BulkResult)
def bulk_accept_type_suggestions(
    payload: RejectSuggestions,
    session: Session = Depends(get_session),
) -> BulkResult:
    return BulkResult(
        affected=TransactionTypeService(session).accept_suggestions(ids=payload.ids)
    )


@router.post("/bulk/delete", response_model=BulkResult)
def bulk_delete(
    payload: BulkDelete, session: Session = Depends(get_session)
) -> BulkResult:
    return BulkResult(affected=tx_service.bulk_delete(session, payload.ids))


@router.delete("/{tx_id}", status_code=204, response_model=None)
def delete_transaction(
    tx_id: int, session: Session = Depends(get_session)
) -> None:
    deleted = tx_service.delete_transaction(session, tx_id)
    if not deleted:
        raise not_found("Transaction not found")
