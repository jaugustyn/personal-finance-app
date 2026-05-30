"""POST /imports — upload a bank CSV and ingest it.

Three flows are supported:

1. **Explicit source** (legacy) — ``source=pekao`` form field; uses the
   registered vendor parser.
2. **Auto-detect** — omit ``source`` (or pass ``auto``); the router peeks
   headers and picks a parser via :func:`finance.ingestion.registry.detect_source`.
   Falls back to the generic parser with header-alias detection if no vendor
   matches.
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

from finance.db import SessionLocal, get_session
from finance.domain.dto import ImportSummary
from finance.domain.enums import BankSource
from finance.domain.models import Import, Transaction
from finance.ingestion import ParseError
from finance.ingestion.generic import GenericCsvParser, preview_csv
from finance.ingestion.registry import detect_source
from finance.ingestion.service import ingest_file
from finance.ml.classification.predict import ClassifierNotAvailable, reclassify_unlabelled

router = APIRouter(prefix="/imports", tags=["imports"])
logger = logging.getLogger(__name__)

# Maximum CSV upload size (10 MiB). Hand-tuned: full-year Pekao XLSX export
# is ~1.5 MiB; this leaves headroom and protects against zip-bomb-style abuse.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = (".csv", ".tsv", ".txt", ".xlsx", ".xls")
ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "text/plain",
    "text/tab-separated-values",
    "application/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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


class PreviewResponse(BaseModel):
    headers: list[str]
    sample_rows: list[dict[str, str]]
    delimiter: str
    encoding: str
    detected_source: BankSource | None
    detected_mapping: dict[str, str | None]


@router.post("/preview", response_model=PreviewResponse)
def preview_import(file: UploadFile = File(...)) -> PreviewResponse:
    raw = _read_validated(file)
    try:
        prev = preview_csv(io.BytesIO(raw))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Cannot parse CSV: {exc}") from exc
    return PreviewResponse(
        headers=prev.headers,
        sample_rows=prev.sample_rows,
        delimiter=prev.delimiter,
        encoding=prev.encoding,
        detected_source=detect_source(prev.headers),
        detected_mapping=prev.detected_mapping,
    )


@router.post("", response_model=ImportSummary)
def upload_import(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    source: str | None = Form(None),
    column_map: str | None = Form(None),
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
        if column_map:
            try:
                mapping = json.loads(column_map)
            except json.JSONDecodeError as exc:
                raise HTTPException(
                    status_code=422, detail=f"Invalid column_map JSON: {exc}"
                ) from exc
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
        )
        if summary.inserted > 0:
            background.add_task(_suggest_import_categories, summary.import_id)
        return summary
    except ParseError as exc:
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
