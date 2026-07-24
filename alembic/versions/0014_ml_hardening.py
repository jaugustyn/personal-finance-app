"""ML label provenance and model lifecycle

Revision ID: 0014_ml_hardening
Revises: 0013_subscription_preferences
Create Date: 2026-07-11 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014_ml_hardening"
down_revision: str | None = "0013_subscription_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("transactions", sa.Column("category_confirmation_method", sa.String(32)))
    op.add_column("transactions", sa.Column("category_confirmed_at", sa.DateTime(timezone=True)))
    op.add_column("transactions", sa.Column("category_origin_ref", sa.String(255)))
    op.add_column("transactions", sa.Column("category_predicted_ref", sa.String(255)))
    op.create_index(
        "ix_transactions_category_confirmation_method",
        "transactions",
        ["category_confirmation_method"],
    )

    op.add_column("ml_feedback_events", sa.Column("previous_category", sa.String(32)))
    op.add_column("ml_feedback_events", sa.Column("confirmation_method", sa.String(32)))
    op.add_column("ml_feedback_events", sa.Column("origin_ref", sa.String(255)))

    op.create_table(
        "ml_evaluation_sets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("ontology_version", sa.String(32), nullable=False),
        sa.Column("dataset_fingerprint", sa.String(64), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("invalidated_at", sa.DateTime(timezone=True)),
        sa.Column("invalidation_reason", sa.String(512)),
        sa.CheckConstraint(
            "status IN ('active', 'invalidated')",
            name="ck_ml_evaluation_sets_status",
        ),
    )
    op.create_index("ix_ml_evaluation_sets_status", "ml_evaluation_sets", ["status"])
    op.create_index(
        "uq_ml_evaluation_sets_one_active",
        "ml_evaluation_sets",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "ml_training_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("execution_slot", sa.Integer()),
        sa.Column("requested_variants", sa.JSON(), nullable=False),
        sa.Column("dataset_fingerprint", sa.String(64)),
        sa.Column(
            "evaluation_set_id",
            sa.String(36),
            sa.ForeignKey("ml_evaluation_sets.id", ondelete="SET NULL"),
        ),
        sa.Column("report_path", sa.String(512)),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("message", sa.String(512)),
        sa.Column("error", sa.String(2048)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("execution_slot", name="uq_ml_training_jobs_execution_slot"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'interrupted')",
            name="ck_ml_training_jobs_status",
        ),
        sa.CheckConstraint(
            "(status IN ('queued', 'running') AND execution_slot = 1) OR "
            "(status NOT IN ('queued', 'running') AND execution_slot IS NULL)",
            name="ck_ml_training_jobs_execution_slot",
        ),
    )
    op.create_index("ix_ml_training_jobs_status", "ml_training_jobs", ["status"])

    op.create_table(
        "ml_model_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "job_id",
            sa.String(36),
            sa.ForeignKey("ml_training_jobs.id", ondelete="SET NULL"),
        ),
        sa.Column("estimator", sa.String(64), nullable=False),
        sa.Column("feature_set", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("artifact_path", sa.String(512), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("dataset_fingerprint", sa.String(64), nullable=False),
        sa.Column(
            "evaluation_set_id",
            sa.String(36),
            sa.ForeignKey("ml_evaluation_sets.id", ondelete="SET NULL"),
        ),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("gates", sa.JSON(), nullable=False),
        sa.Column("confidence_policy", sa.JSON(), nullable=False),
        sa.Column("promotable", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('candidate', 'active', 'archived', 'rejected')",
            name="ck_ml_model_versions_status",
        ),
    )
    op.create_index("ix_ml_model_versions_status", "ml_model_versions", ["status"])
    op.create_index("ix_ml_model_versions_job_id", "ml_model_versions", ["job_id"])
    op.create_index(
        "uq_ml_model_versions_one_active",
        "ml_model_versions",
        ["status"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "ml_evaluation_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "evaluation_set_id",
            sa.String(36),
            sa.ForeignKey("ml_evaluation_sets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "transaction_id",
            sa.Integer(),
            sa.ForeignKey("transactions.id", ondelete="SET NULL"),
        ),
        sa.Column("split", sa.String(24), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("booking_date", sa.Date(), nullable=False),
        sa.Column("merchant_hash", sa.String(64), nullable=False),
        sa.UniqueConstraint(
            "evaluation_set_id",
            "transaction_id",
            "split",
            name="uq_ml_eval_member",
        ),
    )
    op.create_index(
        "ix_ml_eval_members_transaction_id",
        "ml_evaluation_members",
        ["transaction_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ml_eval_members_transaction_id", table_name="ml_evaluation_members")
    op.drop_table("ml_evaluation_members")
    op.drop_index("uq_ml_model_versions_one_active", table_name="ml_model_versions")
    op.drop_index("ix_ml_model_versions_job_id", table_name="ml_model_versions")
    op.drop_index("ix_ml_model_versions_status", table_name="ml_model_versions")
    op.drop_table("ml_model_versions")
    op.drop_index("ix_ml_training_jobs_status", table_name="ml_training_jobs")
    op.drop_table("ml_training_jobs")
    op.drop_index("uq_ml_evaluation_sets_one_active", table_name="ml_evaluation_sets")
    op.drop_index("ix_ml_evaluation_sets_status", table_name="ml_evaluation_sets")
    op.drop_table("ml_evaluation_sets")
    op.drop_column("ml_feedback_events", "origin_ref")
    op.drop_column("ml_feedback_events", "confirmation_method")
    op.drop_column("ml_feedback_events", "previous_category")
    op.drop_index("ix_transactions_category_confirmation_method", table_name="transactions")
    op.drop_column("transactions", "category_predicted_ref")
    op.drop_column("transactions", "category_origin_ref")
    op.drop_column("transactions", "category_confirmed_at")
    op.drop_column("transactions", "category_confirmation_method")
