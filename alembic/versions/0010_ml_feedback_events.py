"""ml feedback events

Revision ID: 0010_ml_feedback_events
Revises: 0009_shopping_income_taxonomy
Create Date: 2026-06-05 00:00:00

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_ml_feedback_events"
down_revision: str | None = "0009_shopping_income_taxonomy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ml_feedback_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "transaction_id",
            sa.Integer(),
            sa.ForeignKey("transactions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("entity_type", sa.String(length=48), nullable=True),
        sa.Column("entity_key", sa.String(length=255), nullable=True),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("predicted_category", sa.String(length=32), nullable=True),
        sa.Column("final_category", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column("model_artifact", sa.String(length=256), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_ml_feedback_events_transaction_id",
        "ml_feedback_events",
        ["transaction_id"],
    )
    op.create_index(
        "ix_ml_feedback_event_type",
        "ml_feedback_events",
        ["event_type"],
    )
    op.create_index(
        "ix_ml_feedback_created_at",
        "ml_feedback_events",
        ["created_at"],
    )
    op.create_index(
        "ix_ml_feedback_predicted_category",
        "ml_feedback_events",
        ["predicted_category"],
    )
    op.create_index(
        "ix_ml_feedback_entity",
        "ml_feedback_events",
        ["entity_type", "entity_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_ml_feedback_entity", table_name="ml_feedback_events")
    op.drop_index("ix_ml_feedback_predicted_category", table_name="ml_feedback_events")
    op.drop_index("ix_ml_feedback_created_at", table_name="ml_feedback_events")
    op.drop_index("ix_ml_feedback_event_type", table_name="ml_feedback_events")
    op.drop_index("ix_ml_feedback_events_transaction_id", table_name="ml_feedback_events")
    op.drop_table("ml_feedback_events")
