"""merchant aliases

Revision ID: 0011_merchant_aliases
Revises: 0010_ml_feedback_events
Create Date: 2026-06-27 00:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_merchant_aliases"
down_revision: str | None = "0010_ml_feedback_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "merchant_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alias_key", sa.String(length=256), nullable=False),
        sa.Column("alias_label", sa.String(length=256), nullable=False),
        sa.Column("canonical_key", sa.String(length=256), nullable=False),
        sa.Column("canonical_label", sa.String(length=256), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("alias_key", name="uq_merchant_aliases_alias_key"),
    )
    op.create_index(
        "ix_merchant_aliases_canonical_key",
        "merchant_aliases",
        ["canonical_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_merchant_aliases_canonical_key", table_name="merchant_aliases")
    op.drop_table("merchant_aliases")
