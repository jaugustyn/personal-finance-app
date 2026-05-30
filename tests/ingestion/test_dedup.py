"""Tests for the dedup hash used by the ingestion service."""
from datetime import date
from decimal import Decimal

from finance.domain.dto import TransactionDTO
from finance.domain.enums import BankSource, TransactionDirection
from finance.ingestion.service import compute_dedup_hash


def _dto(**overrides) -> TransactionDTO:
    base = dict(
        booking_date=date(2026, 1, 1),
        amount=Decimal("-12.34"),
        currency="PLN",
        direction=TransactionDirection.DEBIT,
        merchant="Lidl",
        title="Card payment",
        source=BankSource.REVOLUT,
    )
    base.update(overrides)
    return TransactionDTO(**base)


def test_dedup_hash_stable_for_same_inputs() -> None:
    a = compute_dedup_hash(_dto())
    b = compute_dedup_hash(_dto())
    assert a == b


def test_dedup_hash_changes_with_amount() -> None:
    a = compute_dedup_hash(_dto())
    b = compute_dedup_hash(_dto(amount=Decimal("-12.35")))
    assert a != b


def test_dedup_hash_normalizes_merchant_case() -> None:
    a = compute_dedup_hash(_dto(merchant="Lidl"))
    b = compute_dedup_hash(_dto(merchant="LIDL"))
    assert a == b
