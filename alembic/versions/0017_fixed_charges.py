"""Planned fixed charges.

Revision ID: 0017_fixed_charges
Revises: 0016_app_lock
Create Date: 2026-07-20 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0017_fixed_charges"
down_revision: str | None = "0016_app_lock"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fixed_charges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("cadence", sa.String(length=16), nullable=False),
        sa.Column("anchor_date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "amount > 0",
            name="ck_fixed_charges_amount_positive",
        ),
        sa.CheckConstraint(
            "cadence IN ('monthly', 'quarterly', 'semiannual', 'yearly')",
            name="ck_fixed_charges_cadence",
        ),
    )
    op.create_index(
        "ix_fixed_charges_active_anchor",
        "fixed_charges",
        ["active", "anchor_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_fixed_charges_active_anchor", table_name="fixed_charges")
    op.drop_table("fixed_charges")
