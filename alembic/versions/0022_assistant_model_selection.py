"""Optional local model selection for the assistant.

Revision ID: 0022_assistant_model_selection
Revises: 0021_assistant_preferences
Create Date: 2026-07-29 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0022_assistant_model_selection"
down_revision: str | None = "0021_assistant_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_profile",
        sa.Column("assistant_llm_model", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_profile", "assistant_llm_model")
