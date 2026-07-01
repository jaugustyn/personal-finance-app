"""Pydantic schemas for merchant API endpoints."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class MerchantAliasRow(BaseModel):
    id: int
    alias_key: str
    alias_label: str
    canonical_key: str
    canonical_label: str
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class MerchantAliasCreate(BaseModel):
    canonical_label: str = Field(min_length=1, max_length=256)
    canonical_key: str | None = Field(default=None, max_length=256)
    aliases: list[str] = Field(min_length=1)


class MerchantAliasGroupLabelPatch(BaseModel):
    canonical_key: str = Field(min_length=1, max_length=256)
    canonical_label: str = Field(min_length=1, max_length=256)


class MerchantCandidateVariantRow(BaseModel):
    alias_key: str
    alias_label: str
    count: int
    total_debit: Decimal


class MerchantCandidateRow(BaseModel):
    canonical_key: str
    suggested_label: str
    aliases: list[str]
    variants: list[MerchantCandidateVariantRow]
    count: int
    total_debit: Decimal


class MerchantAliasSuggestionRow(BaseModel):
    alias_key: str
    alias_label: str
    canonical_key: str
    canonical_label: str
    count: int
    total_amount: Decimal
