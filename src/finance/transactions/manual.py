"""Creation and editing of transactions entered explicitly by the user."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

from sqlalchemy.orm import Session

from finance.currencies import BASE_CURRENCY, convert_amount
from finance.domain.enums import BankSource, TransactionDirection, TransactionType
from finance.domain.models import Transaction
from finance.transactions.category_assignment import CategoryAssignmentService
from finance.transactions.mutation_rules import clean_tags
from finance.transactions.type_decision import direction_matches
from finance.transactions.type_service import (
    TransactionTypeDirectionMismatch,
    TransactionTypeService,
)

MONEY_QUANTUM = Decimal("0.01")


class ManualTransactionValidationError(ValueError):
    """Raised when a manual transaction payload is internally inconsistent."""


class ManualTransactionEditForbidden(ValueError):
    """Raised when core bank data is edited through the manual entry endpoint."""


@dataclass(frozen=True)
class ManualTransactionValues:
    booking_date: date
    amount: Decimal
    direction: str
    merchant: str
    title: str
    transaction_type: str | None
    category: str | None
    notes: str | None


def _label(value: str | None) -> str:
    return " ".join((value or "").split())


def _signed_amount(amount: Decimal, direction: str) -> Decimal:
    value = Decimal(amount).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)
    if value <= 0:
        raise ManualTransactionValidationError("Amount must be positive.")
    return -value if direction == TransactionDirection.DEBIT.value else value


def _dedup_hash() -> str:
    token = f"manual:{uuid4().hex}"
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _validated_values(
    *,
    booking_date: date,
    amount: Decimal,
    direction: TransactionDirection | str,
    merchant: str,
    title: str,
    transaction_type: TransactionType | str | None,
    category: str | None,
    notes: str | None,
) -> ManualTransactionValues:
    direction_value = TransactionDirection(str(direction)).value
    merchant_value = _label(merchant)
    title_value = _label(title)
    if not merchant_value and not title_value:
        raise ManualTransactionValidationError(
            "Provide a merchant or transaction title."
        )
    type_value = (
        TransactionType(str(transaction_type)).value
        if transaction_type is not None
        else None
    )
    category_value = _label(category) or None
    if type_value is not None and not direction_matches(type_value, direction_value):
        raise TransactionTypeDirectionMismatch(
            f"{type_value!r} is unusual for direction {direction_value!r}."
        )
    if category_value is not None:
        category_type = (
            TransactionType.REFUND.value
            if direction_value == TransactionDirection.CREDIT.value
            else TransactionType.EXPENSE.value
        )
        if type_value is not None and type_value != category_type:
            raise ManualTransactionValidationError(
                "A category requires expense for an outflow or refund for an inflow."
            )
    return ManualTransactionValues(
        booking_date=booking_date,
        amount=_signed_amount(amount, direction_value),
        direction=direction_value,
        merchant=merchant_value,
        title=title_value,
        transaction_type=type_value,
        category=category_value,
        notes=((notes or "").strip() or None),
    )


def _apply_labels(
    session: Session,
    tx: Transaction,
    *,
    transaction_type: str | None,
    category: str | None,
    subcategory: str | None = None,
) -> None:
    category_service = CategoryAssignmentService(session)
    type_service = TransactionTypeService(session)
    category_service.apply_manual_decision(
        tx,
        category,
        subcategory=subcategory,
    )
    if category is not None:
        return
    if transaction_type is not None:
        if (
            str(tx.transaction_type or "") != transaction_type
            or tx.transaction_type_confirmation_method != "manual"
        ):
            type_service.apply_manual_type(tx, transaction_type)
    else:
        type_service.clear_manual_type(tx)


def add_manual_transaction(
    session: Session,
    *,
    booking_date: date,
    amount: Decimal,
    direction: TransactionDirection | str,
    merchant: str = "",
    title: str = "",
    transaction_type: TransactionType | str | None = None,
    category: str | None = None,
    notes: str | None = None,
) -> Transaction:
    """Add and flush a manual transaction without committing the session."""
    values = _validated_values(
        booking_date=booking_date,
        amount=amount,
        direction=direction,
        merchant=merchant,
        title=title,
        transaction_type=transaction_type,
        category=category,
        notes=notes,
    )
    conversion = convert_amount(
        session,
        amount=values.amount,
        currency=BASE_CURRENCY,
        rate_date=booking_date,
    )
    tx = Transaction(
        booking_date=booking_date,
        booking_datetime=None,
        amount=values.amount,
        currency=BASE_CURRENCY,
        amount_base=conversion.amount_base,
        base_currency=conversion.base_currency,
        fx_rate=conversion.fx_rate,
        fx_rate_date=conversion.fx_rate_date,
        fx_rate_source=conversion.fx_rate_source,
        direction=values.direction,
        merchant=values.merchant,
        title=values.title,
        source=BankSource.MANUAL.value,
        external_id=None,
        dedup_hash=_dedup_hash(),
        import_id=None,
        notes=values.notes,
        tags=clean_tags([]),
    )
    session.add(tx)
    session.flush()
    _apply_labels(
        session,
        tx,
        transaction_type=values.transaction_type,
        category=values.category,
    )
    return tx


def create_manual_transaction(
    session: Session,
    *,
    booking_date: date,
    amount: Decimal,
    direction: TransactionDirection | str,
    merchant: str = "",
    title: str = "",
    transaction_type: TransactionType | str | None = None,
    category: str | None = None,
    notes: str | None = None,
) -> Transaction:
    try:
        tx = add_manual_transaction(
            session,
            booking_date=booking_date,
            amount=amount,
            direction=direction,
            merchant=merchant,
            title=title,
            transaction_type=transaction_type,
            category=category,
            notes=notes,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(tx)
    return tx


def update_manual_transaction(
    session: Session,
    tx_id: int,
    *,
    booking_date: date,
    amount: Decimal,
    direction: TransactionDirection | str,
    merchant: str = "",
    title: str = "",
    transaction_type: TransactionType | str | None = None,
    category: str | None = None,
    notes: str | None = None,
) -> Transaction | None:
    tx = session.get(Transaction, tx_id)
    if tx is None:
        return None
    if str(tx.source) != BankSource.MANUAL.value:
        raise ManualTransactionEditForbidden(
            "Only manually added transactions can be edited here."
        )
    validated = _validated_values(
        booking_date=booking_date,
        amount=amount,
        direction=direction,
        merchant=merchant,
        title=title,
        transaction_type=transaction_type,
        category=category,
        notes=notes,
    )
    preserved_subcategory = (
        str(tx.subcategory)
        if tx.subcategory is not None
        and str(tx.category or "") == str(validated.category or "")
        else None
    )
    try:
        conversion = convert_amount(
            session,
            amount=validated.amount,
            currency=BASE_CURRENCY,
            rate_date=validated.booking_date,
        )
        tx.booking_date = validated.booking_date
        tx.booking_datetime = None
        tx.amount = validated.amount
        tx.currency = BASE_CURRENCY
        tx.amount_base = conversion.amount_base
        tx.base_currency = conversion.base_currency
        tx.fx_rate = conversion.fx_rate
        tx.fx_rate_date = conversion.fx_rate_date
        tx.fx_rate_source = conversion.fx_rate_source
        tx.direction = TransactionDirection(validated.direction)
        tx.merchant = validated.merchant
        tx.title = validated.title
        tx.notes = validated.notes
        _apply_labels(
            session,
            tx,
            transaction_type=validated.transaction_type,
            category=validated.category,
            subcategory=preserved_subcategory,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(tx)
    return tx
