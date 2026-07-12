"""Transaction type ontology and provenance.

Revision ID: 0015_transaction_type_ontology
Revises: 0014_ml_hardening
Create Date: 2026-07-12 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015_transaction_type_ontology"
down_revision: str | None = "0014_ml_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("raw_transaction_type", sa.String(128)))
    op.alter_column(
        "transactions",
        "transaction_type",
        existing_type=sa.String(32),
        nullable=True,
        server_default=None,
    )
    op.add_column("transactions", sa.Column("transaction_type_source", sa.String(32)))
    op.add_column(
        "transactions", sa.Column("transaction_type_confirmation_method", sa.String(32))
    )
    op.add_column(
        "transactions", sa.Column("transaction_type_confirmed_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "transactions", sa.Column("transaction_type_origin_ref", sa.String(255))
    )
    op.add_column(
        "transactions", sa.Column("transaction_type_predicted", sa.String(32))
    )
    op.add_column(
        "transactions", sa.Column("transaction_type_confidence", sa.Float())
    )
    op.add_column(
        "transactions", sa.Column("transaction_type_predicted_source", sa.String(32))
    )
    op.add_column(
        "transactions", sa.Column("transaction_type_predicted_ref", sa.String(255))
    )
    op.create_index(
        "ix_transactions_transaction_type_confirmation_method",
        "transactions",
        ["transaction_type_confirmation_method"],
    )

    op.add_column(
        "ml_feedback_events", sa.Column("predicted_transaction_type", sa.String(32))
    )
    op.add_column(
        "ml_feedback_events", sa.Column("previous_transaction_type", sa.String(32))
    )
    op.add_column(
        "ml_feedback_events", sa.Column("final_transaction_type", sa.String(32))
    )


def downgrade() -> None:
    op.drop_column("ml_feedback_events", "final_transaction_type")
    op.drop_column("ml_feedback_events", "previous_transaction_type")
    op.drop_column("ml_feedback_events", "predicted_transaction_type")

    op.drop_index(
        "ix_transactions_transaction_type_confirmation_method",
        table_name="transactions",
    )
    op.drop_column("transactions", "transaction_type_predicted_ref")
    op.drop_column("transactions", "transaction_type_predicted_source")
    op.drop_column("transactions", "transaction_type_confidence")
    op.drop_column("transactions", "transaction_type_predicted")
    op.drop_column("transactions", "transaction_type_origin_ref")
    op.drop_column("transactions", "transaction_type_confirmed_at")
    op.drop_column("transactions", "transaction_type_confirmation_method")
    op.drop_column("transactions", "transaction_type_source")
    op.alter_column(
        "transactions",
        "transaction_type",
        existing_type=sa.String(32),
        nullable=False,
        server_default="purchase",
    )
    op.drop_column("transactions", "raw_transaction_type")
