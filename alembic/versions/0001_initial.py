"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-30 00:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=256), nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=True),
        sa.Column("import_id", sa.Integer(), sa.ForeignKey("imports.id"), nullable=True),
        sa.Column("booking_date", sa.Date(), nullable=False),
        sa.Column("booking_datetime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("merchant", sa.String(length=256), nullable=False, server_default=""),
        sa.Column("title", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("raw_category", sa.String(length=128), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=True),
        sa.Column("category_predicted", sa.String(length=32), nullable=True),
        sa.Column("category_confidence", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("dedup_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("dedup_hash", name="uq_transactions_dedup_hash"),
    )
    op.create_index("ix_transactions_booking_date", "transactions", ["booking_date"])
    op.create_index("ix_transactions_category", "transactions", ["category"])


def downgrade() -> None:
    op.drop_index("ix_transactions_category", table_name="transactions")
    op.drop_index("ix_transactions_booking_date", table_name="transactions")
    op.drop_table("transactions")
    op.drop_table("imports")
    op.drop_table("accounts")
