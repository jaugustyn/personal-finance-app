"""Application-level orchestration for import preview, upload, and deletion."""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from finance.accounts.service import get_active_account, suggest_account_id
from finance.db import command_transaction
from finance.domain.dto import ImportSummary
from finance.domain.enums import BankSource
from finance.domain.models import Import, Transaction
from finance.ingestion.base import BankParser
from finance.ingestion.generic import CsvPreview, GenericCsvParser, preview_csv
from finance.ingestion.quality import assess_import_quality
from finance.ingestion.registry import available_sources, detect_source, get_parser
from finance.ingestion.schema import clean_column_map, import_quality_warnings, validate_column_map
from finance.ingestion.service import ingest_transactions
from finance.ingestion.types import FxRateMode, ImportQualityReport


class ImportNotFound(LookupError):
    """Raised when an import batch cannot be found."""


class ImportAccountConflict(ValueError):
    """Raised when moving an import would create account-scoped duplicates."""


@dataclass(frozen=True)
class ImportPreviewResult:
    csv: CsvPreview
    detected_source: BankSource | None
    quality_warnings: list[str]
    quality_report: ImportQualityReport
    account_id: int | None
    suggested_account_id: int | None


@dataclass(frozen=True)
class ImportUploadResult:
    summary: ImportSummary
    skipped_rows: int
    quality_report: ImportQualityReport
    chosen_source: BankSource
    parser: BankParser


@dataclass(frozen=True)
class DeletedImport:
    import_id: int
    deleted_transactions: int


@dataclass(frozen=True)
class ImportListItem:
    id: int
    account_id: int
    account_name: str
    source: str
    filename: str
    total_rows: int
    inserted: int
    duplicates: int
    created_at: Any


def preview_import(
    session: Session,
    *,
    filename: str,
    raw: bytes,
    requested_source: str | None,
    column_map: dict[str, str] | None,
    fx_mode: FxRateMode,
    account_id: int | None = None,
) -> ImportPreviewResult:
    if account_id is not None:
        get_active_account(session, account_id)
    preview = preview_csv(io.BytesIO(raw), max_rows=100)
    detected_source = detect_source(preview.headers)
    source_name = (requested_source or "").strip().lower()

    if source_name == "generic" or column_map is not None:
        quality_mapping = column_map or clean_column_map(preview.detected_mapping)
        parser: BankParser = GenericCsvParser(quality_mapping)
    else:
        quality_mapping = clean_column_map(preview.detected_mapping)
        parser = (
            get_parser(detected_source)
            if detected_source is not None
            else GenericCsvParser(quality_mapping)
        )

    quality_report = assess_import_quality(
        session,
        filename=filename,
        raw=raw,
        parser=parser,
        missing_fx_severity="error" if fx_mode == "require_existing" else "warning",
        account_id=account_id,
    )
    suggestion_source = detected_source
    if source_name not in {"", "auto", "generic"}:
        try:
            suggestion_source = BankSource(source_name)
        except ValueError:
            suggestion_source = None
    return ImportPreviewResult(
        csv=preview,
        detected_source=detected_source,
        quality_warnings=import_quality_warnings(quality_mapping),
        quality_report=quality_report,
        account_id=account_id,
        suggested_account_id=(
            account_id if account_id is not None else suggest_account_id(session, suggestion_source)
        ),
    )


def upload_import(
    session: Session,
    *,
    filename: str,
    raw: bytes,
    requested_source: str | None,
    column_map: dict[str, str] | None,
    skip_categories: bool,
    fx_mode: FxRateMode,
    account_id: int,
) -> ImportUploadResult:
    account = get_active_account(session, account_id)
    chosen_source, parser = select_upload_parser(
        raw=raw,
        requested_source=requested_source,
        column_map=column_map,
    )
    dtos = parser.parse(io.BytesIO(raw), filename=filename)
    quality_report = assess_import_quality(
        session,
        filename=filename,
        raw=raw,
        parser=parser,
        missing_fx_severity="error" if fx_mode == "require_existing" else "warning",
        parsed_dtos=dtos,
        account_id=account_id,
    )
    with command_transaction(session):
        summary = ingest_transactions(
            session,
            source=chosen_source,
            account_id=account_id,
            filename=filename,
            dtos=dtos,
            skip_categories=skip_categories,
            fx_mode=fx_mode,
        )
        if str(account.source) == BankSource.UNKNOWN.value:
            account.source = chosen_source

    skipped_rows = (
        max(quality_report.total_rows - quality_report.valid_rows, 0)
        if isinstance(parser, GenericCsvParser)
        else 0
    )
    return ImportUploadResult(
        summary=summary,
        skipped_rows=skipped_rows,
        quality_report=quality_report,
        chosen_source=chosen_source,
        parser=parser,
    )


def list_imports(session: Session) -> list[ImportListItem]:
    rows = list(
        session.scalars(
            select(Import)
            .options(selectinload(Import.account))
            .order_by(Import.created_at.desc(), Import.id.desc())
        )
    )
    return [
        ImportListItem(
            id=row.id,
            account_id=row.account_id,
            account_name=row.account.name,
            source=str(row.source),
            filename=row.filename,
            total_rows=row.total_rows,
            inserted=row.inserted,
            duplicates=row.duplicates,
            created_at=row.created_at,
        )
        for row in rows
    ]


def change_import_account(session: Session, import_id: int, account_id: int) -> ImportListItem:
    import_row = session.get(Import, import_id)
    if import_row is None:
        raise ImportNotFound("Import not found.")
    target = get_active_account(session, account_id)
    if import_row.account_id != account_id:
        hashes = select(Transaction.dedup_hash).where(Transaction.import_id == import_id)
        conflict_exists = session.scalar(
            select(Transaction.id)
            .where(
                Transaction.account_id == account_id,
                Transaction.dedup_hash.in_(hashes),
            )
            .limit(1)
        )
        if conflict_exists is not None:
            raise ImportAccountConflict(
                "The target account already contains one or more transactions from this import."
            )
        try:
            with command_transaction(session):
                import_row.account_id = account_id
                session.execute(
                    update(Transaction)
                    .where(Transaction.import_id == import_id)
                    .values(account_id=account_id)
                )
                if str(target.source) == BankSource.UNKNOWN.value:
                    target.source = import_row.source
        except IntegrityError as exc:
            raise ImportAccountConflict(
                "The target account already contains one or more transactions from this import."
            ) from exc
    row = next(item for item in list_imports(session) if item.id == import_id)
    return row


def delete_import(session: Session, import_id: int) -> DeletedImport:
    import_row = session.get(Import, import_id)
    if import_row is None:
        raise ImportNotFound("Import not found.")
    try:
        result = session.execute(
            delete(Transaction).where(Transaction.import_id == import_id)
        )
        deleted = int(cast(Any, result).rowcount or 0)
        session.delete(import_row)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return DeletedImport(import_id=import_id, deleted_transactions=deleted)


def select_upload_parser(
    *,
    raw: bytes,
    requested_source: str | None,
    column_map: dict[str, str] | None,
) -> tuple[BankSource, BankParser]:
    source_name = (requested_source or "").strip().lower()
    if source_name in {"", "auto"}:
        preview = preview_csv(io.BytesIO(raw))
        detected_source = detect_source(preview.headers)
        if detected_source is not None:
            return detected_source, get_parser(detected_source)
        return BankSource.UNKNOWN, GenericCsvParser()

    if source_name == "generic":
        preview = preview_csv(io.BytesIO(raw))
        mapping = column_map or clean_column_map(preview.detected_mapping)
        errors = validate_column_map(mapping, headers=preview.headers)
        if errors:
            raise ValueError("; ".join(errors))
        return BankSource.UNKNOWN, GenericCsvParser(mapping)

    try:
        source = BankSource(source_name)
    except ValueError as exc:
        raise ValueError(f"Unknown source: {requested_source!r}") from exc
    if source not in available_sources():
        raise ValueError(f"Unknown source: {requested_source!r}")
    return source, get_parser(source)
