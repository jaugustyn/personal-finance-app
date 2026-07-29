"""User profile and personal rule endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.errors import not_found, service_unavailable, validation_error
from apps.api.schemas.profile import (
    AssistantSettingsRow,
    AssistantSettingsUpdate,
    PersonalRuleCreate,
    PersonalRuleRow,
    PersonalRuleUpdate,
)
from finance.config import get_settings
from finance.db import get_session
from finance.llm.client import OllamaUnavailable
from finance.llm.client import installed_models as ollama_models
from finance.profile import service as profile_service

router = APIRouter(prefix="/profile", tags=["profile"])


def _assistant_settings(
    session: Session,
    *,
    known_models: list[str] | None = None,
) -> AssistantSettingsRow:
    settings = get_settings()
    configuration_enabled = settings.llm_enabled
    user_enabled = profile_service.is_assistant_llm_enabled(session)
    model = profile_service.get_assistant_llm_model(session) or settings.ollama_model
    available_models: list[str] = []
    if configuration_enabled and user_enabled:
        if known_models is not None:
            available_models = known_models
        else:
            try:
                available_models = ollama_models()
            except OllamaUnavailable:
                available_models = []
    available = model in available_models
    return AssistantSettingsRow(
        user_enabled=user_enabled,
        configuration_enabled=configuration_enabled,
        ollama_available=available,
        mode=(
            "hybrid"
            if configuration_enabled and user_enabled and available
            else "deterministic"
        ),
        model=model,
        available_models=available_models,
    )


@router.get("/assistant", response_model=AssistantSettingsRow)
def get_assistant_settings(
    session: Session = Depends(get_session),
) -> AssistantSettingsRow:
    return _assistant_settings(session)


@router.put("/assistant", response_model=AssistantSettingsRow)
def update_assistant_settings(
    payload: AssistantSettingsUpdate,
    session: Session = Depends(get_session),
) -> AssistantSettingsRow:
    available_models: list[str] | None = None
    model = payload.model.strip() if payload.model is not None else None
    if model is not None:
        if not get_settings().llm_enabled:
            raise validation_error("The local model is disabled by server configuration.")
        try:
            available_models = ollama_models()
        except OllamaUnavailable as exc:
            raise service_unavailable("Ollama is unavailable.") from exc
        if model not in available_models:
            raise validation_error("The selected model is not installed in Ollama.")
    try:
        profile_service.set_assistant_llm_preferences(
            session,
            enabled=payload.enabled,
            model=model,
        )
    except ValueError as exc:
        raise validation_error(str(exc)) from exc
    return _assistant_settings(session, known_models=available_models)


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
