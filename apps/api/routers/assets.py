"""API for manual and fixed-rate asset valuation."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.errors import conflict, not_found, validation_error
from apps.api.schemas.assets import (
    AssetAccountCreate,
    AssetAccountRow,
    AssetAccountUpdate,
    AssetFxRecomputeRow,
    AssetHistoryRow,
    AssetItemCreate,
    AssetItemRow,
    AssetItemUpdate,
    AssetMutationStatus,
    AssetOverviewRow,
    AssetValuationRow,
    AssetValuationUpdate,
    AssetValuationWrite,
    HistoryRange,
)
from finance.assets import service
from finance.db import get_session

router = APIRouter(prefix="/assets", tags=["assets"])


def _domain_error(exc: ValueError):
    if isinstance(exc, service.AssetConflictError):
        return conflict(str(exc))
    return validation_error(str(exc))


@router.get("/overview", response_model=AssetOverviewRow)
def get_overview(
    as_of: date | None = None,
    session: Session = Depends(get_session),
) -> AssetOverviewRow:
    return AssetOverviewRow.model_validate(service.overview(session, as_of=as_of))


@router.get("/history", response_model=AssetHistoryRow)
def get_history(
    range_name: HistoryRange = Query(default="1y", alias="range"),
    account_id: int | None = Query(default=None, ge=1),
    as_of: date | None = None,
    session: Session = Depends(get_session),
) -> AssetHistoryRow:
    try:
        result = service.history(
            session,
            range_name=range_name,
            account_id=account_id,
            as_of=as_of,
        )
    except service.AssetValidationError as exc:
        raise validation_error(str(exc)) from exc
    return AssetHistoryRow.model_validate(result)


@router.post("/valuations/recompute-fx", response_model=AssetFxRecomputeRow)
def recompute_fx(session: Session = Depends(get_session)) -> AssetFxRecomputeRow:
    return AssetFxRecomputeRow.model_validate(service.recompute_missing_fx(session))


@router.get("/accounts", response_model=list[AssetAccountRow])
def get_accounts(
    include_archived: bool = False,
    as_of: date | None = None,
    session: Session = Depends(get_session),
) -> list[AssetAccountRow]:
    return [
        AssetAccountRow.model_validate(row)
        for row in service.list_accounts(
            session,
            include_archived=include_archived,
            as_of=as_of,
        )
    ]


@router.post("/accounts", response_model=AssetAccountRow, status_code=201)
def post_account(
    payload: AssetAccountCreate,
    session: Session = Depends(get_session),
) -> AssetAccountRow:
    values = payload.model_dump()
    initial = values.pop("initial_valuation")
    try:
        row = service.create_account(
            session,
            **values,
            initial_valuation=initial,
        )
    except (service.AssetValidationError, service.AssetConflictError) as exc:
        raise _domain_error(exc) from exc
    result = service.get_account_view(session, row.id)
    if result is None:  # pragma: no cover
        raise not_found("Asset account not found.")
    return AssetAccountRow.model_validate(result)


@router.patch("/accounts/{account_id}", response_model=AssetAccountRow)
def patch_account(
    account_id: int,
    payload: AssetAccountUpdate,
    session: Session = Depends(get_session),
) -> AssetAccountRow:
    try:
        row = service.update_account(
            session,
            account_id,
            payload.model_dump(exclude_unset=True),
        )
    except (service.AssetValidationError, service.AssetConflictError) as exc:
        raise _domain_error(exc) from exc
    if row is None:
        raise not_found("Asset account not found.")
    result = service.get_account_view(session, row.id)
    if result is None:  # pragma: no cover
        raise not_found("Asset account not found.")
    return AssetAccountRow.model_validate(result)


@router.post("/accounts/{account_id}/archive", response_model=AssetMutationStatus)
def archive_account(
    account_id: int,
    session: Session = Depends(get_session),
) -> AssetMutationStatus:
    if not service.set_account_archived(session, account_id, archived=True):
        raise not_found("Asset account not found.")
    return AssetMutationStatus()


@router.post("/accounts/{account_id}/restore", response_model=AssetMutationStatus)
def restore_account(
    account_id: int,
    session: Session = Depends(get_session),
) -> AssetMutationStatus:
    if not service.set_account_archived(session, account_id, archived=False):
        raise not_found("Asset account not found.")
    return AssetMutationStatus()


@router.post(
    "/accounts/{account_id}/items",
    response_model=AssetItemRow,
    status_code=201,
)
def post_item(
    account_id: int,
    payload: AssetItemCreate,
    session: Session = Depends(get_session),
) -> AssetItemRow:
    values = payload.model_dump()
    initial = values.pop("initial_valuation")
    try:
        row = service.create_item(
            session,
            account_id,
            **values,
            initial_valuation=initial,
        )
    except (service.AssetValidationError, service.AssetConflictError) as exc:
        raise _domain_error(exc) from exc
    if row is None:
        raise not_found("Asset account not found.")
    result = service.get_item_view(session, row.id)
    if result is None:  # pragma: no cover
        raise not_found("Asset item not found.")
    return AssetItemRow.model_validate(result)


@router.patch("/items/{item_id}", response_model=AssetItemRow)
def patch_item(
    item_id: int,
    payload: AssetItemUpdate,
    session: Session = Depends(get_session),
) -> AssetItemRow:
    try:
        row = service.update_item(
            session,
            item_id,
            payload.model_dump(exclude_unset=True),
        )
    except (service.AssetValidationError, service.AssetConflictError) as exc:
        raise _domain_error(exc) from exc
    if row is None:
        raise not_found("Asset item not found.")
    result = service.get_item_view(session, row.id)
    if result is None:  # pragma: no cover
        raise not_found("Asset item not found.")
    return AssetItemRow.model_validate(result)


@router.post("/items/{item_id}/archive", response_model=AssetMutationStatus)
def archive_item(
    item_id: int,
    session: Session = Depends(get_session),
) -> AssetMutationStatus:
    if not service.set_item_archived(session, item_id, archived=True):
        raise not_found("Asset item not found.")
    return AssetMutationStatus()


@router.post("/items/{item_id}/restore", response_model=AssetMutationStatus)
def restore_item(
    item_id: int,
    session: Session = Depends(get_session),
) -> AssetMutationStatus:
    if not service.set_item_archived(session, item_id, archived=False):
        raise not_found("Asset item not found.")
    return AssetMutationStatus()


@router.get("/items/{item_id}/valuations", response_model=list[AssetValuationRow])
def get_valuations(
    item_id: int,
    session: Session = Depends(get_session),
) -> list[AssetValuationRow]:
    rows = service.list_valuations(session, item_id)
    if rows is None:
        raise not_found("Asset item not found.")
    return [AssetValuationRow.model_validate(row) for row in rows]


@router.post(
    "/items/{item_id}/valuations",
    response_model=AssetValuationRow,
    status_code=201,
)
def post_valuation(
    item_id: int,
    payload: AssetValuationWrite,
    session: Session = Depends(get_session),
) -> AssetValuationRow:
    try:
        row = service.add_valuation(session, item_id, payload.model_dump())
    except (service.AssetValidationError, service.AssetConflictError) as exc:
        raise _domain_error(exc) from exc
    if row is None:
        raise not_found("Asset item not found.")
    return AssetValuationRow.model_validate(row)


@router.put("/valuations/{valuation_id}", response_model=AssetValuationRow)
def put_valuation(
    valuation_id: int,
    payload: AssetValuationUpdate,
    session: Session = Depends(get_session),
) -> AssetValuationRow:
    try:
        row = service.update_valuation(
            session,
            valuation_id,
            payload.model_dump(exclude_unset=True),
        )
    except (service.AssetValidationError, service.AssetConflictError) as exc:
        raise _domain_error(exc) from exc
    if row is None:
        raise not_found("Asset valuation not found.")
    return AssetValuationRow.model_validate(row)


@router.delete("/valuations/{valuation_id}", status_code=204, response_model=None)
def remove_valuation(
    valuation_id: int,
    session: Session = Depends(get_session),
) -> None:
    try:
        removed = service.delete_valuation(session, valuation_id)
    except service.AssetConflictError as exc:
        raise conflict(str(exc)) from exc
    if not removed:
        raise not_found("Asset valuation not found.")
