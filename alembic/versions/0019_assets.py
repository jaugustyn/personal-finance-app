"""Asset accounts, items and valuation history.

Revision ID: 0019_assets
Revises: 0018_fixed_charge_transactions
Create Date: 2026-07-24 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0019_assets"
down_revision: str | None = "0018_fixed_charge_transactions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "asset_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("institution", sa.String(128), nullable=True),
        sa.Column("kind", sa.String(24), nullable=False),
        sa.Column("wrapper", sa.String(16), nullable=False, server_default="standard"),
        sa.Column("tracking_mode", sa.String(16), nullable=False),
        sa.Column("default_currency", sa.String(3), nullable=False, server_default="PLN"),
        sa.Column("notes", sa.String(1024), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "kind IN ('bank', 'brokerage', 'retirement', 'crypto', 'physical', 'other')",
            name="ck_asset_accounts_kind",
        ),
        sa.CheckConstraint(
            "wrapper IN ('standard', 'ike', 'ikze', 'ppk')",
            name="ck_asset_accounts_wrapper",
        ),
        sa.CheckConstraint(
            "tracking_mode IN ('aggregate', 'detailed')",
            name="ck_asset_accounts_tracking_mode",
        ),
        sa.CheckConstraint(
            "wrapper = 'standard' OR kind = 'retirement'",
            name="ck_asset_accounts_retirement_wrapper",
        ),
    )
    op.create_index("ix_asset_accounts_archived_at", "asset_accounts", ["archived_at"])

    op.create_table(
        "asset_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "account_id",
            sa.Integer(),
            sa.ForeignKey("asset_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("asset_type", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("symbol", sa.String(32), nullable=True),
        sa.Column("isin", sa.String(12), nullable=True),
        sa.Column("review_interval_days", sa.Integer(), nullable=True, server_default="30"),
        sa.Column("notes", sa.String(1024), nullable=True),
        sa.Column("is_aggregate_summary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "asset_type IN ('cash', 'savings_account', 'deposit', 'bond', 'stock', "
            "'etf', 'fund', 'crypto', 'precious_metal', 'loan_receivable', 'other')",
            name="ck_asset_items_type",
        ),
        sa.CheckConstraint(
            "review_interval_days IS NULL OR review_interval_days IN (7, 30, 90, 180)",
            name="ck_asset_items_review_interval",
        ),
    )
    op.create_index(
        "ix_asset_items_account_archived",
        "asset_items",
        ["account_id", "archived_at"],
    )
    op.create_index(
        "uq_asset_items_aggregate_summary",
        "asset_items",
        ["account_id"],
        unique=True,
        postgresql_where=sa.text("is_aggregate_summary = true"),
        sqlite_where=sa.text("is_aggregate_summary = 1"),
    )

    op.create_table(
        "asset_valuations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("asset_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("valuation_date", sa.Date(), nullable=False),
        sa.Column("input_mode", sa.String(16), nullable=False),
        sa.Column("total_value", sa.Numeric(20, 8), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 8), nullable=True),
        sa.Column("unit_price", sa.Numeric(20, 8), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("amount_pln", sa.Numeric(20, 2), nullable=True),
        sa.Column("fx_rate", sa.Numeric(18, 8), nullable=True),
        sa.Column("fx_rate_date", sa.Date(), nullable=True),
        sa.Column("fx_rate_source", sa.String(32), nullable=True),
        sa.Column("growth_mode", sa.String(16), nullable=False, server_default="none"),
        sa.Column("annual_rate_percent", sa.Numeric(10, 4), nullable=True),
        sa.Column("compounding", sa.String(16), nullable=True),
        sa.Column("growth_end_date", sa.Date(), nullable=True),
        sa.Column("source", sa.String(32), nullable=False, server_default="manual"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("item_id", "valuation_date", name="uq_asset_valuations_item_date"),
        sa.CheckConstraint(
            "input_mode IN ('total', 'unit_price')",
            name="ck_asset_valuations_input_mode",
        ),
        sa.CheckConstraint(
            "growth_mode IN ('none', 'fixed_rate')",
            name="ck_asset_valuations_growth_mode",
        ),
        sa.CheckConstraint(
            "compounding IS NULL OR compounding IN ('simple', 'daily', 'monthly', 'yearly')",
            name="ck_asset_valuations_compounding",
        ),
        sa.CheckConstraint("total_value >= 0", name="ck_asset_valuations_total_nonnegative"),
        sa.CheckConstraint(
            "(input_mode = 'total' AND quantity IS NULL AND unit_price IS NULL) OR "
            "(input_mode = 'unit_price' AND quantity IS NOT NULL AND quantity >= 0 "
            "AND unit_price IS NOT NULL AND unit_price >= 0)",
            name="ck_asset_valuations_input_values",
        ),
        sa.CheckConstraint(
            "(growth_mode = 'none' AND annual_rate_percent IS NULL AND compounding IS NULL "
            "AND growth_end_date IS NULL) OR "
            "(growth_mode = 'fixed_rate' AND annual_rate_percent IS NOT NULL "
            "AND annual_rate_percent > -100 AND annual_rate_percent <= 1000 "
            "AND compounding IS NOT NULL)",
            name="ck_asset_valuations_growth_values",
        ),
        sa.CheckConstraint(
            "amount_pln IS NULL OR amount_pln >= 0",
            name="ck_asset_valuations_amount_pln_nonnegative",
        ),
    )


def downgrade() -> None:
    op.drop_table("asset_valuations")
    op.drop_index("uq_asset_items_aggregate_summary", table_name="asset_items")
    op.drop_index("ix_asset_items_account_archived", table_name="asset_items")
    op.drop_table("asset_items")
    op.drop_index("ix_asset_accounts_archived_at", table_name="asset_accounts")
    op.drop_table("asset_accounts")
