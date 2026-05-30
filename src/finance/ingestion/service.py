"""Persist parsed transactions, deduplicating by a stable content hash."""
from __future__ import annotations

import hashlib
from typing import IO

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from finance.domain.dto import ImportSummary, TransactionDTO
from finance.domain.enums import BankSource, CategorySource, TransactionType
from finance.domain.models import Import, Transaction
from finance.ingestion.base import BankParser
from finance.ingestion.registry import get_parser
from finance.profile.service import RULE_MODE_AUTO, effect_for_transaction
from finance.transactions.normalization import normalize_merchant, normalize_text
from finance.transactions.rules import (
    detect_transaction_type,
    rule_category_for_type,
)
from finance.transactions.rules import detect_transfer as _detect_transfer


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


def detect_transfer(merchant: str | None, title: str | None) -> bool:
    """Backward-compatible import path for transfer detection tests/tools."""
    return _detect_transfer(merchant, title)


def transaction_values_for_dto(
    session: Session,
    dto: TransactionDTO,
    *,
    import_id: int | None,
    dedup_hash: str,
) -> dict[str, object]:
    """Build DB values for a parsed transaction, including personal rules."""
    personal = effect_for_transaction(session, merchant=dto.merchant, title=dto.title)
    system_transaction_type = detect_transaction_type(
        dto.merchant,
        dto.title,
        dto.direction,
        raw_category=dto.raw_category,
    )
    transaction_type = (
        personal.transaction_type
        if personal and personal.transaction_type
        else system_transaction_type.value
    )
    is_transfer = (
        personal.is_transfer
        if personal and personal.is_transfer is not None
        else transaction_type == "own_transfer"
    )

    rule_category = rule_category_for_type(TransactionType(transaction_type))
    category = dto.category.value if dto.category else None
    category_source = CategorySource.BANK.value if category is not None else None
    if category is None and rule_category is not None:
        category = rule_category.value
        category_source = CategorySource.RULE.value

    category_predicted = None
    category_confidence = None
    category_predicted_source = None
    if personal and personal.category and category is None:
        if personal.mode == RULE_MODE_AUTO:
            category = personal.category
            category_source = CategorySource.RULE.value
        else:
            category_predicted = personal.category
            category_confidence = personal.confidence
            category_predicted_source = CategorySource.RULE.value

    return {
        "booking_date": dto.booking_date,
        "booking_datetime": dto.booking_datetime,
        "amount": dto.amount,
        "currency": dto.currency,
        "direction": dto.direction.value,
        "merchant": dto.merchant,
        "title": dto.title,
        "raw_category": dto.raw_category,
        "category": category,
        "category_source": category_source,
        "category_predicted": category_predicted,
        "category_confidence": category_confidence,
        "category_predicted_source": category_predicted_source,
        "source": dto.source.value,
        "external_id": dto.external_id,
        "dedup_hash": dedup_hash,
        "import_id": import_id,
        "transaction_type": transaction_type,
        "is_transfer": bool(is_transfer),
    }


def ingest_file(
    session: Session,
    *,
    source: BankSource,
    filename: str,
    stream: IO[bytes],
    parser: BankParser | None = None,
) -> ImportSummary:
    parser = parser or get_parser(source)
    dtos = parser.parse(stream, filename=filename)

    import_row = Import(source=source, filename=filename, total_rows=len(dtos))
    session.add(import_row)
    session.flush()  # get import_row.id

    inserted = 0
    duplicates = 0
    for dto in dtos:
        h = compute_dedup_hash(dto)
        values = transaction_values_for_dto(
            session,
            dto,
            import_id=import_row.id,
            dedup_hash=h,
        )
        stmt = (
            pg_insert(Transaction)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["dedup_hash"])
            .returning(Transaction.id)
        )
        result = session.execute(stmt).first()
        if result is None:
            duplicates += 1
        else:
            inserted += 1

    import_row.inserted = inserted
    import_row.duplicates = duplicates
    session.commit()

    return ImportSummary(
        import_id=import_row.id,
        source=source,
        inserted=inserted,
        duplicates=duplicates,
        total_rows=len(dtos),
    )
