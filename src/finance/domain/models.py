"""SQLAlchemy ORM models."""
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="account")


class Import(Base):
    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[BankSource] = mapped_column(String(32))
    filename: Mapped[str] = mapped_column(String(256))
    total_rows: Mapped[int] = mapped_column(default=0)
    inserted: Mapped[int] = mapped_column(default=0)
    duplicates: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="import_")


class CategoryDef(Base):
    """User-manageable category catalog.

    System categories from :class:`Category` are seeded on first use and cannot
    be deleted. Users may add their own.
    The ``Transaction.category`` column stores the category *name* (string),
    so removing a custom category simply leaves transactions with an unknown
    label until they are re-categorised.
    """

    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("name", name="uq_categories_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    parent: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


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
        Index("ix_fx_rates_currency_base_date", "currency", "base_currency", "rate_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(String(3))
    base_currency: Mapped[str] = mapped_column(String(3))
    rate_date: Mapped[date] = mapped_column()
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    source: Mapped[str] = mapped_column(String(32), default="manual", server_default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PersonalRule(Base):
    """User-defined merchant/title rule used before ML suggestions."""

    __tablename__ = "personal_rules"
    __table_args__ = (
        Index("ix_personal_rules_active_priority", "active", "priority"),
    )

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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("dedup_hash", name="uq_transactions_dedup_hash"),
        Index("ix_transactions_booking_date", "booking_date"),
        Index("ix_transactions_category", "category"),
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
    transaction_type_origin_ref: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    transaction_type_predicted: Mapped[TransactionType | None] = mapped_column(
        String(32), nullable=True
    )
    transaction_type_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    transaction_type_predicted_source: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    transaction_type_predicted_ref: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    source: Mapped[BankSource] = mapped_column(String(32))
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    dedup_hash: Mapped[str] = mapped_column(String(64))

    is_transfer: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    invalidation_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)


class MlEvaluationMember(Base):
    """Immutable label snapshot belonging to one evaluation slice."""

    __tablename__ = "ml_evaluation_members"
    __table_args__ = (
        UniqueConstraint(
            "evaluation_set_id", "transaction_id", "split", name="uq_ml_eval_member"
        ),
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
    __table_args__ = (
        UniqueConstraint("subscription_key", name="uq_subscription_preferences_key"),
        Index("ix_subscription_preferences_key", "subscription_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subscription_key: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    cadence_override: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Asset(Base):
    """User-tracked asset (stock, ETF, crypto, cash position)."""

    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("symbol", name="uq_assets_symbol"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32))  # e.g. AAPL, BTC-USD, CASH-PLN
    name: Mapped[str] = mapped_column(String(128), default="")
    # equity | etf | crypto | cash | bond
    asset_class: Mapped[str] = mapped_column(String(16), default="equity")
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=Decimal("0"))
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    snapshots: Mapped[list["AssetSnapshot"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )


class AssetSnapshot(Base):
    """Historical price/value point for an asset."""

    __tablename__ = "asset_snapshots"
    __table_args__ = (
        UniqueConstraint("asset_id", "snapshot_date", name="uq_asset_snapshot_date"),
        Index("ix_asset_snapshots_date", "snapshot_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
    snapshot_date: Mapped[date] = mapped_column()
    price: Mapped[Decimal] = mapped_column(Numeric(20, 8))
    value_pln: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    source: Mapped[str] = mapped_column(String(32), default="yfinance")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    asset: Mapped[Asset] = relationship(back_populates="snapshots")
