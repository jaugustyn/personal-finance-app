"""categories table + is_transfer flag

Revision ID: 0003_categories
Revises: 0001_initial
Create Date: 2026-05-01 12:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_categories"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SYSTEM_CATEGORIES = [
    ("food", "#f59e0b"),
    ("transport", "#3b82f6"),
    ("subscriptions", "#a855f7"),
    ("health", "#ef4444"),
    ("entertainment", "#ec4899"),
    ("housing", "#10b981"),
    ("savings", "#14b8a6"),
    ("other", "#6b7280"),
]


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("color", sa.String(length=16), nullable=True),
        sa.Column("icon", sa.String(length=32), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("name", name="uq_categories_name"),
    )

    op.add_column(
        "transactions",
        sa.Column(
            "is_transfer",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_index(
        "ix_transactions_is_transfer", "transactions", ["is_transfer"]
    )

    # Seed the eight built-in categories.
    categories = sa.table(
        "categories",
        sa.column("name", sa.String),
        sa.column("is_system", sa.Boolean),
        sa.column("color", sa.String),
    )
    op.bulk_insert(
        categories,
        [
            {"name": name, "is_system": True, "color": color}
            for name, color in SYSTEM_CATEGORIES
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_is_transfer", table_name="transactions")
    op.drop_column("transactions", "is_transfer")
    op.drop_table("categories")
