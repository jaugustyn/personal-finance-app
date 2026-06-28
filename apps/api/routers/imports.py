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
from datetime import datetime
from typing import Any, cast

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from finance.currencies import MissingFxRate
from finance.db import SessionLocal, get_session
from finance.domain.dto import ImportSummary
from finance.domain.enums import BankSource
from finance.domain.models import Import, Transaction
from finance.ingestion import ParseError
from finance.ingestion.generic import GenericCsvParser, preview_csv
from finance.ingestion.quality import ImportQualityReport, assess_import_quality
from finance.ingestion.registry import detect_source, get_parser
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
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file extension: {file.filename!r}",
        )
    ct = (file.content_type or "").lower().split(";")[0].strip()
    if ct not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported content type: {file.content_type!r}",
        )
    raw = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=(
                f"File too large (limit: {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB)."
            ),
        )
    if not raw:
        raise HTTPException(status_code=422, detail="Empty file.")
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


class ImportQualityIssueResponse(BaseModel):
    code: str
    severity: str
    count: int
    sample_rows: list[int]


class ImportQualityReportResponse(BaseModel):
    total_rows: int
    valid_rows: int
    blocking_issues: int
    warnings: int
    issues: list[ImportQualityIssueResponse]


class PreviewResponse(BaseModel):
    headers: list[str]
    sample_rows: list[dict[str, str]]
    delimiter: str
    encoding: str
    detected_source: BankSource | None
    detected_mapping: dict[str, str | None]
    field_specs: list[dict[str, object]]
    quality_warnings: list[str]
    quality_report: ImportQualityReportResponse
    supported_extensions: list[str]


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


@router.post("/preview", response_model=PreviewResponse)
def preview_import(
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> PreviewResponse:
    raw = _read_validated(file)
    try:
        prev = preview_csv(io.BytesIO(raw))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Cannot parse CSV: {exc}") from exc
    detected_source = detect_source(prev.headers)
    quality_source = detected_source or BankSource.UNKNOWN
    quality_parser = (
        get_parser(detected_source)
        if detected_source is not None
        else GenericCsvParser({k: v for k, v in prev.detected_mapping.items() if v})
    )
    quality_report = assess_import_quality(
        session,
        source=quality_source,
        filename=file.filename or "uploaded.csv",
        raw=raw,
        parser=quality_parser,
    )
    return PreviewResponse(
        headers=prev.headers,
        sample_rows=prev.sample_rows,
        delimiter=prev.delimiter,
        encoding=prev.encoding,
        detected_source=detected_source,
        detected_mapping=prev.detected_mapping,
        field_specs=import_field_specs_payload(),
        quality_warnings=import_quality_warnings(
            {k: v for k, v in prev.detected_mapping.items() if v}
        ),
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
    session: Session = Depends(get_session),
) -> ImportSummary:
    raw = _read_validated(file)

    src_lower = (source or "").strip().lower()
    parser: GenericCsvParser | None = None

    if src_lower in ("", "auto"):
        try:
            prev = preview_csv(io.BytesIO(raw))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=f"Cannot parse CSV: {exc}") from exc
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
            raise HTTPException(status_code=422, detail=f"Cannot parse CSV: {exc}") from exc
        if column_map:
            try:
                parsed = json.loads(column_map)
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=422, detail=f"Invalid column_map JSON: {exc}"
                ) from exc
            if not isinstance(parsed, dict):
                raise HTTPException(status_code=422, detail="column_map must be an object.")
            mapping = clean_column_map(parsed)
        else:
            mapping = clean_column_map(prev.detected_mapping)
        errors = validate_column_map(mapping or {}, headers=prev.headers)
        if errors:
            raise HTTPException(status_code=422, detail="; ".join(errors))
        parser = GenericCsvParser(mapping)
    else:
        try:
            chosen_source = BankSource(src_lower)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"Unknown source: {source!r}") from exc

    try:
        summary = ingest_file(
            session,
            source=chosen_source,
            filename=file.filename or "uploaded.csv",
            stream=io.BytesIO(raw),
            parser=parser,
            skip_categories=skip_categories,
        )
        if summary.inserted > 0:
            background.add_task(_suggest_import_categories, summary.import_id)
        return summary
    except ParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except MissingFxRate as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc


class ImportRow(BaseModel):
    id: int
    source: str
    filename: str
    total_rows: int
    inserted: int
    duplicates: int
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ImportRow])
def list_imports(session: Session = Depends(get_session)) -> list[ImportRow]:
    rows = session.execute(
        select(Import).order_by(Import.created_at.desc())
    ).scalars().all()
    return [ImportRow.model_validate(r) for r in rows]


class ImportDeleteResult(BaseModel):
    deleted_transactions: int
    import_id: int


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
        raise HTTPException(status_code=404, detail="Import not found.")
    res = session.execute(
        delete(Transaction).where(Transaction.import_id == import_id)
    )
    deleted = int(cast(Any, res).rowcount or 0)
    session.delete(imp)
    session.commit()
    return ImportDeleteResult(deleted_transactions=deleted, import_id=import_id)
