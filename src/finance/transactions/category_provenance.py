"""Shared write-side helpers for category label provenance."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from finance.domain.enums import CategoryConfirmationMethod
from finance.domain.models import Transaction


def personal_rule_ref(rule_id: int | None) -> str | None:
    return f"personal_rule:{rule_id}" if rule_id is not None else None


def bank_mapping_ref(source: object) -> str:
    return f"bank_mapping:{source}"


def system_rule_ref(rule_code: object) -> str:
    return f"system_rule:{rule_code}"


def model_version_ref(version_id: str | None) -> str | None:
    return f"model_version:{version_id}" if version_id else None


def confirm_category(
    tx: Transaction,
    *,
    category: str,
    source: str,
    method: CategoryConfirmationMethod | str,
    origin_ref: str | None,
    confirmed_at: datetime | None = None,
) -> None:
    row = cast(Any, tx)
    row.category = category
    row.category_source = source
    row.category_confirmation_method = str(method)
    row.category_confirmed_at = confirmed_at or datetime.now(UTC)
    row.category_origin_ref = origin_ref
    row.category_suggestion_rejected = False


def clear_confirmation(tx: Transaction) -> None:
    row = cast(Any, tx)
    row.category = None
    row.category_source = None
    row.category_confirmation_method = None
    row.category_confirmed_at = None
    row.category_origin_ref = None


def set_suggestion(
    tx: Transaction,
    *,
    category: str,
    source: str,
    confidence: float | None,
    origin_ref: str | None,
) -> None:
    row = cast(Any, tx)
    row.category_predicted = category
    row.category_confidence = confidence
    row.category_predicted_source = source
    row.category_predicted_ref = origin_ref
    row.category_suggestion_rejected = False


def clear_suggestion(tx: Transaction) -> None:
    row = cast(Any, tx)
    row.category_predicted = None
    row.category_confidence = None
    row.category_predicted_source = None
    row.category_predicted_ref = None
