"""Transactional account endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.errors import conflict, not_found, validation_error
from apps.api.schemas.accounts import AccountCreate, AccountRow, AccountUpdate
from finance.accounts import service
from finance.db import get_session

router = APIRouter(prefix="/accounts", tags=["accounts"])


def _account_row(session: Session, account_id: int) -> AccountRow:
    rows = service.list_accounts(session, include_archived=True)
    row = next((item for item in rows if item.id == account_id), None)
    if row is None:
        raise not_found("Account not found.")
    return AccountRow.model_validate(row)


def _account_error(exc: Exception) -> Exception:
    if isinstance(exc, service.AccountNotFound):
        return not_found(str(exc))
    if isinstance(exc, service.AccountNameConflict):
        return conflict(str(exc))
    return validation_error(str(exc))


@router.get("", response_model=list[AccountRow])
def get_accounts(
    include_archived: bool = Query(default=False),
    session: Session = Depends(get_session),
) -> list[AccountRow]:
    return [
        AccountRow.model_validate(row)
        for row in service.list_accounts(session, include_archived=include_archived)
    ]


@router.post("", response_model=AccountRow, status_code=201)
def post_account(
    payload: AccountCreate,
    session: Session = Depends(get_session),
) -> AccountRow:
    try:
        row = service.create_account(session, **payload.model_dump())
    except (service.AccountNameConflict, ValueError) as exc:
        raise _account_error(exc) from exc
    return _account_row(session, row.id)


@router.patch("/{account_id}", response_model=AccountRow)
def patch_account(
    account_id: int,
    payload: AccountUpdate,
    session: Session = Depends(get_session),
) -> AccountRow:
    try:
        row = service.update_account(
            session,
            account_id,
            **payload.model_dump(exclude_unset=True),
        )
    except (service.AccountNotFound, service.AccountNameConflict, ValueError) as exc:
        raise _account_error(exc) from exc
    return _account_row(session, row.id)


@router.post("/{account_id}/archive", response_model=AccountRow)
def post_archive_account(
    account_id: int,
    session: Session = Depends(get_session),
) -> AccountRow:
    try:
        row = service.archive_account(session, account_id)
    except service.AccountNotFound as exc:
        raise not_found(str(exc)) from exc
    return _account_row(session, row.id)


@router.post("/{account_id}/restore", response_model=AccountRow)
def post_restore_account(
    account_id: int,
    session: Session = Depends(get_session),
) -> AccountRow:
    try:
        row = service.restore_account(session, account_id)
    except service.AccountNotFound as exc:
        raise not_found(str(exc)) from exc
    return _account_row(session, row.id)
