"""Schemas for transactional account management."""

from datetime import date, datetime

from pydantic import BaseModel, Field

from finance.domain.enums import AccountKind


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    kind: AccountKind


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    kind: AccountKind | None = None


class AccountRow(BaseModel):
    id: int
    name: str
    kind: AccountKind
    currency: str
    archived_at: datetime | None
    updated_at: datetime
    transaction_count: int
    import_count: int
    currencies: list[str]
    last_transaction_date: date | None
    last_imported_at: datetime | None

    model_config = {"from_attributes": True}
