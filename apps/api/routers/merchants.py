"""Merchant canonicalization and alias endpoints."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.errors import conflict, not_found, validation_error
from apps.api.schemas.merchants import (
    MerchantAliasCreate,
    MerchantAliasGroupLabelPatch,
    MerchantAliasRow,
    MerchantAliasSuggestionRow,
    MerchantCandidateRow,
    MerchantCandidateVariantRow,
)
from finance.currencies import BASE_CURRENCY
from finance.db import get_session
from finance.transactions import merchants as merchant_service

router = APIRouter(prefix="/merchants", tags=["merchants"])


def _alias_rows(session: Session, rows: Iterable[object]) -> list[MerchantAliasRow]:
    serialized = [MerchantAliasRow.model_validate(row) for row in rows]
    usage_stats = merchant_service.alias_usage_stats(
        session,
        (row.alias_key for row in serialized),
    )
    result: list[MerchantAliasRow] = []
    for row in serialized:
        usage = usage_stats[row.alias_key]
        result.append(
            row.model_copy(
                update={
                    "alias_label": merchant_service.compact_merchant_label(
                        row.alias_label
                    ),
                    "canonical_label": merchant_service.compact_merchant_label(
                        row.canonical_label
                    ),
                    "usage_count": usage.count,
                    "total_expenses": usage.total_expenses,
                    "base_currency": BASE_CURRENCY,
                }
            )
        )
    return result


@router.get("/aliases", response_model=list[MerchantAliasRow])
def list_aliases(session: Session = Depends(get_session)) -> list[MerchantAliasRow]:
    return _alias_rows(session, merchant_service.list_aliases(session))


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
    except merchant_service.MerchantAliasConflict as exc:
        raise conflict(str(exc)) from exc
    except ValueError as exc:
        raise validation_error(str(exc)) from exc
    return _alias_rows(session, rows)


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
    return _alias_rows(session, rows)


@router.delete("/aliases/{alias_id}", status_code=204, response_model=None)
def delete_alias(alias_id: int, session: Session = Depends(get_session)) -> None:
    if not merchant_service.delete_alias(session, alias_id):
        raise not_found("Merchant alias not found.")


@router.get("/suggestions", response_model=list[MerchantAliasSuggestionRow])
def alias_suggestions(
    q: str = Query(min_length=1, max_length=128),
    limit: int = Query(default=10, ge=1, le=30),
    session: Session = Depends(get_session),
) -> list[MerchantAliasSuggestionRow]:
    base_currency = BASE_CURRENCY
    return [
        MerchantAliasSuggestionRow(
            alias_key=row.alias_key,
            alias_label=row.alias_label,
            canonical_key=row.canonical_key,
            canonical_label=row.canonical_label,
            count=row.count,
            total_amount=row.total_amount,
            base_currency=base_currency,
        )
        for row in merchant_service.alias_suggestions(session, q=q, limit=limit)
    ]


@router.get("/candidates", response_model=list[MerchantCandidateRow])
def alias_candidates(
    session: Session = Depends(get_session),
    min_variants: int = Query(default=2, ge=2, le=20),
    limit: int = Query(default=100, ge=1, le=100),
    q: str | None = Query(default=None, min_length=1, max_length=128),
    sort_by: Literal[
        "suggested_label",
        "variants",
        "count",
        "total_debit",
    ] = "count",
    sort_dir: Literal["asc", "desc"] = "desc",
) -> list[MerchantCandidateRow]:
    base_currency = BASE_CURRENCY
    return [
        MerchantCandidateRow(
            canonical_key=row.canonical_key,
            canonical_label=row.canonical_label,
            suggested_label=row.suggested_label,
            aliases=row.aliases,
            variants=[
                MerchantCandidateVariantRow(
                    alias_key=variant.alias_key,
                    alias_label=variant.alias_label,
                    count=variant.count,
                    total_debit=variant.total_debit,
                    base_currency=base_currency,
                )
                for variant in row.variants
            ],
            count=row.count,
            total_debit=row.total_debit,
            base_currency=base_currency,
        )
        for row in merchant_service.alias_candidates(
            session,
            min_variants=min_variants,
            limit=limit,
            q=q,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )
    ]
