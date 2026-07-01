"""Merchant canonicalization and alias endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.errors import not_found, validation_error
from apps.api.schemas.merchants import (
    MerchantAliasCreate,
    MerchantAliasGroupLabelPatch,
    MerchantAliasRow,
    MerchantAliasSuggestionRow,
    MerchantCandidateRow,
    MerchantCandidateVariantRow,
)
from finance.db import get_session
from finance.transactions import merchants as merchant_service

router = APIRouter(prefix="/merchants", tags=["merchants"])


@router.get("/aliases", response_model=list[MerchantAliasRow])
def list_aliases(session: Session = Depends(get_session)) -> list[MerchantAliasRow]:
    return [
        MerchantAliasRow.model_validate(row)
        for row in merchant_service.list_aliases(session)
    ]


@router.post("/aliases", response_model=list[MerchantAliasRow], status_code=201)
def create_aliases(
    payload: MerchantAliasCreate,
    session: Session = Depends(get_session),
) -> list[MerchantAliasRow]:
    try:
        rows = merchant_service.create_aliases(
            session,
            canonical_label=payload.canonical_label,
            canonical_key=payload.canonical_key,
            aliases=payload.aliases,
        )
    except ValueError as exc:
        raise validation_error(str(exc)) from exc
    return [MerchantAliasRow.model_validate(row) for row in rows]


@router.patch("/aliases/group-label", response_model=list[MerchantAliasRow])
def update_alias_group_label(
    payload: MerchantAliasGroupLabelPatch,
    session: Session = Depends(get_session),
) -> list[MerchantAliasRow]:
    try:
        rows = merchant_service.update_alias_group_label(
            session,
            canonical_key=payload.canonical_key,
            canonical_label=payload.canonical_label,
        )
    except ValueError as exc:
        raise validation_error(str(exc)) from exc
    if not rows:
        raise not_found("Merchant alias group not found.")
    return [MerchantAliasRow.model_validate(row) for row in rows]


@router.delete("/aliases/{alias_id}", status_code=204)
def delete_alias(alias_id: int, session: Session = Depends(get_session)) -> None:
    if not merchant_service.delete_alias(session, alias_id):
        raise not_found("Merchant alias not found.")


@router.get("/suggestions", response_model=list[MerchantAliasSuggestionRow])
def alias_suggestions(
    q: str = Query(min_length=1, max_length=128),
    limit: int = Query(default=10, ge=1, le=30),
    session: Session = Depends(get_session),
) -> list[MerchantAliasSuggestionRow]:
    return [
        MerchantAliasSuggestionRow(
            alias_key=row.alias_key,
            alias_label=row.alias_label,
            canonical_key=row.canonical_key,
            canonical_label=row.canonical_label,
            count=row.count,
            total_amount=row.total_amount,
        )
        for row in merchant_service.alias_suggestions(session, q=q, limit=limit)
    ]


@router.get("/candidates", response_model=list[MerchantCandidateRow])
def alias_candidates(
    session: Session = Depends(get_session),
    min_variants: int = Query(default=2, ge=2, le=20),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[MerchantCandidateRow]:
    return [
        MerchantCandidateRow(
            canonical_key=row.canonical_key,
            suggested_label=row.suggested_label,
            aliases=row.aliases,
            variants=[
                MerchantCandidateVariantRow(
                    alias_key=variant.alias_key,
                    alias_label=variant.alias_label,
                    count=variant.count,
                    total_debit=variant.total_debit,
                )
                for variant in row.variants
            ],
            count=row.count,
            total_debit=row.total_debit,
        )
        for row in merchant_service.alias_candidates(
            session,
            min_variants=min_variants,
            limit=limit,
        )
    ]
