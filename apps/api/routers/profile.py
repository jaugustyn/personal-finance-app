"""User profile and personal rule endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.errors import not_found, validation_error
from apps.api.schemas.profile import (
    PersonalRuleCreate,
    PersonalRuleRow,
    PersonalRuleUpdate,
)
from finance.db import get_session
from finance.profile import service as profile_service

router = APIRouter(prefix="/profile", tags=["profile"])


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
