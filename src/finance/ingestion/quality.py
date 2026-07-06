"""Deterministic quality checks for transaction imports."""
from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finance.currencies import MissingFxRate, convert_amount, resolve_base_currency
from finance.domain.dto import TransactionDTO
from finance.domain.enums import BankSource
from finance.domain.models import Transaction
from finance.ingestion.base import BankParser
from finance.ingestion.csv_utils import (
    decode_csv,
    parse_date,
    parse_decimal,
    sniff_delimiter,
)
from finance.ingestion.generic import GenericCsvParser, auto_detect_columns
from finance.ingestion.schema import REQUIRED_IMPORT_FIELDS, clean_column_map
from finance.ingestion.service import compute_dedup_hash
from finance.ingestion.types import (
    ImportQualityIssue,
    ImportQualityReport,
    IssueSeverity,
)
from finance.transactions.normalization import normalize_text


def assess_import_quality(
    session: Session,
    *,
    source: BankSource,
    filename: str,
    raw: bytes,
    parser: BankParser,
    missing_fx_severity: IssueSeverity = "error",
) -> ImportQualityReport:
    """Inspect an upload before committing it to the database."""
    total_rows = _csv_data_row_count(raw)
    issues: list[ImportQualityIssue] = []
    dtos: list[TransactionDTO] = []
    generic_mapping: dict[str, str] | None = None

    if isinstance(parser, GenericCsvParser):
        generic_mapping = _generic_mapping(parser, raw)
        issues.extend(_generic_row_issues(raw, generic_mapping))
        if any(
            issue.severity == "error"
            and (
                issue.code.startswith("missing_required_mapping_")
                or issue.code.startswith("mapped_column_missing_")
            )
            for issue in issues
        ):
            return _report(total_rows=total_rows, valid_rows=0, issues=issues)

    try:
        dtos = parser.parse(io.BytesIO(raw), filename=filename)
    except Exception:  # noqa: BLE001 - quality should report, not crash preview
        issues.append(ImportQualityIssue("parse_error", "error", 1, []))
        dtos = []

    issues.extend(
        _dto_issues(
            session,
            dtos,
            source=source,
            include_content_issues=generic_mapping is None,
            missing_fx_severity=missing_fx_severity,
        )
    )
    return _report(total_rows=total_rows, valid_rows=len(dtos), issues=issues)


def _report(
    *,
    total_rows: int,
    valid_rows: int,
    issues: list[ImportQualityIssue],
) -> ImportQualityReport:
    merged = _merge_issues(issues)
    return ImportQualityReport(
        total_rows=total_rows,
        valid_rows=valid_rows,
        blocking_issues=sum(issue.count for issue in merged if issue.severity == "error"),
        warnings=sum(issue.count for issue in merged if issue.severity == "warning"),
        issues=merged,
    )


def _merge_issues(issues: list[ImportQualityIssue]) -> list[ImportQualityIssue]:
    grouped: dict[tuple[str, IssueSeverity], tuple[int, list[int]]] = {}
    for issue in issues:
        key = (issue.code, issue.severity)
        count, rows = grouped.get(key, (0, []))
        grouped[key] = (
            count + issue.count,
            _sample_rows([*rows, *issue.sample_rows]),
        )
    severity_order = {"error": 0, "warning": 1}
    return [
        ImportQualityIssue(code=code, severity=severity, count=count, sample_rows=rows)
        for (code, severity), (count, rows) in sorted(
            grouped.items(), key=lambda item: (severity_order[item[0][1]], item[0][0])
        )
    ]


def _sample_rows(rows: list[int], *, limit: int = 5) -> list[int]:
    out: list[int] = []
    for row in rows:
        if row not in out:
            out.append(row)
        if len(out) >= limit:
            break
    return out


def _csv_data_row_count(raw: bytes) -> int:
    text = decode_csv(raw)
    if not text.strip():
        return 0
    delimiter = sniff_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return sum(1 for _ in reader)


def _generic_mapping(parser: GenericCsvParser, raw: bytes) -> dict[str, str]:
    if parser.column_map:
        return clean_column_map(parser.column_map)
    text = decode_csv(raw)
    delimiter = sniff_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return {
        key: value
        for key, value in auto_detect_columns(list(reader.fieldnames or [])).items()
        if value is not None
    }


def _generic_row_issues(
    raw: bytes,
    mapping: dict[str, str],
) -> list[ImportQualityIssue]:
    text = decode_csv(raw)
    delimiter = sniff_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = set(reader.fieldnames or [])
    missing_required = sorted(REQUIRED_IMPORT_FIELDS - set(mapping))
    issues: list[ImportQualityIssue] = [
        ImportQualityIssue(
            f"missing_required_mapping_{field}",
            "error",
            1,
            [],
        )
        for field in missing_required
    ]
    missing_columns = [
        field for field, column in mapping.items() if column and column not in headers
    ]
    issues.extend(
        ImportQualityIssue(f"mapped_column_missing_{field}", "error", 1, [])
        for field in missing_columns
    )
    if missing_required or missing_columns:
        return issues

    date_col = mapping["date"]
    amount_col = mapping["amount"]
    currency_col = mapping.get("currency")
    merchant_col = mapping.get("merchant")
    title_col = mapping.get("title")
    row_hits: dict[tuple[str, IssueSeverity], list[int]] = defaultdict(list)

    for index, row in enumerate(reader, start=2):
        raw_date = (row.get(date_col, "") or "").strip()
        if not raw_date:
            row_hits[("missing_date", "error")].append(index)
        elif parse_date(raw_date) is None:
            row_hits[("invalid_date", "error")].append(index)

        raw_amount = (row.get(amount_col, "") or "").strip()
        amount = parse_decimal(raw_amount)
        if not raw_amount:
            row_hits[("missing_amount", "error")].append(index)
        elif amount is None:
            row_hits[("invalid_amount", "error")].append(index)
        elif amount == 0:
            row_hits[("zero_amount", "warning")].append(index)

        raw_currency = (
            (row.get(currency_col, "") or "").strip().upper() if currency_col else ""
        )
        if not currency_col or not raw_currency:
            row_hits[("missing_currency", "warning")].append(index)
        elif len(raw_currency) != 3 or not raw_currency.isalpha():
            row_hits[("invalid_currency", "warning")].append(index)

        merchant = normalize_text(row.get(merchant_col, "") if merchant_col else "")
        title = normalize_text(row.get(title_col, "") if title_col else "")
        if not merchant and not title:
            row_hits[("missing_counterparty", "warning")].append(index)

    issues.extend(
        ImportQualityIssue(code, severity, len(rows), _sample_rows(rows))
        for (code, severity), rows in row_hits.items()
    )
    return issues


def _dto_issues(
    session: Session,
    dtos: list[TransactionDTO],
    *,
    source: BankSource,
    include_content_issues: bool = True,
    missing_fx_severity: IssueSeverity = "error",
) -> list[ImportQualityIssue]:
    if not dtos:
        return []
    issues: list[ImportQualityIssue] = []
    hashes = [compute_dedup_hash(dto) for dto in dtos]
    duplicate_in_file = sum(count - 1 for count in Counter(hashes).values() if count > 1)
    if duplicate_in_file:
        issues.append(
            ImportQualityIssue("duplicate_in_file", "warning", duplicate_in_file, [])
        )

    unique_hashes = sorted(set(hashes))
    existing_hashes = set(
        session.execute(
            select(Transaction.dedup_hash).where(Transaction.dedup_hash.in_(unique_hashes))
        ).scalars()
    )
    if existing_hashes:
        issues.append(
            ImportQualityIssue("duplicate_existing", "warning", len(existing_hashes), [])
        )

    if include_content_issues:
        zero_amount = sum(1 for dto in dtos if dto.amount == 0)
        if zero_amount:
            issues.append(ImportQualityIssue("zero_amount", "warning", zero_amount, []))

        missing_counterparty = sum(1 for dto in dtos if _missing_counterparty(dto))
        if missing_counterparty:
            issues.append(
                ImportQualityIssue(
                    "missing_counterparty",
                    "warning",
                    missing_counterparty,
                    [],
                )
            )

        invalid_currency = sum(
            1 for dto in dtos if len(dto.currency) != 3 or not dto.currency.isalpha()
        )
        if invalid_currency:
            issues.append(ImportQualityIssue("invalid_currency", "warning", invalid_currency, []))

    currencies = {dto.currency for dto in dtos}
    if len(currencies) > 1:
        issues.append(ImportQualityIssue("multiple_currencies", "warning", len(currencies), []))
    base_currency = resolve_base_currency(session)
    missing_fx = {
        (dto.currency, dto.booking_date)
        for dto in dtos
        if dto.currency != base_currency and _conversion_missing(session, dto, base_currency)
    }
    if missing_fx:
        issues.append(
            ImportQualityIssue(
                "missing_fx_rate",
                missing_fx_severity,
                len(missing_fx),
                [],
            )
        )

    date_from = min(dto.booking_date for dto in dtos)
    date_to = max(dto.booking_date for dto in dtos)
    overlap_count = int(
        session.execute(
            select(func.count())
            .select_from(Transaction)
            .where(
                Transaction.source == source.value,
                Transaction.booking_date >= date_from,
                Transaction.booking_date <= date_to,
            )
        ).scalar_one()
    )
    if overlap_count:
        issues.append(
            ImportQualityIssue("date_range_overlap", "warning", overlap_count, [])
        )

    return issues


def _conversion_missing(
    session: Session,
    dto: TransactionDTO,
    base_currency: str,
) -> bool:
    try:
        convert_amount(
            session,
            amount=dto.amount,
            currency=dto.currency,
            rate_date=dto.booking_date,
            base_currency=base_currency,
            allow_fetch=False,
        )
    except MissingFxRate:
        return True
    except ValueError:
        return False
    return False


def _missing_counterparty(dto: TransactionDTO) -> bool:
    merchant = normalize_text(dto.merchant)
    title = normalize_text(dto.title)
    return merchant in {"", "brak"} and not title
