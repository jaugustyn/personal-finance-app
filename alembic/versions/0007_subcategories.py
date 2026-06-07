"""two-level taxonomy: category parent + transaction subcategory

Adds an optional subcategory refinement layer on top of the eight ML category
groups. ``categories.parent`` links a subcategory to one of the eight system
groups; ``transactions.subcategory`` stores the user/rule-assigned refinement.
The ML classifier keeps predicting the eight parent groups, so training labels
and metrics are unaffected by this migration.

Revision ID: 0007_subcategories
Revises: 0006_profile_personal_rules
Create Date: 2026-05-30 00:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_subcategories"
down_revision: str | None = "0006_profile_personal_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_SYSTEM_CATEGORY_COLORS: dict[str, str] = {
    "food": "#f59e0b",
    "transport": "#3b82f6",
    "subscriptions": "#a855f7",
    "health": "#ef4444",
    "entertainment": "#ec4899",
    "housing": "#10b981",
    "savings": "#14b8a6",
    "other": "#6b7280",
}

_SYSTEM_SUBCATEGORIES: dict[str, tuple[str, ...]] = {
    "food": ("groceries", "dining_out", "fast_food", "alcohol"),
    "transport": ("fuel", "public_transport", "taxi", "parking", "vehicle"),
    "subscriptions": (
        "streaming",
        "software",
        "telecom",
        "gym_membership",
    ),
    "health": ("pharmacy", "doctor", "dental", "health_insurance"),
    "entertainment": ("events", "games", "hobbies", "books_media", "sports"),
    "housing": ("rent", "mortgage", "utilities", "internet", "repairs"),
    "savings": ("deposit", "investment", "retirement", "emergency_fund"),
    "other": ("fees", "taxes", "gifts", "charity", "misc"),
}


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("parent", sa.String(length=64), nullable=True),
    )
    op.create_index("ix_categories_parent", "categories", ["parent"])
    op.add_column(
        "transactions",
        sa.Column("subcategory", sa.String(length=64), nullable=True),
    )

    categories = sa.table(
        "categories",
        sa.column("name", sa.String),
        sa.column("is_system", sa.Boolean),
        sa.column("parent", sa.String),
        sa.column("color", sa.String),
    )
    rows = [
        {
            "name": sub,
            "is_system": True,
            "parent": parent,
            "color": _SYSTEM_CATEGORY_COLORS[parent],
        }
        for parent, subs in _SYSTEM_SUBCATEGORIES.items()
        for sub in subs
    ]
    if rows:
        op.bulk_insert(categories, rows)


def downgrade() -> None:
    subcategory_names = tuple(
        sub for subs in _SYSTEM_SUBCATEGORIES.values() for sub in subs
    )
    categories = sa.table(
        "categories",
        sa.column("name", sa.String),
    )
    op.execute(
        categories.delete().where(categories.c.name.in_(subcategory_names))
    )
    op.drop_column("transactions", "subcategory")
    op.drop_index("ix_categories_parent", table_name="categories")
    op.drop_column("categories", "parent")
