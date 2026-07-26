"""Domain operations for transactional accounts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finance.currencies import BASE_CURRENCY
from finance.db import command_transaction
from finance.domain.enums import AccountKind, BankSource
from finance.domain.models import Account, Import, Transaction


class AccountNotFound(LookupError):
    """Raised when a transactional account does not exist."""


class AccountArchived(ValueError):
    """Raised when a new operation targets an archived account."""


class AccountNameConflict(ValueError):
    """Raised when a normalized account name is already in use."""


@dataclass(frozen=True)
class AccountView:
    id: int
    name: str
    kind: str
    currency: str
    archived_at: datetime | None
    updated_at: datetime
    transaction_count: int
    import_count: int
    currencies: tuple[str, ...]
    last_transaction_date: date | None


def normalize_account_name(name: str) -> str:
    normalized = " ".join(name.split())
    if not normalized:
        raise ValueError("Account name is required.")
    if len(normalized) > 128:
        raise ValueError("Account name is too long.")
    return normalized


def _name_exists(session: Session, name: str, *, exclude_id: int | None = None) -> bool:
    stmt = select(Account.id).where(func.lower(Account.name) == name.lower())
    if exclude_id is not None:
        stmt = stmt.where(Account.id != exclude_id)
    return session.scalar(stmt.limit(1)) is not None


def get_active_account(session: Session, account_id: int) -> Account:
    account = session.get(Account, account_id)
    if account is None:
        raise AccountNotFound("Account not found.")
    if account.archived_at is not None:
        raise AccountArchived("Archived account cannot receive new transactions.")
    return account


def create_account(session: Session, *, name: str, kind: AccountKind | str) -> Account:
    normalized = normalize_account_name(name)
    kind_value = AccountKind(str(kind))
    if _name_exists(session, normalized):
        raise AccountNameConflict("An account with this name already exists.")
    row = Account(
        name=normalized,
        kind=kind_value,
        currency=BASE_CURRENCY,
        source=BankSource.UNKNOWN,
    )
    try:
        with command_transaction(session):
            session.add(row)
            session.flush()
    except IntegrityError as exc:
        raise AccountNameConflict("An account with this name already exists.") from exc
    session.refresh(row)
    return row


def update_account(
    session: Session,
    account_id: int,
    *,
    name: str | None = None,
    kind: AccountKind | str | None = None,
) -> Account:
    row = session.get(Account, account_id)
    if row is None:
        raise AccountNotFound("Account not found.")
    normalized = normalize_account_name(name) if name is not None else None
    if normalized is not None and _name_exists(session, normalized, exclude_id=account_id):
        raise AccountNameConflict("An account with this name already exists.")
    try:
        with command_transaction(session):
            if normalized is not None:
                row.name = normalized
            if kind is not None:
                row.kind = AccountKind(str(kind))
            row.updated_at = datetime.now(UTC)
            session.flush()
    except IntegrityError as exc:
        raise AccountNameConflict("An account with this name already exists.") from exc
    session.refresh(row)
    return row


def archive_account(session: Session, account_id: int) -> Account:
    row = session.get(Account, account_id)
    if row is None:
        raise AccountNotFound("Account not found.")
    if row.archived_at is None:
        with command_transaction(session):
            now = datetime.now(UTC)
            row.archived_at = now
            row.updated_at = now
    session.refresh(row)
    return row


def restore_account(session: Session, account_id: int) -> Account:
    row = session.get(Account, account_id)
    if row is None:
        raise AccountNotFound("Account not found.")
    if row.archived_at is not None:
        with command_transaction(session):
            row.archived_at = None
            row.updated_at = datetime.now(UTC)
    session.refresh(row)
    return row


def list_accounts(session: Session, *, include_archived: bool = False) -> list[AccountView]:
    account_stmt = select(Account).order_by(func.lower(Account.name), Account.id)
    if not include_archived:
        account_stmt = account_stmt.where(Account.archived_at.is_(None))
    accounts = list(session.scalars(account_stmt))
    if not accounts:
        return []
    ids = [row.id for row in accounts]
    transaction_stats = {
        int(account_id): (int(count), last_date)
        for account_id, count, last_date in session.execute(
            select(
                Transaction.account_id,
                func.count(Transaction.id),
                func.max(Transaction.booking_date),
            )
            .where(Transaction.account_id.in_(ids))
            .group_by(Transaction.account_id)
        )
    }
    import_counts = {
        int(account_id): int(count)
        for account_id, count in session.execute(
            select(Import.account_id, func.count(Import.id))
            .where(Import.account_id.in_(ids))
            .group_by(Import.account_id)
        )
    }
    currencies: dict[int, list[str]] = {account_id: [] for account_id in ids}
    for account_id, currency in session.execute(
        select(Transaction.account_id, Transaction.currency)
        .where(Transaction.account_id.in_(ids))
        .distinct()
        .order_by(Transaction.account_id, Transaction.currency)
    ):
        currencies[int(account_id)].append(str(currency))
    return [
        AccountView(
            id=row.id,
            name=row.name,
            kind=str(row.kind),
            currency=row.currency,
            archived_at=row.archived_at,
            updated_at=row.updated_at,
            transaction_count=transaction_stats.get(row.id, (0, None))[0],
            import_count=import_counts.get(row.id, 0),
            currencies=tuple(currencies[row.id]),
            last_transaction_date=transaction_stats.get(row.id, (0, None))[1],
        )
        for row in accounts
    ]


def suggest_account_id(session: Session, source: BankSource | None) -> int | None:
    if source is not None:
        recent = session.scalar(
            select(Import.account_id)
            .join(Account, Account.id == Import.account_id)
            .where(Import.source == source, Account.archived_at.is_(None))
            .order_by(Import.created_at.desc(), Import.id.desc())
            .limit(1)
        )
        if recent is not None:
            return int(recent)
    active_ids = list(
        session.scalars(
            select(Account.id)
            .where(Account.archived_at.is_(None))
            .order_by(Account.id)
            .limit(2)
        )
    )
    return int(active_ids[0]) if len(active_ids) == 1 else None
