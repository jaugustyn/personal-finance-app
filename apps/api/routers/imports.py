"""POST /imports — upload a bank CSV and ingest it.

Three flows are supported:

1. **Auto-detect** — omit ``source`` (or pass ``auto``); the router peeks
   headers and picks a parser via :func:`finance.ingestion.registry.detect_source`.
   Falls back to the generic parser with header-alias detection if no vendor
   matches.
2. **Detected source** — pass a known bank source after preview.
3. **Generic with column-map** — ``source=generic`` plus ``column_map`` JSON
   string mapping logical fields (date, amount, currency, merchant, title,
   category, external_id) to actual header names.

``POST /imports/preview`` returns headers + sample rows + auto-detected
mapping, so the UI can show a column mapper before commit.
"""
from __future__ import annotations

import io
import json
import logging
from typing import Any, Literal, cast

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from apps.api.errors import (
    not_found,
    not_implemented,
    payload_too_large,
    unsupported_media_type,
    validation_error,
)
from apps.api.schemas.imports import (
    ImportDeleteResult,
    ImportQualityIssueResponse,
    ImportQualityReportResponse,
    ImportRow,
    PreviewResponse,
)
from finance.currencies import MissingFxRate
from finance.db import SessionLocal, get_session
from finance.domain.dto import ImportSummary
from finance.domain.enums import BankSource
from finance.domain.models import Import, Transaction
from finance.ingestion import BankParser, ParseError
from finance.ingestion.generic import GenericCsvParser, preview_csv
from finance.ingestion.quality import ImportQualityReport, assess_import_quality
from finance.ingestion.registry import available_sources, detect_source, get_parser
from finance.ingestion.schema import (
    clean_column_map,
    import_field_specs_payload,
    import_quality_warnings,
    validate_column_map,
)
from finance.ingestion.service import ingest_file
from finance.ml.classification.predict import ClassifierNotAvailable, reclassify_unlabelled

router = APIRouter(prefix="/imports", tags=["imports"])
logger = logging.getLogger(__name__)

# Maximum text upload size (10 MiB). Full-year CSV exports are typically much
# smaller; this leaves headroom and protects against oversized payloads.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = (".csv", ".tsv", ".txt")
ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "text/plain",
    "text/tab-separated-values",
    "application/csv",
    "application/vnd.ms-excel",  # Windows often reports CSV as this MIME type.
    "application/octet-stream",  # browsers often default to this for CSV
    "",  # some HTTP clients omit content-type
}


def _read_validated(file: UploadFile) -> bytes:
    """Validate filename, content-type and size; return raw bytes."""
    name = (file.filename or "").lower()
    if name and not name.endswith(ALLOWED_EXTENSIONS):
        raise unsupported_media_type(f"Unsupported file extension: {file.filename!r}")
    ct = (file.content_type or "").lower().split(";")[0].strip()
    if ct not in ALLOWED_CONTENT_TYPES:
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
        logger.info("Suggested categories for import %s: %s rows", import_id, updated)
    except ClassifierNotAvailable:
        logger.info("Skipping category suggestions for import %s: no classifier", import_id)
    except Exception:
        logger.exception("Category suggestion job failed for import %s", import_id)


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
    fx_mode: Literal["require_existing", "prefetch_missing"] = Form("prefetch_missing"),
    session: Session = Depends(get_session),
) -> PreviewResponse:
    raw = _read_validated(file)
    try:
        prev = preview_csv(io.BytesIO(raw), max_rows=100)
    except Exception as exc:  # noqa: BLE001
        raise validation_error(f"Cannot parse CSV: {exc}") from exc
    detected_source = detect_source(prev.headers)
    requested_source = (source or "").strip().lower()
    requested_mapping = _parse_column_map(column_map)
    quality_parser: BankParser

    if requested_source == "generic" or requested_mapping is not None:
        quality_mapping = requested_mapping or clean_column_map(prev.detected_mapping)
        quality_parser = GenericCsvParser(quality_mapping)
        quality_warnings = import_quality_warnings(quality_mapping)
    else:
        quality_mapping = clean_column_map(prev.detected_mapping)
        quality_parser = (
            get_parser(detected_source)
            if detected_source is not None
            else GenericCsvParser(quality_mapping)
        )
        quality_warnings = import_quality_warnings(quality_mapping)

    quality_report = assess_import_quality(
        session,
        filename=file.filename or "uploaded.csv",
        raw=raw,
        parser=quality_parser,
        missing_fx_severity="error" if fx_mode == "require_existing" else "warning",
    )
    return PreviewResponse(
        headers=prev.headers,
        sample_rows=prev.sample_rows,
        delimiter=prev.delimiter,
        encoding=prev.encoding,
        detected_source=detected_source,
        detected_mapping=prev.detected_mapping,
        field_specs=import_field_specs_payload(),
        quality_warnings=quality_warnings,
        quality_report=_quality_report_response(quality_report),
        supported_extensions=list(ALLOWED_EXTENSIONS),
    )


@router.post("", response_model=ImportSummary)
def upload_import(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    source: str | None = Form(None),
    column_map: str | None = Form(None),
    skip_categories: bool = Form(False),
    fx_mode: Literal["require_existing", "prefetch_missing"] = Form("prefetch_missing"),
    session: Session = Depends(get_session),
) -> ImportSummary:
    raw = _read_validated(file)

    src_lower = (source or "").strip().lower()
    parser: GenericCsvParser | None = None

    if src_lower in ("", "auto"):
        try:
            prev = preview_csv(io.BytesIO(raw))
        except Exception as exc:  # noqa: BLE001
            raise validation_error(f"Cannot parse CSV: {exc}") from exc
        detected = detect_source(prev.headers)
        if detected is not None:
            chosen_source = detected
        else:
            chosen_source = BankSource.UNKNOWN
            parser = GenericCsvParser()
    elif src_lower == "generic":
        chosen_source = BankSource.UNKNOWN
        mapping: dict[str, str] | None = None
        try:
            prev = preview_csv(io.BytesIO(raw))
        except Exception as exc:  # noqa: BLE001
            raise validation_error(f"Cannot parse CSV: {exc}") from exc
        if column_map:
            mapping = _parse_column_map(column_map)
        else:
            mapping = clean_column_map(prev.detected_mapping)
        errors = validate_column_map(mapping or {}, headers=prev.headers)
        if errors:
            raise validation_error("; ".join(errors))
        parser = GenericCsvParser(mapping)
    else:
        try:
            chosen_source = BankSource(src_lower)
        except ValueError as exc:
            raise validation_error(f"Unknown source: {source!r}") from exc
        if chosen_source not in available_sources():
            raise validation_error(f"Unknown source: {source!r}")

    try:
        summary = ingest_file(
            session,
            source=chosen_source,
            filename=file.filename or "uploaded.csv",
            stream=io.BytesIO(raw),
            parser=parser,
            skip_categories=skip_categories,
            fx_mode=fx_mode,
        )
        if summary.inserted > 0:
            background.add_task(_suggest_import_categories, summary.import_id)
        return summary
    except ParseError as exc:
        raise validation_error(str(exc)) from exc
    except MissingFxRate as exc:
        session.rollback()
        raise validation_error(str(exc)) from exc
    except ValueError as exc:
        session.rollback()
        raise validation_error(str(exc)) from exc
    except NotImplementedError as exc:
        raise not_implemented(str(exc)) from exc


@router.get("", response_model=list[ImportRow])
def list_imports(session: Session = Depends(get_session)) -> list[ImportRow]:
    rows = session.execute(
        select(Import).order_by(Import.created_at.desc())
    ).scalars().all()
    return [ImportRow.model_validate(r) for r in rows]


@router.delete("/{import_id}", response_model=ImportDeleteResult)
def delete_import(
    import_id: int, session: Session = Depends(get_session)
) -> ImportDeleteResult:
    """Delete an import row together with all transactions it created.

    Useful when re-importing a corrected CSV: drop the old batch first to
    avoid stale rows, then upload the new file.
    """
    imp = session.get(Import, import_id)
    if imp is None:
        raise not_found("Import not found.")
    res = session.execute(
        delete(Transaction).where(Transaction.import_id == import_id)
    )
    deleted = int(cast(Any, res).rowcount or 0)
    session.delete(imp)
    session.commit()
    return ImportDeleteResult(deleted_transactions=deleted, import_id=import_id)
