"""Pydantic schemas for merchant API endpoints."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field

MerchantAliasLabel = Annotated[str, Field(min_length=1, max_length=256)]


class MerchantAliasRow(BaseModel):
    id: int
    alias_key: str
    alias_label: str
    canonical_key: str
    canonical_label: str
    usage_count: int = 0
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class MerchantAliasCreate(BaseModel):
    canonical_label: str = Field(min_length=1, max_length=256)
    canonical_key: str | None = Field(default=None, max_length=256)
    aliases: list[MerchantAliasLabel] = Field(min_length=1, max_length=1000)


class MerchantAliasGroupLabelPatch(BaseModel):
    canonical_key: str = Field(min_length=1, max_length=256)
    canonical_label: str = Field(min_length=1, max_length=256)


class MerchantCandidateVariantRow(BaseModel):
    alias_key: str
    alias_label: str
    count: int
    total_debit: Decimal
    base_currency: str


class MerchantCandidateRow(BaseModel):
    canonical_key: str
    canonical_label: str
    suggested_label: str
    aliases: list[str]
    variants: list[MerchantCandidateVariantRow]
    count: int
    total_debit: Decimal
    base_currency: str


class MerchantAliasSuggestionRow(BaseModel):
    alias_key: str
    alias_label: str
    canonical_key: str
    canonical_label: str
    count: int
    total_amount: Decimal
    base_currency: str
