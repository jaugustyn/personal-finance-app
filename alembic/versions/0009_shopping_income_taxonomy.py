"""shopping category and income transaction type

Revision ID: 0009_shopping_income_taxonomy
Revises: 0008_transaction_tags_notes
Create Date: 2026-06-04 00:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_shopping_income_taxonomy"
down_revision: str | None = "0008_transaction_tags_notes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SHOPPING_COLOR = "#6366f1"
_SHOPPING_SUBCATEGORIES = (
    "online_retail",
    "clothing",
    "electronics",
    "personal_goods",
)


def upgrade() -> None:
    categories = sa.table(
        "categories",
        sa.column("name", sa.String),
        sa.column("is_system", sa.Boolean),
        sa.column("parent", sa.String),
        sa.column("color", sa.String),
    )
    names = ("shopping", *_SHOPPING_SUBCATEGORIES)
    conn = op.get_bind()
    existing = {
        row[0]
        for row in conn.execute(
            sa.select(categories.c.name).where(categories.c.name.in_(names))
        )
    }
    rows = [
        {
            "name": "shopping",
            "is_system": True,
            "parent": None,
            "color": _SHOPPING_COLOR,
        },
        *[
            {
                "name": sub,
                "is_system": True,
                "parent": "shopping",
                "color": _SHOPPING_COLOR,
            }
            for sub in _SHOPPING_SUBCATEGORIES
        ],
    ]
    missing = [row for row in rows if row["name"] not in existing]
    if missing:
        op.bulk_insert(categories, missing)


def downgrade() -> None:
    categories = sa.table(
        "categories",
        sa.column("name", sa.String),
        sa.column("is_system", sa.Boolean),
    )
    op.execute(
        categories.delete().where(
            categories.c.name.in_(("shopping", *_SHOPPING_SUBCATEGORIES)),
            categories.c.is_system.is_(True),
        )
    )
