"""transaction tags and notes

Revision ID: 0008_transaction_tags_notes
Revises: 0007_subcategories
Create Date: 2026-05-29 00:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_transaction_tags_notes"
down_revision: str | None = "0007_subcategories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("notes", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("tags", sa.JSON(), server_default="[]", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("transactions", "tags")
    op.drop_column("transactions", "notes")
