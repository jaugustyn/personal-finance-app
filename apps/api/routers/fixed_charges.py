"""CRUD API for user-maintained fixed-charge schedules."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.errors import conflict, not_found, validation_error
from apps.api.schemas.fixed_charges import (
    FixedChargeCreate,
    FixedChargeLinkRequest,
    FixedChargeLinkResponse,
    FixedChargeListResponse,
    FixedChargeManualPaymentCreate,
    FixedChargeRow,
    FixedChargeSummaryRow,
    FixedChargeTransactionRow,
    FixedChargeTransactionsResponse,
    FixedChargeUpdate,
)
from finance.accounts.service import AccountArchived, AccountNotFound
from finance.db import get_session
from finance.fixed_charges import service

router = APIRouter(prefix="/fixed-charges", tags=["fixed-charges"])


def _to_row(projection: service.FixedChargeView) -> FixedChargeRow:
    return FixedChargeRow(
        id=projection.id,
        name=projection.name,
        amount=float(projection.amount),
        cadence=projection.cadence,
        anchor_date=projection.anchor_date,
        category=projection.category,
        active=projection.active,
        next_due_date=projection.next_due_date,
        current_due_date=projection.current_due_date,
        payment_status=projection.payment_status,
        current_paid_amount=float(projection.current_paid_amount),
        linked_transaction_count=projection.linked_transaction_count,
        last_payment_date=projection.last_payment_date,
        monthly_equivalent=float(projection.monthly_equivalent),
        yearly_cost=float(projection.yearly_cost),
    )


@router.get("", response_model=FixedChargeListResponse)
def get_fixed_charges(
    session: Session = Depends(get_session),
) -> FixedChargeListResponse:
    result = service.list_fixed_charges(session)
    return FixedChargeListResponse(
        items=[_to_row(item) for item in result.items],
        summary=FixedChargeSummaryRow(
            active_count=result.summary.active_count,
            monthly_total=float(result.summary.monthly_total),
            yearly_total=float(result.summary.yearly_total),
            next_30_days_count=result.summary.next_30_days_count,
            next_30_days_total=float(result.summary.next_30_days_total),
        ),
    )


@router.post("", response_model=FixedChargeRow, status_code=201)
def create_fixed_charge(
    payload: FixedChargeCreate,
    session: Session = Depends(get_session),
) -> FixedChargeRow:
    try:
        row = service.create_fixed_charge(
            session,
            name=payload.name,
            amount=payload.amount,
            cadence=payload.cadence,
            anchor_date=payload.anchor_date,
            category=payload.category,
        )
    except service.FixedChargeValidationError as exc:
        raise validation_error(str(exc)) from exc
    projection = service.get_fixed_charge_view(session, row.id)
    if projection is None:  # pragma: no cover - row was created in this transaction
        raise not_found("Fixed charge not found.")
    return _to_row(projection)


@router.patch("/{charge_id}", response_model=FixedChargeRow)
def patch_fixed_charge(
    charge_id: int,
    payload: FixedChargeUpdate,
    session: Session = Depends(get_session),
) -> FixedChargeRow:
    try:
        row = service.update_fixed_charge(
            session,
            charge_id,
            payload.model_dump(exclude_unset=True),
        )
    except service.FixedChargeValidationError as exc:
        raise validation_error(str(exc)) from exc
    if row is None:
        raise not_found("Fixed charge not found.")
    projection = service.get_fixed_charge_view(session, row.id)
    if projection is None:  # pragma: no cover - row was updated in this transaction
        raise not_found("Fixed charge not found.")
    return _to_row(projection)


def _transaction_row(
    item: service.FixedChargeTransactionView,
) -> FixedChargeTransactionRow:
    return FixedChargeTransactionRow(
        transaction_id=item.transaction_id,
        scheduled_due_date=item.scheduled_due_date,
        booking_date=item.booking_date,
        merchant=item.merchant,
        title=item.title,
        amount=float(item.amount),
        currency=item.currency,
        amount_base=float(item.amount_base),
    )


@router.get(
    "/{charge_id}/transactions",
    response_model=FixedChargeTransactionsResponse,
)
def get_fixed_charge_transactions(
    charge_id: int,
    session: Session = Depends(get_session),
) -> FixedChargeTransactionsResponse:
    result = service.fixed_charge_transactions(session, charge_id)
    if result is None:
        raise not_found("Fixed charge not found.")
    return FixedChargeTransactionsResponse(
        fixed_charge_id=result.fixed_charge_id,
        current_due_date=result.current_due_date,
        linked=[_transaction_row(item) for item in result.linked],
        candidates=[_transaction_row(item) for item in result.candidates],
    )


@router.post(
    "/{charge_id}/transactions",
    response_model=FixedChargeLinkResponse,
)
def link_fixed_charge_transactions(
    charge_id: int,
    payload: FixedChargeLinkRequest,
    session: Session = Depends(get_session),
) -> FixedChargeLinkResponse:
    try:
        found = service.link_fixed_charge_transactions(
            session,
            charge_id,
            transaction_ids=payload.transaction_ids,
            scheduled_due_date=payload.scheduled_due_date,
        )
    except service.FixedChargeLinkConflict as exc:
        raise conflict(str(exc)) from exc
    except service.FixedChargeValidationError as exc:
        raise validation_error(str(exc)) from exc
    if not found:
        raise not_found("Fixed charge not found.")
    return FixedChargeLinkResponse()


@router.post(
    "/{charge_id}/transactions/manual",
    response_model=FixedChargeTransactionRow,
    status_code=201,
)
def create_fixed_charge_manual_payment(
    charge_id: int,
    payload: FixedChargeManualPaymentCreate,
    session: Session = Depends(get_session),
) -> FixedChargeTransactionRow:
    try:
        row = service.create_and_link_manual_payment(
            session,
            charge_id,
            **payload.model_dump(),
        )
    except AccountNotFound as exc:
        raise not_found(str(exc)) from exc
    except AccountArchived as exc:
        raise validation_error(str(exc)) from exc
    except service.FixedChargeValidationError as exc:
        raise validation_error(str(exc)) from exc
    except ValueError as exc:
        raise validation_error(str(exc)) from exc
    if row is None:
        raise not_found("Fixed charge not found.")
    return _transaction_row(row)


@router.delete(
    "/{charge_id}/transactions/{transaction_id}",
    status_code=204,
    response_model=None,
)
def unlink_fixed_charge_transaction(
    charge_id: int,
    transaction_id: int,
    session: Session = Depends(get_session),
) -> None:
    if not service.unlink_fixed_charge_transaction(
        session,
        charge_id,
        transaction_id,
    ):
        raise not_found("Fixed charge transaction link not found.")


@router.delete("/{charge_id}", status_code=204, response_model=None)
def delete_fixed_charge(
    charge_id: int,
    session: Session = Depends(get_session),
) -> None:
    if not service.delete_fixed_charge(session, charge_id):
        raise not_found("Fixed charge not found.")
