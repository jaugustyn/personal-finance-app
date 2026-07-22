"""Manual transaction links for fixed-charge occurrences.

Revision ID: 0018_fixed_charge_transactions
Revises: 0017_fixed_charges
Create Date: 2026-07-20 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0018_fixed_charge_transactions"
down_revision: str | None = "0017_fixed_charges"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fixed_charge_transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "fixed_charge_id",
            sa.Integer(),
            sa.ForeignKey("fixed_charges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "transaction_id",
            sa.Integer(),
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scheduled_due_date", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "transaction_id",
            name="uq_fixed_charge_transactions_transaction",
        ),
    )
    op.create_index(
        "ix_fixed_charge_transactions_charge_due",
        "fixed_charge_transactions",
        ["fixed_charge_id", "scheduled_due_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_fixed_charge_transactions_charge_due",
        table_name="fixed_charge_transactions",
    )
    op.drop_table("fixed_charge_transactions")
