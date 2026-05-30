"""assets

Revision ID: 0002_assets
Revises: 0001_initial
Create Date: 2026-05-01 00:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_assets"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("asset_class", sa.String(length=16), nullable=False, server_default="equity"),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("quantity", sa.Numeric(20, 8), nullable=False, server_default="0"),
        sa.Column("cost_basis", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("symbol", name="uq_assets_symbol"),
    )

    op.create_table(
        "asset_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("price", sa.Numeric(20, 8), nullable=False),
        sa.Column("value_pln", sa.Numeric(14, 2), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="yfinance"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("asset_id", "snapshot_date", name="uq_asset_snapshot_date"),
    )
    op.create_index("ix_asset_snapshots_date", "asset_snapshots", ["snapshot_date"])


def downgrade() -> None:
    op.drop_index("ix_asset_snapshots_date", table_name="asset_snapshots")
    op.drop_table("asset_snapshots")
    op.drop_table("assets")
