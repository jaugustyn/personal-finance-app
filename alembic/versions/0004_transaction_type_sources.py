"""transaction type and category sources

Revision ID: 0004_transaction_type_sources
Revises: 0003_categories
Create Date: 2026-05-16 00:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_transaction_type_sources"
down_revision: str | None = "0003_categories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "transaction_type",
            sa.String(length=32),
            nullable=False,
            server_default="purchase",
        ),
    )
    op.add_column(
        "transactions",
        sa.Column("category_source", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("category_predicted_source", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_transactions_transaction_type",
        "transactions",
        ["transaction_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_transaction_type", table_name="transactions")
    op.drop_column("transactions", "category_predicted_source")
    op.drop_column("transactions", "category_source")
    op.drop_column("transactions", "transaction_type")
