"""Pydantic DTOs used at the boundary between parsers/API and persistence."""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from finance.domain.enums import BankSource, Category, TransactionDirection


class TransactionDTO(BaseModel):
    """Normalized transaction produced by bank parsers."""

    booking_date: date
    amount: Decimal
    currency: str = Field(min_length=3, max_length=3)
    direction: TransactionDirection
    merchant: str = ""
    title: str = ""
    raw_category: str | None = None  # original category from the bank
    raw_transaction_type: str | None = None  # original bank operation type
    category: Category | None = None  # mapped to unified schema (if known)
    source: BankSource = BankSource.UNKNOWN
    external_id: str | None = None  # bank reference if any
    booking_datetime: datetime | None = None


class ImportSummary(BaseModel):
    import_id: int
    source: BankSource
    inserted: int
    duplicates: int
    total_rows: int
