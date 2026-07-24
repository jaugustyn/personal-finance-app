"""currency layer

Revision ID: 0012_currency_layer
Revises: 0011_merchant_aliases
Create Date: 2026-06-27 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_currency_layer"
down_revision: str | None = "0011_merchant_aliases"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fx_rates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("base_currency", sa.String(length=3), nullable=False),
        sa.Column("rate_date", sa.Date(), nullable=False),
        sa.Column("rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("source", sa.String(length=32), server_default="manual", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "currency",
            "base_currency",
            "rate_date",
            name="uq_fx_rates_currency_base_date",
        ),
    )
    op.add_column(
        "transactions",
        sa.Column("amount_base", sa.Numeric(14, 2), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("base_currency", sa.String(length=3), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("fx_rate", sa.Numeric(18, 8), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("fx_rate_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("fx_rate_source", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("transactions", "fx_rate_source")
    op.drop_column("transactions", "fx_rate_date")
    op.drop_column("transactions", "fx_rate")
    op.drop_column("transactions", "base_currency")
    op.drop_column("transactions", "amount_base")
    op.drop_table("fx_rates")
