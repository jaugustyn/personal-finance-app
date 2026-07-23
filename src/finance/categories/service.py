"""Application services for the category catalog."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from finance.domain.category_mapping import SYSTEM_CATEGORY_COLORS, SYSTEM_SUBCATEGORIES
from finance.domain.models import CategoryDef, FixedCharge, PersonalRule, Transaction


class CategoryNotFound(LookupError):
    """Raised when a requested category does not exist."""


class CategoryAlreadyExists(ValueError):
    """Raised when a normalized category name is already present."""


class CategoryValidationError(ValueError):
    """Raised when a category hierarchy request is invalid."""


class SystemCategoryDeletionForbidden(ValueError):
    """Raised when deletion of a system category is requested."""


@dataclass(frozen=True)
class CategoryInUse(ValueError):
    transaction_count: int
    rule_count: int
    subcategory_count: int
    fixed_charge_count: int


@dataclass(frozen=True)
class CategoryView:
    id: int
    name: str
    is_system: bool
    parent: str | None
    color: str | None
    icon: str | None
    usage_count: int = 0


def _normalize(name: str) -> str:
    return name.strip().lower()


def _system_category_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for group, color in SYSTEM_CATEGORY_COLORS.items():
        rows.append(
            {"name": group.value, "is_system": True, "parent": None, "color": color}
        )
        rows.extend(
            {
                "name": subcategory,
                "is_system": True,
                "parent": group.value,
                "color": color,
            }
            for subcategory in SYSTEM_SUBCATEGORIES.get(group, ())
        )
    return rows


def missing_system_category_names(session: Session) -> list[str]:
    expected = {str(row["name"]) for row in _system_category_rows()}
    existing = set(
        session.scalars(select(CategoryDef.name).where(CategoryDef.name.in_(expected)))
    )
    return sorted(expected - existing)


def seed_system_categories(session: Session) -> int:
    """Explicitly seed missing system categories without committing.

    Production databases are seeded by Alembic. This helper exists for test and
    controlled bootstrap code; read-side use cases must never call it.
    """
    existing = set(session.scalars(select(CategoryDef.name)))
    rows = [row for row in _system_category_rows() if row["name"] not in existing]
    session.add_all(CategoryDef(**row) for row in rows)
    if rows:
        session.flush()
    return len(rows)


def list_categories(session: Session) -> list[CategoryView]:
    categories = list(
        session.scalars(
            select(CategoryDef).order_by(
                CategoryDef.is_system.desc(), CategoryDef.name.asc()
            )
        )
    )
    usage: dict[str, int] = {}
    for category, count in session.execute(
        select(Transaction.category, func.count(Transaction.id)).group_by(
            Transaction.category
        )
    ):
        if category:
            usage[str(category)] = int(count)
    for subcategory, count in session.execute(
        select(Transaction.subcategory, func.count(Transaction.id)).group_by(
            Transaction.subcategory
        )
    ):
        if subcategory:
            name = str(subcategory)
            usage[name] = usage.get(name, 0) + int(count)
    return [
        CategoryView(
            id=category.id,
            name=category.name,
            is_system=category.is_system,
            parent=category.parent,
            color=category.color,
            icon=category.icon,
            usage_count=usage.get(category.name, 0),
        )
        for category in categories
    ]


def create_category(
    session: Session,
    *,
    name: str,
    parent: str | None,
    color: str | None,
    icon: str | None,
) -> CategoryDef:
    normalized_name = _normalize(name)
    if not normalized_name:
        raise CategoryValidationError("Category name cannot be empty.")
    normalized_parent = _normalize(parent) if parent else None
    if normalized_parent is not None:
        parent_def = session.scalar(
            select(CategoryDef).where(CategoryDef.name == normalized_parent)
        )
        if parent_def is None:
            raise CategoryValidationError("Parent category not found.")
        if parent_def.parent is not None:
            raise CategoryValidationError("Subcategories cannot be nested.")
    if session.scalar(select(CategoryDef.id).where(CategoryDef.name == normalized_name)):
        raise CategoryAlreadyExists("Category already exists.")

    category = CategoryDef(
        name=normalized_name,
        is_system=False,
        parent=normalized_parent,
        color=color,
        icon=icon,
    )
    session.add(category)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise CategoryAlreadyExists("Category already exists.") from exc
    except Exception:
        session.rollback()
        raise
    session.refresh(category)
    return category


def update_category(
    session: Session,
    category_id: int,
    *,
    color: str | None,
    icon: str | None,
) -> CategoryDef:
    category = session.get(CategoryDef, category_id)
    if category is None:
        raise CategoryNotFound("Category not found.")
    if color is not None:
        category.color = color
    if icon is not None:
        category.icon = icon
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(category)
    return category


def delete_category(session: Session, category_id: int) -> None:
    category = session.get(CategoryDef, category_id)
    if category is None:
        raise CategoryNotFound("Category not found.")
    if category.is_system:
        raise SystemCategoryDeletionForbidden("System categories cannot be deleted.")

    transaction_count = int(
        session.scalar(
            select(func.count(Transaction.id)).where(
                or_(
                    Transaction.category == category.name,
                    Transaction.subcategory == category.name,
                    Transaction.category_predicted == category.name,
                )
            )
        )
        or 0
    )
    rule_count = int(
        session.scalar(
            select(func.count(PersonalRule.id)).where(
                PersonalRule.category == category.name
            )
        )
        or 0
    )
    subcategory_count = int(
        session.scalar(
            select(func.count(CategoryDef.id)).where(CategoryDef.parent == category.name)
        )
        or 0
    )
    fixed_charge_count = int(
        session.scalar(
            select(func.count(FixedCharge.id)).where(
                FixedCharge.category == category.name
            )
        )
        or 0
    )
    if transaction_count or rule_count or subcategory_count or fixed_charge_count:
        raise CategoryInUse(
            transaction_count=transaction_count,
            rule_count=rule_count,
            subcategory_count=subcategory_count,
            fixed_charge_count=fixed_charge_count,
        )

    session.delete(category)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
