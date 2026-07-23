"""HTTP adapter for the category catalog."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.errors import conflict, not_found, validation_error
from apps.api.schemas.categories import CategoryCreate, CategoryRow, CategoryUpdate
from finance.categories import service
from finance.db import get_session

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryRow])
def list_categories(session: Session = Depends(get_session)) -> list[CategoryRow]:
    return [CategoryRow(**row.__dict__) for row in service.list_categories(session)]


@router.post("", response_model=CategoryRow, status_code=201)
def create_category(
    payload: CategoryCreate,
    session: Session = Depends(get_session),
) -> CategoryRow:
    try:
        category = service.create_category(session, **payload.model_dump())
    except service.CategoryAlreadyExists as exc:
        raise conflict(str(exc)) from exc
    except service.CategoryValidationError as exc:
        raise validation_error(str(exc)) from exc
    return CategoryRow.model_validate(category)


@router.patch("/{category_id}", response_model=CategoryRow)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    session: Session = Depends(get_session),
) -> CategoryRow:
    try:
        category = service.update_category(session, category_id, **payload.model_dump())
    except service.CategoryNotFound as exc:
        raise not_found(str(exc)) from exc
    return CategoryRow.model_validate(category)


@router.delete("/{category_id}", status_code=204, response_model=None)
def delete_category(category_id: int, session: Session = Depends(get_session)) -> None:
    try:
        service.delete_category(session, category_id)
    except service.CategoryNotFound as exc:
        raise not_found(str(exc)) from exc
    except service.SystemCategoryDeletionForbidden as exc:
        raise conflict(str(exc)) from exc
    except service.CategoryInUse as exc:
        detail = {
            "code": "category_in_use",
            "message": "Category is in use and cannot be deleted.",
            "transaction_count": exc.transaction_count,
            "rule_count": exc.rule_count,
            "subcategory_count": exc.subcategory_count,
        }
        if exc.fixed_charge_count:
            detail["fixed_charge_count"] = exc.fixed_charge_count
        raise conflict(detail) from exc
