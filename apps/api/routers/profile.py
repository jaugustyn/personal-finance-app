"""User profile and personal rule endpoints."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from finance.db import get_session
from finance.domain.enums import Category, TransactionType
from finance.profile import service as profile_service

RuleTarget = Literal["merchant", "title", "both"]
RuleMode = Literal["suggest_only", "auto_apply"]

router = APIRouter(prefix="/profile", tags=["profile"])


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


@router.get("", response_model=UserProfileRow)
def get_profile(session: Session = Depends(get_session)) -> UserProfileRow:
    profile = profile_service.get_or_create_profile(session)
    return UserProfileRow.model_validate(profile)


@router.patch("", response_model=UserProfileRow)
def patch_profile(
    payload: UserProfileUpdate,
    session: Session = Depends(get_session),
) -> UserProfileRow:
    current = profile_service.get_or_create_profile(session)
    fields = payload.model_fields_set
    profile = profile_service.update_profile(
        session,
        base_currency=payload.base_currency
        if "base_currency" in fields
        else current.base_currency,
        salary_day=payload.salary_day if "salary_day" in fields else current.salary_day,
        monthly_savings_goal=payload.monthly_savings_goal
        if "monthly_savings_goal" in fields
        else current.monthly_savings_goal,
        category_limits=payload.category_limits
        if "category_limits" in fields
        else current.category_limits,
    )
    return UserProfileRow.model_validate(profile)


@router.get("/rules", response_model=list[PersonalRuleRow])
def list_rules(session: Session = Depends(get_session)) -> list[PersonalRuleRow]:
    return [
        PersonalRuleRow.model_validate(rule)
        for rule in profile_service.list_rules(session)
    ]


@router.post("/rules", response_model=PersonalRuleRow, status_code=201)
def create_rule(
    payload: PersonalRuleCreate,
    session: Session = Depends(get_session),
) -> PersonalRuleRow:
    try:
        rule = profile_service.create_rule(session, **payload.model_dump(mode="json"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return PersonalRuleRow.model_validate(rule)


@router.patch("/rules/{rule_id}", response_model=PersonalRuleRow)
def patch_rule(
    rule_id: int,
    payload: PersonalRuleUpdate,
    session: Session = Depends(get_session),
) -> PersonalRuleRow:
    try:
        rule = profile_service.update_rule(
            session,
            rule_id,
            **payload.model_dump(exclude_unset=True, mode="json"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found.")
    return PersonalRuleRow.model_validate(rule)


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, session: Session = Depends(get_session)) -> None:
    deleted = profile_service.delete_rule(session, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found.")
