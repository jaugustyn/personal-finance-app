"""subscription preferences

Revision ID: 0013_subscription_preferences
Revises: 0012_currency_layer
Create Date: 2026-06-28 00:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0013_subscription_preferences"
down_revision: str | None = "0012_currency_layer"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "subscription_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_key", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=256), nullable=True),
        sa.Column("cadence_override", sa.String(length=32), nullable=True),
        sa.Column("confirmed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("ignored", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "subscription_key",
            name="uq_subscription_preferences_key",
        ),
    )
    op.create_index(
        "ix_subscription_preferences_key",
        "subscription_preferences",
        ["subscription_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_subscription_preferences_key", table_name="subscription_preferences")
    op.drop_table("subscription_preferences")
