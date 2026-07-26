"""Transactional accounts for imports and transactions.

Revision ID: 0020_transaction_accounts
Revises: 0019_assets
Create Date: 2026-07-26 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0020_transaction_accounts"
down_revision: str | None = "0019_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "accounts",
        sa.Column("kind", sa.String(24), nullable=False, server_default="bank"),
    )
    op.add_column(
        "accounts",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "accounts",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.alter_column("accounts", "source", server_default="unknown")
    op.alter_column("accounts", "currency", server_default="PLN")
    op.create_check_constraint(
        "ck_accounts_kind",
        "accounts",
        "kind IN ('bank', 'savings', 'credit_card', 'cash', 'other')",
    )
    op.create_index(
        "uq_accounts_name_ci",
        "accounts",
        [sa.text("lower(name)")],
        unique=True,
    )

    op.add_column(
        "imports",
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("accounts.id"),
            nullable=False,
        ),
    )
    op.create_index("ix_imports_account_id", "imports", ["account_id"])

    op.drop_constraint("uq_transactions_dedup_hash", "transactions", type_="unique")
    op.alter_column("transactions", "account_id", nullable=False)
    op.create_index("ix_transactions_account_id", "transactions", ["account_id"])
    op.create_unique_constraint(
        "uq_transactions_account_dedup_hash",
        "transactions",
        ["account_id", "dedup_hash"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_transactions_account_dedup_hash",
        "transactions",
        type_="unique",
    )
    op.drop_index("ix_transactions_account_id", table_name="transactions")
    op.alter_column("transactions", "account_id", nullable=True)
    op.create_unique_constraint(
        "uq_transactions_dedup_hash",
        "transactions",
        ["dedup_hash"],
    )

    op.drop_index("ix_imports_account_id", table_name="imports")
    op.drop_column("imports", "account_id")

    op.drop_index("uq_accounts_name_ci", table_name="accounts")
    op.drop_constraint("ck_accounts_kind", "accounts", type_="check")
    op.alter_column("accounts", "currency", server_default=None)
    op.alter_column("accounts", "source", server_default=None)
    op.drop_column("accounts", "updated_at")
    op.drop_column("accounts", "archived_at")
    op.drop_column("accounts", "kind")
