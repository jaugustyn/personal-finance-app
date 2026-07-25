"""SQLAlchemy ORM models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from finance.domain.enums import (
    BankSource,
    Category,
    TransactionDirection,
    TransactionType,
)


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    source: Mapped[BankSource] = mapped_column(String(32))
    currency: Mapped[str] = mapped_column(String(3))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    transactions: Mapped[list[Transaction]] = relationship(back_populates="account")


class Import(Base):
    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[BankSource] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(String(256))
    total_rows: Mapped[int] = mapped_column(default=0)
    inserted: Mapped[int] = mapped_column(default=0)
    duplicates: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    transactions: Mapped[list[Transaction]] = relationship(back_populates="import_")


class CategoryDef(Base):
    """User-manageable category catalog.

    System categories from :class:`Category` are installed by migrations and
    cannot be deleted. Users may add their own. Because transaction and rule
    records store the category name, custom categories referenced by those
    records must not be deleted before the references are reassigned.
    """

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name", name="uq_categories_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    parent: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserProfile(Base):
    """Single-user operational profile for local personalization."""

    __tablename__ = "user_profile"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    base_currency: Mapped[str] = mapped_column(String(3), default="PLN", server_default="PLN")
    salary_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_savings_goal: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    category_limits: Mapped[dict[str, float]] = mapped_column(
        JSON, default=dict, server_default="{}"
    )
    app_lock_secret_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    app_lock_timeout_minutes: Mapped[int] = mapped_column(Integer, default=15, server_default="15")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class FxRate(Base):
    """Historical exchange rate used to convert transaction amounts."""

    __tablename__ = "fx_rates"
    __table_args__ = (
        UniqueConstraint(
            "currency",
            "base_currency",
            "rate_date",
            name="uq_fx_rates_currency_base_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(String(3))
    base_currency: Mapped[str] = mapped_column(String(3))
    rate_date: Mapped[date] = mapped_column()
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    source: Mapped[str] = mapped_column(String(32), default="manual", server_default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PersonalRule(Base):
    """User-defined merchant/title rule used before ML suggestions."""

    __tablename__ = "personal_rules"
    __table_args__ = (Index("ix_personal_rules_active_priority", "active", "priority"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    pattern: Mapped[str] = mapped_column(String(256))
    pattern_norm: Mapped[str] = mapped_column(String(256), index=True)
    pattern_target: Mapped[str] = mapped_column(String(16), default="merchant")
    category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    transaction_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_transfer: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    mode: Mapped[str] = mapped_column(
        String(16), default="suggest_only", server_default="suggest_only"
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.95, server_default="0.95")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MerchantAlias(Base):
    """User-curated merchant alias mapped to a canonical display merchant."""

    __tablename__ = "merchant_aliases"
    __table_args__ = (
        UniqueConstraint("alias_key", name="uq_merchant_aliases_alias_key"),
        Index("ix_merchant_aliases_canonical_key", "canonical_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    alias_key: Mapped[str] = mapped_column(String(256))
    alias_label: Mapped[str] = mapped_column(String(256))
    canonical_key: Mapped[str] = mapped_column(String(256))
    canonical_label: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("dedup_hash", name="uq_transactions_dedup_hash"),
        Index("ix_transactions_booking_date", "booking_date"),
        Index("ix_transactions_category", "category"),
        Index("ix_transactions_import_id", "import_id"),
        Index("ix_transactions_is_transfer", "is_transfer"),
        Index("ix_transactions_transaction_type", "transaction_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    import_id: Mapped[int | None] = mapped_column(ForeignKey("imports.id"), nullable=True)

    booking_date: Mapped[date] = mapped_column()
    booking_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3))
    amount_base: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    base_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    fx_rate_date: Mapped[date | None] = mapped_column(nullable=True)
    fx_rate_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    direction: Mapped[TransactionDirection] = mapped_column(String(8))

    merchant: Mapped[str] = mapped_column(String(256), default="")
    title: Mapped[str] = mapped_column(String(512), default="")

    raw_category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    raw_transaction_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    category: Mapped[Category | None] = mapped_column(String(32), nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    category_confirmation_method: Mapped[str | None] = mapped_column(
        String(32), nullable=True, index=True
    )
    category_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    category_origin_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_predicted: Mapped[Category | None] = mapped_column(String(32), nullable=True)
    category_confidence: Mapped[float | None] = mapped_column(nullable=True)
    category_predicted_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    category_predicted_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category_suggestion_rejected: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    transaction_type: Mapped[TransactionType | None] = mapped_column(String(32), nullable=True)
    transaction_type_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    transaction_type_confirmation_method: Mapped[str | None] = mapped_column(
        String(32), nullable=True, index=True
    )
    transaction_type_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    transaction_type_origin_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    transaction_type_predicted: Mapped[TransactionType | None] = mapped_column(
        String(32), nullable=True
    )
    transaction_type_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    transaction_type_predicted_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    transaction_type_predicted_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[BankSource] = mapped_column(String(32))
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dedup_hash: Mapped[str] = mapped_column(String(64))

    is_transfer: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    account: Mapped[Account | None] = relationship(back_populates="transactions")
    import_: Mapped[Import | None] = relationship(back_populates="transactions")


class MlFeedbackEvent(Base):
    """Audit trail of user feedback on ML/AI suggestions."""

    __tablename__ = "ml_feedback_events"
    __table_args__ = (
        Index("ix_ml_feedback_event_type", "event_type"),
        Index("ix_ml_feedback_created_at", "created_at"),
        Index("ix_ml_feedback_predicted_category", "predicted_category"),
        Index("ix_ml_feedback_entity", "entity_type", "entity_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    entity_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    entity_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_type: Mapped[str] = mapped_column(String(48))
    predicted_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    previous_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    final_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    predicted_transaction_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    previous_transaction_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    final_transaction_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confirmation_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    origin_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model_artifact: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MlTrainingJob(Base):
    """Durable state for a local, single-slot classifier training job."""

    __tablename__ = "ml_training_jobs"
    __table_args__ = (
        UniqueConstraint("execution_slot", name="uq_ml_training_jobs_execution_slot"),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'interrupted')",
            name="ck_ml_training_jobs_status",
        ),
        CheckConstraint(
            "(status IN ('queued', 'running') AND execution_slot = 1) OR "
            "(status NOT IN ('queued', 'running') AND execution_slot IS NULL)",
            name="ck_ml_training_jobs_execution_slot",
        ),
        Index("ix_ml_training_jobs_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    execution_slot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requested_variants: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list)
    dataset_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evaluation_set_id: Mapped[str | None] = mapped_column(
        ForeignKey("ml_evaluation_sets.id", ondelete="SET NULL"), nullable=True
    )
    report_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    result: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MlModelVersion(Base):
    """Candidate or archived classifier artifact registered for activation."""

    __tablename__ = "ml_model_versions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('candidate', 'active', 'archived', 'rejected')",
            name="ck_ml_model_versions_status",
        ),
        Index("ix_ml_model_versions_status", "status"),
        Index("ix_ml_model_versions_job_id", "job_id"),
        Index(
            "uq_ml_model_versions_one_active",
            "status",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("ml_training_jobs.id", ondelete="SET NULL"), nullable=True
    )
    estimator: Mapped[str] = mapped_column(String(64))
    feature_set: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), default="candidate")
    artifact_path: Mapped[str] = mapped_column(String(512))
    artifact_sha256: Mapped[str] = mapped_column(String(64))
    dataset_fingerprint: Mapped[str] = mapped_column(String(64))
    evaluation_set_id: Mapped[str | None] = mapped_column(
        ForeignKey("ml_evaluation_sets.id", ondelete="SET NULL"), nullable=True
    )
    metrics: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    gates: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    confidence_policy: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    promotable: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MlEvaluationSet(Base):
    """Versioned private thesis holdout definition."""

    __tablename__ = "ml_evaluation_sets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'invalidated')",
            name="ck_ml_evaluation_sets_status",
        ),
        Index("ix_ml_evaluation_sets_status", "status"),
        Index(
            "uq_ml_evaluation_sets_one_active",
            "status",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(24), default="active")
    ontology_version: Mapped[str] = mapped_column(String(32), default="category_v1")
    dataset_fingerprint: Mapped[str] = mapped_column(String(64))
    config: Mapped[dict[str, object]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidation_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)


class MlEvaluationMember(Base):
    """Immutable label snapshot belonging to one evaluation slice."""

    __tablename__ = "ml_evaluation_members"
    __table_args__ = (
        UniqueConstraint("evaluation_set_id", "transaction_id", "split", name="uq_ml_eval_member"),
        Index("ix_ml_eval_members_transaction_id", "transaction_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    evaluation_set_id: Mapped[str] = mapped_column(
        ForeignKey("ml_evaluation_sets.id", ondelete="CASCADE")
    )
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True
    )
    split: Mapped[str] = mapped_column(String(24))
    category: Mapped[str] = mapped_column(String(32))
    booking_date: Mapped[date] = mapped_column()
    merchant_hash: Mapped[str] = mapped_column(String(64))


class SubscriptionPreference(Base):
    """User decision layer for recurring subscription groups."""

    __tablename__ = "subscription_preferences"
    __table_args__ = (UniqueConstraint("subscription_key", name="uq_subscription_preferences_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_key: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    cadence_override: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FixedCharge(Base):
    """User-maintained schedule of planned recurring charges in PLN."""

    __tablename__ = "fixed_charges"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_fixed_charges_amount_positive"),
        CheckConstraint(
            "cadence IN ('monthly', 'quarterly', 'semiannual', 'yearly')",
            name="ck_fixed_charges_cadence",
        ),
        Index("ix_fixed_charges_active_anchor", "active", "anchor_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    cadence: Mapped[str] = mapped_column(String(16), nullable=False)
    anchor_date: Mapped[date] = mapped_column(nullable=False)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FixedChargeTransaction(Base):
    """Manual link between a scheduled charge occurrence and a transaction."""

    __tablename__ = "fixed_charge_transactions"
    __table_args__ = (
        UniqueConstraint(
            "transaction_id",
            name="uq_fixed_charge_transactions_transaction",
        ),
        Index(
            "ix_fixed_charge_transactions_charge_due",
            "fixed_charge_id",
            "scheduled_due_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fixed_charge_id: Mapped[int] = mapped_column(
        ForeignKey("fixed_charges.id", ondelete="CASCADE"), nullable=False
    )
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_due_date: Mapped[date] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AssetAccount(Base):
    """Container grouping assets held at one institution or platform."""

    __tablename__ = "asset_accounts"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('bank', 'brokerage', 'retirement', 'crypto', 'physical', 'other')",
            name="ck_asset_accounts_kind",
        ),
        CheckConstraint(
            "wrapper IN ('standard', 'ike', 'ikze', 'ppk')",
            name="ck_asset_accounts_wrapper",
        ),
        CheckConstraint(
            "tracking_mode IN ('aggregate', 'detailed')",
            name="ck_asset_accounts_tracking_mode",
        ),
        CheckConstraint(
            "wrapper = 'standard' OR kind = 'retirement'",
            name="ck_asset_accounts_retirement_wrapper",
        ),
        Index("ix_asset_accounts_archived_at", "archived_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    institution: Mapped[str | None] = mapped_column(String(128), nullable=True)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    wrapper: Mapped[str] = mapped_column(
        String(16), nullable=False, default="standard", server_default="standard"
    )
    tracking_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    default_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, default="PLN", server_default="PLN"
    )
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list[AssetItem]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )


class AssetItem(Base):
    """One value-bearing component of an asset account."""

    __tablename__ = "asset_items"
    __table_args__ = (
        CheckConstraint(
            "asset_type IN ('cash', 'savings_account', 'deposit', 'bond', 'stock', "
            "'etf', 'fund', 'crypto', 'precious_metal', 'loan_receivable', 'other')",
            name="ck_asset_items_type",
        ),
        CheckConstraint(
            "review_interval_days IS NULL OR review_interval_days IN (7, 30, 90, 180)",
            name="ck_asset_items_review_interval",
        ),
        Index("ix_asset_items_account_archived", "account_id", "archived_at"),
        Index(
            "uq_asset_items_aggregate_summary",
            "account_id",
            unique=True,
            postgresql_where=text("is_aggregate_summary = true"),
            sqlite_where=text("is_aggregate_summary = 1"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("asset_accounts.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True)
    review_interval_days: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=30, server_default="30"
    )
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_aggregate_summary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    account: Mapped[AssetAccount] = relationship(back_populates="items")
    valuations: Mapped[list[AssetValuation]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
    )


class AssetValuation(Base):
    """Manual valuation checkpoint and its optional growth policy."""

    __tablename__ = "asset_valuations"
    __table_args__ = (
        UniqueConstraint("item_id", "valuation_date", name="uq_asset_valuations_item_date"),
        CheckConstraint(
            "input_mode IN ('total', 'unit_price')",
            name="ck_asset_valuations_input_mode",
        ),
        CheckConstraint(
            "growth_mode IN ('none', 'fixed_rate')",
            name="ck_asset_valuations_growth_mode",
        ),
        CheckConstraint(
            "compounding IS NULL OR compounding IN ('simple', 'daily', 'monthly', 'yearly')",
            name="ck_asset_valuations_compounding",
        ),
        CheckConstraint("total_value >= 0", name="ck_asset_valuations_total_nonnegative"),
        CheckConstraint(
            "(input_mode = 'total' AND quantity IS NULL AND unit_price IS NULL) OR "
            "(input_mode = 'unit_price' AND quantity IS NOT NULL AND quantity >= 0 "
            "AND unit_price IS NOT NULL AND unit_price >= 0)",
            name="ck_asset_valuations_input_values",
        ),
        CheckConstraint(
            "(growth_mode = 'none' AND annual_rate_percent IS NULL AND compounding IS NULL "
            "AND growth_end_date IS NULL) OR "
            "(growth_mode = 'fixed_rate' AND annual_rate_percent IS NOT NULL "
            "AND annual_rate_percent > -100 AND annual_rate_percent <= 1000 "
            "AND compounding IS NOT NULL)",
            name="ck_asset_valuations_growth_values",
        ),
        CheckConstraint(
            "amount_pln IS NULL OR amount_pln >= 0",
            name="ck_asset_valuations_amount_pln_nonnegative",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("asset_items.id", ondelete="CASCADE"), nullable=False
    )
    valuation_date: Mapped[date] = mapped_column(nullable=False)
    input_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    total_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    amount_pln: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    fx_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    fx_rate_date: Mapped[date | None] = mapped_column(nullable=True)
    fx_rate_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    growth_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="none", server_default="none"
    )
    annual_rate_percent: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    compounding: Mapped[str | None] = mapped_column(String(16), nullable=True)
    growth_end_date: Mapped[date | None] = mapped_column(nullable=True)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="manual", server_default="manual"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    item: Mapped[AssetItem] = relationship(back_populates="valuations")
