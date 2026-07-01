"""Pydantic schemas for profile API endpoints."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from finance.domain.enums import Category, TransactionType

RuleTarget = Literal["merchant", "title", "both"]
RuleMode = Literal["suggest_only", "auto_apply"]


class UserProfileRow(BaseModel):
    id: int
    base_currency: str
    salary_day: int | None
    monthly_savings_goal: Decimal | None
    category_limits: dict[str, float]
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class UserProfileUpdate(BaseModel):
    base_currency: str | None = Field(default=None, min_length=3, max_length=3)
    salary_day: int | None = Field(default=None, ge=1, le=31)
    monthly_savings_goal: Decimal | None = Field(default=None, ge=0)
    category_limits: dict[str, float] | None = None


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
    category: Category | None = None
    transaction_type: TransactionType | None = None
    is_transfer: bool | None = None
    priority: int = 100
    active: bool = True
    mode: RuleMode = "suggest_only"
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)


class PersonalRuleUpdate(BaseModel):
    pattern: str | None = Field(default=None, min_length=1, max_length=256)
    pattern_target: RuleTarget | None = None
    category: Category | None = None
    transaction_type: TransactionType | None = None
    is_transfer: bool | None = None
    priority: int | None = None
    active: bool | None = None
    mode: RuleMode | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
