"""user profile and personal rules

Revision ID: 0006_profile_personal_rules
Revises: 0005_cat_suggestion_rejected
Create Date: 2026-05-17 00:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_profile_personal_rules"
down_revision: str | None = "0005_cat_suggestion_rejected"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_profile",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("base_currency", sa.String(length=3), server_default="PLN", nullable=False),
        sa.Column("salary_day", sa.Integer(), nullable=True),
        sa.Column("monthly_savings_goal", sa.Numeric(14, 2), nullable=True),
        sa.Column("category_limits", sa.JSON(), server_default="{}", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "personal_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pattern", sa.String(length=256), nullable=False),
        sa.Column("pattern_norm", sa.String(length=256), nullable=False),
        sa.Column("pattern_target", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=True),
        sa.Column("transaction_type", sa.String(length=32), nullable=True),
        sa.Column("is_transfer", sa.Boolean(), nullable=True),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("mode", sa.String(length=16), server_default="suggest_only", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0.95", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_personal_rules_pattern_norm", "personal_rules", ["pattern_norm"])
    op.create_index(
        "ix_personal_rules_active_priority",
        "personal_rules",
        ["active", "priority"],
    )


def downgrade() -> None:
    op.drop_index("ix_personal_rules_active_priority", table_name="personal_rules")
    op.drop_index("ix_personal_rules_pattern_norm", table_name="personal_rules")
    op.drop_table("personal_rules")
    op.drop_table("user_profile")
