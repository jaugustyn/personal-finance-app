"""Pydantic schemas for profile API endpoints."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from finance.domain.enums import TransactionType

RuleTarget = Literal["merchant", "title", "both"]
RuleMode = Literal["suggest_only", "auto_apply"]


class PersonalRuleRow(BaseModel):
    id: int
    pattern: str
    pattern_norm: str
    pattern_target: str
    category: str | None
    transaction_type: str | None
    is_transfer: bool | None
    priority: int
    active: bool
    mode: str
    confidence: float
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class PersonalRuleCreate(BaseModel):
    pattern: str = Field(min_length=1, max_length=256)
    pattern_target: RuleTarget = "merchant"
    category: str | None = Field(default=None, min_length=1, max_length=64)
    transaction_type: TransactionType | None = None
    is_transfer: bool | None = None
    priority: int = 100
    active: bool = True
    mode: RuleMode = "suggest_only"
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)


class PersonalRuleUpdate(BaseModel):
    pattern: str | None = Field(default=None, min_length=1, max_length=256)
    pattern_target: RuleTarget | None = None
    category: str | None = Field(default=None, min_length=1, max_length=64)
    transaction_type: TransactionType | None = None
    is_transfer: bool | None = None
    priority: int | None = None
    active: bool | None = None
    mode: RuleMode | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def reject_null_for_required_rule_fields(self) -> PersonalRuleUpdate:
        nullable_fields = {"category", "transaction_type", "is_transfer"}
        for field_name in self.model_fields_set - nullable_fields:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null")
        return self
