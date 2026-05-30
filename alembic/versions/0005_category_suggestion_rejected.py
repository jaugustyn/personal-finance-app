"""category suggestion rejection flag

Revision ID: 0005_cat_suggestion_rejected
Revises: 0004_transaction_type_sources
Create Date: 2026-05-17 00:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_cat_suggestion_rejected"
down_revision: str | None = "0004_transaction_type_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "category_suggestion_rejected",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("transactions", "category_suggestion_rejected")
