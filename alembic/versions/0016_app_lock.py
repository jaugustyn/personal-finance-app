"""Optional application lock settings.

Revision ID: 0016_app_lock
Revises: 0015_transaction_type_ontology
Create Date: 2026-07-19 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0016_app_lock"
down_revision: str | None = "0015_transaction_type_ontology"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_profile",
        sa.Column("app_lock_secret_hash", sa.String(255), nullable=True),
    )
    op.add_column(
        "user_profile",
        sa.Column(
            "app_lock_timeout_minutes",
            sa.Integer(),
            nullable=False,
            server_default="15",
        ),
    )


def downgrade() -> None:
    op.drop_column("user_profile", "app_lock_timeout_minutes")
    op.drop_column("user_profile", "app_lock_secret_hash")
