"""CRUD and calendar projections for user-maintained fixed charges."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal, cast

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finance.currencies import BASE_CURRENCY, amount_base_value
from finance.db import command_transaction
from finance.domain.models import (
    CategoryDef,
    FixedCharge,
    FixedChargeTransaction,
    Transaction,
)
from finance.transactions.manual import add_manual_transaction

FixedChargeCadence = Literal["monthly", "quarterly", "semiannual", "yearly"]
FixedChargePaymentStatus = Literal["pending", "paid", "overdue", "paused"]

CADENCE_MONTHS: dict[FixedChargeCadence, int] = {
    "monthly": 1,
    "quarterly": 3,
    "semiannual": 6,
    "yearly": 12,
}
MONEY_QUANTUM = Decimal("0.01")
UPCOMING_WINDOW_DAYS = 30
LINK_WINDOW_DAYS = 14


class FixedChargeValidationError(ValueError):
    """Raised when a fixed-charge mutation violates the domain contract."""


class FixedChargeLinkConflict(ValueError):
    """Raised when a transaction already belongs to another fixed charge."""


@dataclass(frozen=True)
class FixedChargeView:
    id: int
    name: str
    amount: Decimal
    cadence: FixedChargeCadence
    anchor_date: date
    category: str | None
    active: bool
    next_due_date: date | None
    current_due_date: date | None
    payment_status: FixedChargePaymentStatus
    current_paid_amount: Decimal
    linked_transaction_count: int
    last_payment_date: date | None
    monthly_equivalent: Decimal
    yearly_cost: Decimal


@dataclass(frozen=True)
class FixedChargeTransactionView:
    transaction_id: int
    scheduled_due_date: date | None
    booking_date: date
    merchant: str
    title: str
    amount: Decimal
    currency: str
    amount_base: Decimal
    base_currency: str = BASE_CURRENCY


@dataclass(frozen=True)
class FixedChargeTransactions:
    fixed_charge_id: int
    current_due_date: date
    linked: list[FixedChargeTransactionView]
    candidates: list[FixedChargeTransactionView]


@dataclass(frozen=True)
class FixedChargeSummary:
    active_count: int
    monthly_total: Decimal
    yearly_total: Decimal
    next_30_days_count: int
    next_30_days_total: Decimal
    base_currency: str = BASE_CURRENCY


@dataclass(frozen=True)
class FixedChargeList:
    items: list[FixedChargeView]
    summary: FixedChargeSummary


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _cadence_months(cadence: str) -> int:
    if cadence not in CADENCE_MONTHS:
        raise FixedChargeValidationError("Unsupported fixed charge cadence.")
    return CADENCE_MONTHS[cast(FixedChargeCadence, cadence)]


def _add_months(anchor: date, months: int) -> date:
    month_index = anchor.month - 1 + months
    year = anchor.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(anchor.day, last_day))


def next_due_date(anchor: date, cadence: str, *, as_of: date) -> date:
    """Return the first calendar occurrence on or after ``as_of``."""
    interval = _cadence_months(cadence)
    if anchor >= as_of:
        return anchor
    elapsed_months = (as_of.year - anchor.year) * 12 + as_of.month - anchor.month
    occurrence = max(0, elapsed_months // interval)
    candidate = _add_months(anchor, occurrence * interval)
    if candidate < as_of:
        candidate = _add_months(anchor, (occurrence + 1) * interval)
    return candidate


def current_due_date(anchor: date, cadence: str, *, as_of: date) -> date:
    """Return the occurrence whose payment state is currently being reviewed."""
    interval = _cadence_months(cadence)
    if anchor >= as_of:
        return anchor
    elapsed_months = (as_of.year - anchor.year) * 12 + as_of.month - anchor.month
    occurrence = max(0, elapsed_months // interval)
    candidate = _add_months(anchor, occurrence * interval)
    if candidate > as_of and occurrence > 0:
        candidate = _add_months(anchor, (occurrence - 1) * interval)
    return candidate


def _is_occurrence(anchor: date, cadence: str, candidate: date) -> bool:
    if candidate < anchor:
        return False
    interval = _cadence_months(cadence)
    elapsed_months = (candidate.year - anchor.year) * 12 + candidate.month - anchor.month
    if elapsed_months % interval:
        return False
    return _add_months(anchor, elapsed_months) == candidate


def _period_costs(amount: Decimal, cadence: str) -> tuple[Decimal, Decimal]:
    interval = Decimal(_cadence_months(cadence))
    yearly = amount * Decimal(12) / interval
    return _money(yearly / Decimal(12)), _money(yearly)


def fixed_charge_view(
    row: FixedCharge,
    *,
    as_of: date | None = None,
    linked: list[tuple[FixedChargeTransaction, Transaction]] | None = None,
) -> FixedChargeView:
    today = as_of or date.today()
    monthly, yearly = _period_costs(row.amount, row.cadence)
    current_due = current_due_date(row.anchor_date, row.cadence, as_of=today)
    linked_rows = linked or []
    current_links = [
        transaction
        for link, transaction in linked_rows
        if link.scheduled_due_date == current_due
    ]
    current_paid = _money(
        sum(
            (
                abs(amount)
                for transaction in current_links
                if (amount := amount_base_value(transaction)) is not None
            ),
            Decimal(0),
        )
    )
    last_payment = max(
        (transaction.booking_date for _, transaction in linked_rows),
        default=None,
    )
    if not row.active:
        payment_status: FixedChargePaymentStatus = "paused"
    elif current_links:
        payment_status = "paid"
    elif current_due < today:
        payment_status = "overdue"
    else:
        payment_status = "pending"
    return FixedChargeView(
        id=row.id,
        name=row.name,
        amount=_money(row.amount),
        cadence=cast(FixedChargeCadence, row.cadence),
        anchor_date=row.anchor_date,
        category=row.category,
        active=row.active,
        next_due_date=(
            next_due_date(row.anchor_date, row.cadence, as_of=today) if row.active else None
        ),
        current_due_date=current_due if row.active else None,
        payment_status=payment_status,
        current_paid_amount=current_paid,
        linked_transaction_count=len(linked_rows),
        last_payment_date=last_payment,
        monthly_equivalent=monthly,
        yearly_cost=yearly,
    )


def _upcoming_occurrences(row: FixedCharge, *, as_of: date) -> list[date]:
    if not row.active:
        return []
    interval = _cadence_months(row.cadence)
    end = as_of + timedelta(days=UPCOMING_WINDOW_DAYS)
    first = next_due_date(row.anchor_date, row.cadence, as_of=as_of)
    if first > end:
        return []
    elapsed_months = (first.year - row.anchor_date.year) * 12 + first.month - row.anchor_date.month
    occurrence = max(0, elapsed_months // interval)
    dates: list[date] = []
    while True:
        candidate = _add_months(row.anchor_date, occurrence * interval)
        if candidate < as_of:
            occurrence += 1
            continue
        if candidate > end:
            break
        dates.append(candidate)
        occurrence += 1
    return dates


def list_fixed_charges(session: Session, *, as_of: date | None = None) -> FixedChargeList:
    today = as_of or date.today()
    rows = session.execute(select(FixedCharge)).scalars().all()
    linked_rows = session.execute(
        select(FixedChargeTransaction, Transaction)
        .join(Transaction, Transaction.id == FixedChargeTransaction.transaction_id)
        .order_by(FixedChargeTransaction.id)
    ).all()
    links_by_charge: dict[int, list[tuple[FixedChargeTransaction, Transaction]]] = {}
    for link, transaction in linked_rows:
        links_by_charge.setdefault(link.fixed_charge_id, []).append((link, transaction))
    views = [
        fixed_charge_view(
            row,
            as_of=today,
            linked=links_by_charge.get(row.id, []),
        )
        for row in rows
    ]
    views.sort(
        key=lambda item: (
            not item.active,
            item.next_due_date or date.max,
            item.name.casefold(),
            item.id,
        )
    )
    active_rows = [row for row in rows if row.active]
    active_views = [item for item in views if item.active]
    upcoming = [
        (row, occurrence)
        for row in active_rows
        for occurrence in _upcoming_occurrences(row, as_of=today)
        if not any(
            link.scheduled_due_date == occurrence
            for link, _ in links_by_charge.get(row.id, [])
        )
    ]
    summary = FixedChargeSummary(
        active_count=len(active_rows),
        monthly_total=_money(sum((item.monthly_equivalent for item in active_views), Decimal(0))),
        yearly_total=_money(sum((item.yearly_cost for item in active_views), Decimal(0))),
        next_30_days_count=len(upcoming),
        next_30_days_total=_money(sum((row.amount for row, _ in upcoming), Decimal(0))),
    )
    return FixedChargeList(items=views, summary=summary)


def get_fixed_charge_view(
    session: Session,
    charge_id: int,
    *,
    as_of: date | None = None,
) -> FixedChargeView | None:
    result = list_fixed_charges(session, as_of=as_of)
    return next((item for item in result.items if item.id == charge_id), None)


def _transaction_view(
    transaction: Transaction,
    *,
    scheduled_due_date: date | None,
) -> FixedChargeTransactionView:
    base_amount = amount_base_value(transaction)
    if base_amount is None:
        raise FixedChargeValidationError("Transaction has no valid PLN conversion.")
    return FixedChargeTransactionView(
        transaction_id=transaction.id,
        scheduled_due_date=scheduled_due_date,
        booking_date=transaction.booking_date,
        merchant=transaction.merchant or "",
        title=transaction.title or "",
        amount=Decimal(transaction.amount),
        currency=str(transaction.currency or ""),
        amount_base=_money(base_amount),
    )


def fixed_charge_transactions(
    session: Session,
    charge_id: int,
    *,
    as_of: date | None = None,
) -> FixedChargeTransactions | None:
    charge = session.get(FixedCharge, charge_id)
    if charge is None:
        return None
    today = as_of or date.today()
    due_date = current_due_date(charge.anchor_date, charge.cadence, as_of=today)
    linked_rows = session.execute(
        select(FixedChargeTransaction, Transaction)
        .join(Transaction, Transaction.id == FixedChargeTransaction.transaction_id)
        .where(FixedChargeTransaction.fixed_charge_id == charge_id)
        .order_by(
            FixedChargeTransaction.scheduled_due_date.desc(),
            Transaction.booking_date.desc(),
            Transaction.id.desc(),
        )
    ).all()
    linked = [
        _transaction_view(transaction, scheduled_due_date=link.scheduled_due_date)
        for link, transaction in linked_rows
    ]
    already_linked_ids = set(
        session.execute(select(FixedChargeTransaction.transaction_id)).scalars().all()
    )
    start = due_date - timedelta(days=LINK_WINDOW_DAYS)
    end = due_date + timedelta(days=LINK_WINDOW_DAYS)
    rows = session.execute(
        select(Transaction).where(
            Transaction.direction == "debit",
            Transaction.booking_date >= start,
            Transaction.booking_date <= end,
        )
    ).scalars().all()
    candidates = [
        _transaction_view(transaction, scheduled_due_date=None)
        for transaction in rows
        if transaction.id not in already_linked_ids
        and amount_base_value(transaction) is not None
    ]
    candidates.sort(
        key=lambda item: (
            abs(abs(item.amount_base) - charge.amount),
            abs((item.booking_date - due_date).days),
            -item.transaction_id,
        )
    )
    return FixedChargeTransactions(
        fixed_charge_id=charge_id,
        current_due_date=due_date,
        linked=linked,
        candidates=candidates,
    )


def link_fixed_charge_transactions(
    session: Session,
    charge_id: int,
    *,
    transaction_ids: list[int],
    scheduled_due_date: date,
) -> bool:
    charge = session.get(FixedCharge, charge_id)
    if charge is None:
        return False
    if not transaction_ids:
        raise FixedChargeValidationError("Select at least one transaction.")
    if not _is_occurrence(charge.anchor_date, charge.cadence, scheduled_due_date):
        raise FixedChargeValidationError("Date is not part of this fixed charge schedule.")
    unique_ids = list(dict.fromkeys(transaction_ids))
    rows = session.execute(
        select(Transaction).where(Transaction.id.in_(unique_ids))
    ).scalars().all()
    if len(rows) != len(unique_ids):
        raise FixedChargeValidationError("Transaction not found.")
    existing = set(
        session.execute(
            select(FixedChargeTransaction.transaction_id).where(
                FixedChargeTransaction.transaction_id.in_(unique_ids)
            )
        ).scalars().all()
    )
    if existing:
        raise FixedChargeLinkConflict("Transaction is already assigned to a fixed charge.")
    try:
        with command_transaction(session):
            for transaction in rows:
                if transaction.direction != "debit":
                    raise FixedChargeValidationError(
                        "Only outgoing transactions can be assigned."
                    )
                if amount_base_value(transaction) is None:
                    raise FixedChargeValidationError(
                        "Transaction has no valid PLN conversion."
                    )
                if (
                    abs((transaction.booking_date - scheduled_due_date).days)
                    > LINK_WINDOW_DAYS
                ):
                    raise FixedChargeValidationError(
                        "Transaction is outside the allowed date range."
                    )
                session.add(
                    FixedChargeTransaction(
                        fixed_charge_id=charge_id,
                        transaction_id=transaction.id,
                        scheduled_due_date=scheduled_due_date,
                    )
                )
    except IntegrityError as exc:
        raise FixedChargeLinkConflict(
            "Transaction is already assigned to a fixed charge."
        ) from exc
    return True


def create_and_link_manual_payment(
    session: Session,
    charge_id: int,
    *,
    account_id: int,
    scheduled_due_date: date,
    booking_date: date,
    amount: Decimal,
    direction: str,
    merchant: str = "",
    title: str = "",
    transaction_type: str | None = None,
    category: str | None = None,
    notes: str | None = None,
) -> FixedChargeTransactionView | None:
    """Create a manual debit and link it to one schedule occurrence atomically."""
    charge = session.get(FixedCharge, charge_id)
    if charge is None:
        return None
    if direction != "debit":
        raise FixedChargeValidationError(
            "Only outgoing transactions can be assigned to a fixed charge."
        )
    if not _is_occurrence(charge.anchor_date, charge.cadence, scheduled_due_date):
        raise FixedChargeValidationError(
            "Date is not part of this fixed charge schedule."
        )
    if abs((booking_date - scheduled_due_date).days) > LINK_WINDOW_DAYS:
        raise FixedChargeValidationError(
            "Transaction is outside the allowed date range."
        )
    try:
        transaction = add_manual_transaction(
            session,
            account_id=account_id,
            booking_date=booking_date,
            amount=amount,
            direction=direction,
            merchant=merchant,
            title=title,
            transaction_type=transaction_type,
            category=category,
            notes=notes,
        )
        session.add(
            FixedChargeTransaction(
                fixed_charge_id=charge_id,
                transaction_id=transaction.id,
                scheduled_due_date=scheduled_due_date,
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(transaction)
    return _transaction_view(
        transaction,
        scheduled_due_date=scheduled_due_date,
    )


def unlink_fixed_charge_transaction(
    session: Session,
    charge_id: int,
    transaction_id: int,
) -> bool:
    link = session.execute(
        select(FixedChargeTransaction).where(
            FixedChargeTransaction.fixed_charge_id == charge_id,
            FixedChargeTransaction.transaction_id == transaction_id,
        )
    ).scalar_one_or_none()
    if link is None:
        return False
    with command_transaction(session):
        session.execute(
            delete(FixedChargeTransaction).where(FixedChargeTransaction.id == link.id)
        )
    return True


def _normalized_name(name: str) -> str:
    normalized = " ".join(name.split())
    if not normalized:
        raise FixedChargeValidationError("Fixed charge name cannot be empty.")
    return normalized


def _validated_category(session: Session, category: str | None) -> str | None:
    normalized = category.strip() if category else None
    if not normalized:
        return None
    exists = session.execute(
        select(CategoryDef.id).where(CategoryDef.name == normalized)
    ).scalar_one_or_none()
    if exists is None:
        raise FixedChargeValidationError("Category not found.")
    return normalized


def create_fixed_charge(
    session: Session,
    *,
    name: str,
    amount: Decimal,
    cadence: str,
    anchor_date: date,
    category: str | None = None,
) -> FixedCharge:
    _cadence_months(cadence)
    if amount <= 0:
        raise FixedChargeValidationError("Fixed charge amount must be positive.")
    row = FixedCharge(
        name=_normalized_name(name),
        amount=_money(amount),
        cadence=cadence,
        anchor_date=anchor_date,
        category=_validated_category(session, category),
    )
    with command_transaction(session):
        session.add(row)
    session.refresh(row)
    return row


def update_fixed_charge(
    session: Session,
    charge_id: int,
    values: dict[str, object],
) -> FixedCharge | None:
    row = session.get(FixedCharge, charge_id)
    if row is None:
        return None
    with command_transaction(session):
        _apply_fixed_charge_update(session, row, values)
    session.refresh(row)
    return row


def _apply_fixed_charge_update(
    session: Session,
    row: FixedCharge,
    values: dict[str, object],
) -> None:
    if "name" in values:
        name = values["name"]
        if not isinstance(name, str):
            raise FixedChargeValidationError("Fixed charge name is required.")
        row.name = _normalized_name(name)
    if "amount" in values:
        amount = values["amount"]
        if not isinstance(amount, Decimal) or amount <= 0:
            raise FixedChargeValidationError("Fixed charge amount must be positive.")
        row.amount = _money(amount)
    if "cadence" in values:
        cadence = values["cadence"]
        if not isinstance(cadence, str):
            raise FixedChargeValidationError("Fixed charge cadence is required.")
        _cadence_months(cadence)
        row.cadence = cadence
    if "anchor_date" in values:
        anchor_date = values["anchor_date"]
        if not isinstance(anchor_date, date):
            raise FixedChargeValidationError("Fixed charge date is required.")
        row.anchor_date = anchor_date
    if "category" in values:
        category = values["category"]
        if category is not None and not isinstance(category, str):
            raise FixedChargeValidationError("Invalid fixed charge category.")
        row.category = _validated_category(session, category)
    if "active" in values:
        active = values["active"]
        if not isinstance(active, bool):
            raise FixedChargeValidationError("Invalid fixed charge state.")
        row.active = active


def delete_fixed_charge(session: Session, charge_id: int) -> bool:
    row = session.get(FixedCharge, charge_id)
    if row is None:
        return False
    with command_transaction(session):
        session.execute(
            delete(FixedChargeTransaction).where(
                FixedChargeTransaction.fixed_charge_id == charge_id
            )
        )
        session.delete(row)
    return True
