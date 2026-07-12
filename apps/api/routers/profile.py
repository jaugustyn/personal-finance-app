"""User profile and personal rule endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.errors import not_found, validation_error
from apps.api.schemas.profile import (
    PersonalRuleCreate,
    PersonalRuleRow,
    PersonalRuleUpdate,
    UserProfileRow,
    UserProfileUpdate,
)
from finance.db import get_session
from finance.profile import service as profile_service

router = APIRouter(prefix="/profile", tags=["profile"])


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
        raise validation_error(str(exc)) from exc
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
        raise validation_error(str(exc)) from exc
    if rule is None:
        raise not_found("Rule not found.")
    return PersonalRuleRow.model_validate(rule)


@router.delete("/rules/{rule_id}", status_code=204, response_model=None)
def delete_rule(rule_id: int, session: Session = Depends(get_session)) -> None:
    deleted = profile_service.delete_rule(session, rule_id)
    if not deleted:
        raise not_found("Rule not found.")
