"""Persist parsed transactions, deduplicating by a stable content hash."""
from __future__ import annotations

import hashlib
from typing import IO

from sqlalchemy.orm import Session

from finance.currencies import convert_amount, prefetch_nbp_rates, resolve_base_currency
from finance.domain.dto import ImportSummary, TransactionDTO
from finance.domain.enums import BankSource
from finance.ingestion.base import BankParser
from finance.ingestion.policy import TransactionImportPolicy, build_transaction_values
from finance.ingestion.registry import get_parser
from finance.ingestion.repository import TransactionImportRepository
from finance.ingestion.types import FxRateMode
from finance.ml.feedback import (
    EVENT_AUTO_RULE_CATEGORY,
    FeedbackEventInput,
    record_feedback_event,
)
from finance.profile.service import effect_for_transaction
from finance.transactions.normalization import normalize_merchant, normalize_text


def compute_dedup_hash(dto: TransactionDTO) -> str:
    """Stable hash over fields that uniquely identify a transaction.

    Intentionally excludes import-time metadata. Re-importing the same export
    file (or overlapping range) will not create duplicates.
    """
    payload = "|".join(
        [
            dto.source.value,
            dto.booking_date.isoformat(),
            f"{dto.amount:.2f}",
            dto.currency,
            dto.direction.value,
            normalize_merchant(dto.merchant),
            normalize_text(dto.title),
            dto.external_id or "",
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def transaction_values_for_dto(
    session: Session,
    dto: TransactionDTO,
    *,
    import_id: int | None,
    dedup_hash: str,
    skip_categories: bool = False,
) -> dict[str, object]:
    """Build DB values for a parsed transaction, including session-backed inputs."""
    converted = convert_amount(
        session,
        amount=dto.amount,
        currency=dto.currency,
        rate_date=dto.booking_date,
    )
    personal = effect_for_transaction(session, merchant=dto.merchant, title=dto.title)
    return build_transaction_values(
        dto,
        converted=converted,
        personal=personal,
        import_id=import_id,
        dedup_hash=dedup_hash,
        skip_categories=skip_categories,
    )


def ingest_file(
    session: Session,
    *,
    source: BankSource,
    filename: str,
    stream: IO[bytes],
    parser: BankParser | None = None,
    skip_categories: bool = False,
    fx_mode: FxRateMode = "prefetch_missing",
) -> ImportSummary:
    parser = parser or get_parser(source)
    dtos = parser.parse(stream, filename=filename)
    base_currency = resolve_base_currency(session)
    if fx_mode == "prefetch_missing":
        prefetch_nbp_rates(
            session,
            rate_requests=[(dto.currency, dto.booking_date) for dto in dtos],
            base_currency=base_currency,
        )
    elif fx_mode != "require_existing":
        raise ValueError(f"Unsupported FX mode: {fx_mode}")

    repository = TransactionImportRepository(session)
    policy = TransactionImportPolicy(skip_categories=skip_categories)
    import_row = repository.create_import(
        source=source,
        filename=filename,
        total_rows=len(dtos),
    )

    inserted = 0
    duplicates = 0
    for dto in dtos:
        h = compute_dedup_hash(dto)
        converted = convert_amount(
            session,
            amount=dto.amount,
            currency=dto.currency,
            rate_date=dto.booking_date,
            base_currency=base_currency,
            allow_fetch=False,
        )
        personal = effect_for_transaction(session, merchant=dto.merchant, title=dto.title)
        values = policy.build_transaction_values(
            dto,
            converted=converted,
            personal=personal,
            import_id=import_row.id,
            dedup_hash=h,
        )
        transaction_id = repository.insert_transaction_values(values)
        if transaction_id is not None:
            inserted += 1
            if values.get("category_confirmation_method") == "personal_rule_auto":
                record_feedback_event(
                    session,
                    FeedbackEventInput(
                        transaction_id=transaction_id,
                        entity_type="transaction",
                        entity_key=str(transaction_id),
                        event_type=EVENT_AUTO_RULE_CATEGORY,
                        final_category=str(values.get("category")),
                        confirmation_method="personal_rule_auto",
                        source=str(values.get("category_source")),
                        origin_ref=(
                            str(values["category_origin_ref"])
                            if values.get("category_origin_ref")
                            else None
                        ),
                    ),
                )
        else:
            duplicates += 1

    repository.finalize_import(import_row, inserted=inserted, duplicates=duplicates)
    session.commit()

    return ImportSummary(
        import_id=import_row.id,
        source=source,
        inserted=inserted,
        duplicates=duplicates,
        total_rows=len(dtos),
    )
