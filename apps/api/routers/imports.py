"""HTTP adapter for transaction import preview and ingestion."""
from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from apps.api.errors import (
    conflict,
    not_found,
    not_implemented,
    payload_too_large,
    unsupported_media_type,
    validation_error,
)
from apps.api.schemas.imports import (
    ImportAccountUpdate,
    ImportDeleteResult,
    ImportQualityIssueResponse,
    ImportQualityReportResponse,
    ImportRow,
    ImportUploadResponse,
    PreviewResponse,
)
from finance.accounts.service import AccountArchived, AccountNotFound
from finance.currencies import MissingFxRate
from finance.db import SessionLocal, get_session
from finance.ingestion import ParseError
from finance.ingestion.schema import clean_column_map, import_field_specs_payload
from finance.ingestion.types import ImportQualityReport
from finance.ingestion.use_cases import (
    ImportAccountConflict,
    ImportNotFound,
    change_import_account,
)
from finance.ingestion.use_cases import (
    delete_import as delete_import_batch,
)
from finance.ingestion.use_cases import (
    list_imports as load_imports,
)
from finance.ingestion.use_cases import (
    preview_import as inspect_import,
)
from finance.ingestion.use_cases import (
    upload_import as run_import,
)
from finance.ml.classification.predict import ClassifierNotAvailable, reclassify_unlabelled
from finance.observability import get_logger

router = APIRouter(prefix="/imports", tags=["imports"])
logger = get_logger("api.imports")

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = (".csv", ".tsv", ".txt")
ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "text/plain",
    "text/tab-separated-values",
    "application/csv",
    "application/vnd.ms-excel",
    "application/octet-stream",
    "",
}


def _read_validated(file: UploadFile) -> bytes:
    name = (file.filename or "").lower()
    if name and not name.endswith(ALLOWED_EXTENSIONS):
        raise unsupported_media_type(f"Unsupported file extension: {file.filename!r}")
    content_type = (file.content_type or "").lower().split(";")[0].strip()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise unsupported_media_type(f"Unsupported content type: {file.content_type!r}")
    raw = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise payload_too_large(
            f"File too large (limit: {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB)."
        )
    if not raw:
        raise validation_error("Empty file.")
    return raw


def _suggest_import_categories(import_id: int) -> None:
    try:
        with SessionLocal() as session:
            updated = reclassify_unlabelled(session, import_id=import_id)
        logger.info(
            "import_category_suggestions_completed",
            import_id=import_id,
            updated=updated,
        )
    except ClassifierNotAvailable:
        logger.info("import_category_suggestions_skipped", import_id=import_id)
    except Exception:
        logger.exception("import_category_suggestions_failed", import_id=import_id)


def _quality_report_response(report: ImportQualityReport) -> ImportQualityReportResponse:
    return ImportQualityReportResponse(
        total_rows=report.total_rows,
        valid_rows=report.valid_rows,
        blocking_issues=report.blocking_issues,
        warnings=report.warnings,
        issues=[
            ImportQualityIssueResponse(
                code=issue.code,
                severity=issue.severity,
                count=issue.count,
                sample_rows=issue.sample_rows,
            )
            for issue in report.issues
        ],
    )


def _parse_column_map(column_map: str | None) -> dict[str, str] | None:
    if not column_map:
        return None
    try:
        parsed = json.loads(column_map)
    except json.JSONDecodeError as exc:
        raise validation_error(f"Invalid column_map JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise validation_error("column_map must be an object.")
    return clean_column_map(parsed)


@router.post("/preview", response_model=PreviewResponse)
def preview_import(
    file: UploadFile = File(...),
    source: str | None = Form(None),
    column_map: str | None = Form(None),
    fx_mode: Literal["require_existing", "prefetch_missing"] = Form(
        "prefetch_missing"
    ),
    account_id: int | None = Form(default=None),
    session: Session = Depends(get_session),
) -> PreviewResponse:
    raw = _read_validated(file)
    try:
        result = inspect_import(
            session,
            filename=file.filename or "uploaded.csv",
            raw=raw,
            requested_source=source,
            column_map=_parse_column_map(column_map),
            fx_mode=fx_mode,
            account_id=account_id,
        )
    except (AccountArchived, AccountNotFound, ParseError, ValueError) as exc:
        raise validation_error(f"Cannot parse CSV: {exc}") from exc
    return PreviewResponse(
        headers=result.csv.headers,
        sample_rows=result.csv.sample_rows,
        delimiter=result.csv.delimiter,
        encoding=result.csv.encoding,
        detected_source=result.detected_source,
        detected_mapping=result.csv.detected_mapping,
        field_specs=import_field_specs_payload(),
        quality_warnings=result.quality_warnings,
        quality_report=_quality_report_response(result.quality_report),
        supported_extensions=list(ALLOWED_EXTENSIONS),
        account_id=result.account_id,
        suggested_account_id=result.suggested_account_id,
    )


@router.post("", response_model=ImportUploadResponse)
def upload_import(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    source: str | None = Form(None),
    column_map: str | None = Form(None),
    skip_categories: bool = Form(False),
    fx_mode: Literal["require_existing", "prefetch_missing"] = Form(
        "prefetch_missing"
    ),
    account_id: int = Form(..., gt=0),
    session: Session = Depends(get_session),
) -> ImportUploadResponse:
    raw = _read_validated(file)
    try:
        result = run_import(
            session,
            filename=file.filename or "uploaded.csv",
            raw=raw,
            requested_source=source,
            column_map=_parse_column_map(column_map),
            skip_categories=skip_categories,
            fx_mode=fx_mode,
            account_id=account_id,
        )
    except (AccountArchived, AccountNotFound, ParseError, MissingFxRate, ValueError) as exc:
        raise validation_error(str(exc)) from exc
    except NotImplementedError as exc:
        raise not_implemented(str(exc)) from exc

    summary = result.summary
    if summary.inserted > 0:
        background.add_task(_suggest_import_categories, summary.import_id)
    return ImportUploadResponse(
        import_id=summary.import_id,
        account_id=summary.account_id,
        account_name=summary.account_name,
        source=summary.source,
        inserted=summary.inserted,
        duplicates=summary.duplicates,
        total_rows=summary.total_rows,
        skipped_rows=result.skipped_rows,
        quality_report=_quality_report_response(result.quality_report),
    )


@router.get("", response_model=list[ImportRow])
def list_imports(session: Session = Depends(get_session)) -> list[ImportRow]:
    return [ImportRow.model_validate(row) for row in load_imports(session)]


@router.patch("/{import_id}/account", response_model=ImportRow)
def patch_import_account(
    import_id: int,
    payload: ImportAccountUpdate,
    session: Session = Depends(get_session),
) -> ImportRow:
    try:
        row = change_import_account(session, import_id, payload.account_id)
    except ImportNotFound as exc:
        raise not_found(str(exc)) from exc
    except ImportAccountConflict as exc:
        raise conflict(str(exc)) from exc
    except AccountNotFound as exc:
        raise not_found(str(exc)) from exc
    except AccountArchived as exc:
        raise validation_error(str(exc)) from exc
    return ImportRow.model_validate(row)


@router.delete("/{import_id}", response_model=ImportDeleteResult)
def delete_import(
    import_id: int,
    session: Session = Depends(get_session),
) -> ImportDeleteResult:
    try:
        result = delete_import_batch(session, import_id)
    except ImportNotFound as exc:
        raise not_found(str(exc)) from exc
    return ImportDeleteResult(
        deleted_transactions=result.deleted_transactions,
        import_id=result.import_id,
    )
