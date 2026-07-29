"""Optional local model preference for the assistant.

Revision ID: 0021_assistant_preferences
Revises: 0020_transaction_accounts
Create Date: 2026-07-27 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0021_assistant_preferences"
down_revision: str | None = "0020_transaction_accounts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_profile",
        sa.Column(
            "assistant_llm_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_profile", "assistant_llm_enabled")
