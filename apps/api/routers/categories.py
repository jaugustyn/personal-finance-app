"""Category catalog endpoints — system + user-defined categories.

System categories (the eight built-in classes) are seeded on first read so
the table is populated even when migrations were skipped (e.g. SQLite tests
that use ``Base.metadata.create_all``).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.db import get_session
from finance.domain.enums import Category
from finance.domain.models import CategoryDef, Transaction

router = APIRouter(prefix="/categories", tags=["categories"])


SYSTEM_CATEGORY_COLORS: dict[str, str] = {
    Category.FOOD.value: "#f59e0b",
    Category.TRANSPORT.value: "#3b82f6",
    Category.SUBSCRIPTIONS.value: "#a855f7",
    Category.HEALTH.value: "#ef4444",
    Category.ENTERTAINMENT.value: "#ec4899",
    Category.HOUSING.value: "#10b981",
    Category.SAVINGS.value: "#14b8a6",
    Category.OTHER.value: "#6b7280",
}


def ensure_system_categories(session: Session) -> None:
    """Seed the eight system categories if they are missing."""
    existing = {
        name for (name,) in session.execute(select(CategoryDef.name)).all()
    }
    added = False
    for name, color in SYSTEM_CATEGORY_COLORS.items():
        if name not in existing:
            session.add(
                CategoryDef(name=name, is_system=True, color=color)
            )
            added = True
    if added:
        session.commit()


class CategoryRow(BaseModel):
    id: int
    name: str
    is_system: bool
    color: str | None
    icon: str | None
    usage_count: int = 0

    model_config = {"from_attributes": True}


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
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
    # Build usage counts in a single grouped query.
    from sqlalchemy import func

    usage: dict[str, int] = {}
    for cat_name, count in session.execute(
        select(Transaction.category, func.count(Transaction.id)).group_by(
            Transaction.category
        )
    ).all():
        if cat_name:
            usage[str(cat_name)] = int(count)
    return [
        CategoryRow(
            id=c.id,
            name=c.name,
            is_system=c.is_system,
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
        raise HTTPException(status_code=422, detail="Category name cannot be empty.")
    existing = session.execute(
        select(CategoryDef).where(CategoryDef.name == name)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Category already exists.")
    cat = CategoryDef(name=name, is_system=False, color=payload.color, icon=payload.icon)
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
        raise HTTPException(status_code=404, detail="Category not found.")
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
        raise HTTPException(status_code=404, detail="Category not found.")
    if cat.is_system:
        raise HTTPException(
            status_code=409, detail="System categories cannot be deleted."
        )
    session.delete(cat)
    session.commit()
