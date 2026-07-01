"""Category catalog endpoints — system + user-defined categories."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.api.errors import conflict, not_found, validation_error
from finance.db import get_session
from finance.domain.category_mapping import (
    SYSTEM_CATEGORY_COLORS,
    SYSTEM_SUBCATEGORIES,
)
from finance.domain.models import CategoryDef, Transaction

router = APIRouter(prefix="/categories", tags=["categories"])


def ensure_system_categories(session: Session) -> None:
    """Seed the system groups and their subcategories if missing."""
    existing = {
        name for (name,) in session.execute(select(CategoryDef.name)).all()
    }
    added = False
    for group, color in SYSTEM_CATEGORY_COLORS.items():
        if group.value not in existing:
            session.add(
                CategoryDef(name=group.value, is_system=True, color=color)
            )
            added = True
        for sub in SYSTEM_SUBCATEGORIES.get(group, ()):
            if sub not in existing:
                session.add(
                    CategoryDef(
                        name=sub,
                        is_system=True,
                        parent=group.value,
                        color=color,
                    )
                )
                added = True
    if added:
        session.commit()


class CategoryRow(BaseModel):
    id: int
    name: str
    is_system: bool
    parent: str | None = None
    color: str | None
    icon: str | None
    usage_count: int = 0

    model_config = {"from_attributes": True}


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    parent: str | None = Field(default=None, max_length=64)
    color: str | None = Field(default=None, max_length=16)
    icon: str | None = Field(default=None, max_length=32)


class CategoryUpdate(BaseModel):
    color: str | None = Field(default=None, max_length=16)
    icon: str | None = Field(default=None, max_length=32)


def _normalize(name: str) -> str:
    return name.strip().lower()


@router.get("", response_model=list[CategoryRow])
def list_categories(session: Session = Depends(get_session)) -> list[CategoryRow]:
    ensure_system_categories(session)
    rows = session.execute(
        select(CategoryDef).order_by(
            CategoryDef.is_system.desc(), CategoryDef.name.asc()
        )
    ).scalars().all()
    # Build usage counts in single grouped queries: group-level usage comes
    # from ``Transaction.category``; subcategory usage from ``subcategory``.
    from sqlalchemy import func

    usage: dict[str, int] = {}
    for cat_name, count in session.execute(
        select(Transaction.category, func.count(Transaction.id)).group_by(
            Transaction.category
        )
    ).all():
        if cat_name:
            usage[str(cat_name)] = int(count)
    for sub_name, count in session.execute(
        select(Transaction.subcategory, func.count(Transaction.id)).group_by(
            Transaction.subcategory
        )
    ).all():
        if sub_name:
            usage[str(sub_name)] = usage.get(str(sub_name), 0) + int(count)
    return [
        CategoryRow(
            id=c.id,
            name=c.name,
            is_system=c.is_system,
            parent=c.parent,
            color=c.color,
            icon=c.icon,
            usage_count=usage.get(c.name, 0),
        )
        for c in rows
    ]


@router.post("", response_model=CategoryRow, status_code=201)
def create_category(
    payload: CategoryCreate, session: Session = Depends(get_session)
) -> CategoryRow:
    ensure_system_categories(session)
    name = _normalize(payload.name)
    if not name:
        raise validation_error("Category name cannot be empty.")
    parent = _normalize(payload.parent) if payload.parent else None
    if parent is not None:
        parent_def = session.execute(
            select(CategoryDef).where(CategoryDef.name == parent)
        ).scalar_one_or_none()
        if parent_def is None:
            raise validation_error("Parent category not found.")
        if parent_def.parent is not None:
            raise validation_error("Subcategories cannot be nested.")
    existing = session.execute(
        select(CategoryDef).where(CategoryDef.name == name)
    ).scalar_one_or_none()
    if existing is not None:
        raise conflict("Category already exists.")
    cat = CategoryDef(
        name=name,
        is_system=False,
        parent=parent,
        color=payload.color,
        icon=payload.icon,
    )
    session.add(cat)
    session.commit()
    session.refresh(cat)
    return CategoryRow.model_validate(cat)


@router.patch("/{category_id}", response_model=CategoryRow)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    session: Session = Depends(get_session),
) -> CategoryRow:
    cat = session.get(CategoryDef, category_id)
    if cat is None:
        raise not_found("Category not found.")
    if payload.color is not None:
        cat.color = payload.color
    if payload.icon is not None:
        cat.icon = payload.icon
    session.commit()
    session.refresh(cat)
    return CategoryRow.model_validate(cat)


@router.delete("/{category_id}", status_code=204)
def delete_category(
    category_id: int, session: Session = Depends(get_session)
) -> None:
    cat = session.get(CategoryDef, category_id)
    if cat is None:
        raise not_found("Category not found.")
    if cat.is_system:
        raise conflict("System categories cannot be deleted.")
    session.delete(cat)
    session.commit()
