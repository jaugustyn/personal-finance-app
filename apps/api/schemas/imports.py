"""Pydantic schemas for import API endpoints."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from finance.domain.enums import BankSource


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
    account_id: int | None
    suggested_account_id: int | None


class ImportUploadResponse(BaseModel):
    import_id: int
    account_id: int
    account_name: str
    source: BankSource
    inserted: int
    duplicates: int
    total_rows: int
    skipped_rows: int
    quality_report: ImportQualityReportResponse


class ImportRow(BaseModel):
    id: int
    account_id: int
    account_name: str
    source: str
    filename: str
    total_rows: int
    inserted: int
    duplicates: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ImportDeleteResult(BaseModel):
    deleted_transactions: int
    import_id: int


class ImportAccountUpdate(BaseModel):
    account_id: int = Field(gt=0)
