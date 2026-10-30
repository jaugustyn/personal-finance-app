"""Generic CSV parser with column-mapping (PL/EN header heuristics).

Goal: accept arbitrary bank exports without bespoke code per institution.
The parser either:
  1. Receives an explicit ``column_map`` (preferred — no ambiguity), or
  2. Auto-detects columns by matching header names against PL/EN aliases.

Reading a file (:func:`read_csv_table`) is shared by preview, parsing and
quality checks so they always agree on headers and rows:
- encoding is sniffed (utf-8-sig / utf-8 / cp1250 / latin1);
- the header row is the first of the leading lines that contains a date and
  an amount column, so bank preambles (account number, period, ...) above the
  table are skipped; the delimiter is sniffed from that line;
- repeated header names are suffixed (``Kwota``, ``Kwota (2)``).

Amounts come from a signed ``amount`` column or, for exports without one,
from separate ``debit_amount`` / ``credit_amount`` columns. A currency code
inside the amount cell (``-45,99 PLN``) is used when no currency column is
mapped.

Note: this is the **flexible** path. Bank-specific parsers (``pekao``,
``revolut``, ``credit_agricole``) are detected first so users with
vendor-exact exports get deterministic mapping; the generic parser is the
fallback / "any CSV" entry.
"""
from __future__ import annotations

import csv
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import IO

from finance.domain.category_mapping import map_source_category
from finance.domain.dto import TransactionDTO
from finance.domain.enums import BankSource, TransactionDirection
from finance.ingestion.base import BankParser, ParseError
from finance.ingestion.csv_utils import (
    csv_dict_reader,
    detect_encoding,
    parse_amount_with_currency,
    parse_date,
    sniff_delimiter,
    unique_headers,
)
from finance.ingestion.schema import (
    SPLIT_AMOUNT_FIELDS,
    clean_column_map,
    missing_required_fields,
)

# ---------------------------------------------------------------------------
# Header aliases — matched after `_norm` (lower-case, Polish letters folded to
# ASCII, whitespace collapsed). Order is priority: the first alias present in
# the file wins, and fields are resolved in dict order without reusing a
# header, so the result is deterministic.
# ---------------------------------------------------------------------------
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "date": (
        "data ksiegowania", "data operacji", "data transakcji", "data zrealizowania",
        "booking date", "booking_date", "transaction date", "transaction_date",
        "posted date", "posted_date", "date", "data", "data waluty", "value date",
        "value_date",
    ),
    "amount": (
        "kwota operacji", "kwota transakcji", "kwota", "wartosc", "amount", "value",
        "total",
    ),
    "debit_amount": (
        "obciazenia", "obciazenie", "kwota obciazenia", "wydatki", "debit", "debits",
        "debit amount", "withdrawal", "withdrawals", "money out", "paid out",
    ),
    "credit_amount": (
        "uznania", "uznanie", "kwota uznania", "wplywy", "wplyw", "credit", "credits",
        "credit amount", "deposit", "deposits", "money in", "paid in",
    ),
    "currency": ("waluta", "currency", "ccy"),
    "merchant": (
        "nadawca / odbiorca", "kontrahent", "odbiorca", "nazwa odbiorcy", "sprzedawca",
        "merchant", "payee", "counterparty", "opis", "description",
    ),
    "title": (
        "tytulem", "tytul", "tytul operacji", "opis operacji", "title", "memo",
        "details", "narrative", "szczegoly",
    ),
    "category": ("kategoria", "kategoria transakcji", "category", "tag"),
    "transaction_type": (
        "typ operacji", "typ transakcji", "rodzaj operacji", "rodzaj transakcji",
        "transaction type", "operation type", "transaction_type", "operation_type",
        "rodzaj", "typ", "type",
    ),
    "external_id": (
        "numer referencyjny", "referencja", "reference", "transaction id",
        "id transakcji", "numer transakcji", "external id", "id",
    ),
}

_POLISH_TO_ASCII = str.maketrans("ąćęłńóśźż", "acelnoszz")
#: How many leading lines may hold a bank preamble before the header row.
_HEADER_SCAN_LINES = 30


def _norm(s: str) -> str:
    folded = " ".join(s.lower().translate(_POLISH_TO_ASCII).split())
    # mBank-style "#Data operacji", "Kwota:" etc.
    return folded.strip("#*:. ")


def auto_detect_columns(headers: list[str]) -> dict[str, str | None]:
    """Map logical fields → actual header name (case-preserving) or None."""
    norm_to_orig: dict[str, str] = {}
    for header in headers:
        if header:
            norm_to_orig.setdefault(_norm(header), header)
    used: set[str] = set()
    out: dict[str, str | None] = {}
    for field, aliases in _FIELD_ALIASES.items():
        match = None
        if not (field in SPLIT_AMOUNT_FIELDS and out.get("amount")):
            for alias in aliases:
                candidate = norm_to_orig.get(alias)
                if candidate is not None and candidate not in used:
                    match = candidate
                    break
        if match is not None:
            used.add(match)
        out[field] = match
    return out


def resolve_column_map(
    column_map: Mapping[str, object] | None,
    headers: list[str],
) -> dict[str, str]:
    """Explicit user mapping when given, otherwise auto-detected columns."""
    if column_map:
        return clean_column_map(column_map)
    return {k: v for k, v in auto_detect_columns(headers).items() if v is not None}


def _looks_like_header(cells: list[str]) -> bool:
    detected = auto_detect_columns(unique_headers(cells))
    return bool(detected["date"]) and any(
        detected[field] for field in ("amount", *SPLIT_AMOUNT_FIELDS)
    )


def _locate_header(lines: list[str]) -> tuple[int, str]:
    """Index and delimiter of the header row; falls back to the first line."""
    for index, line in enumerate(lines[:_HEADER_SCAN_LINES]):
        delimiter = sniff_delimiter(line)
        cells = next(csv.reader([line], delimiter=delimiter), [])
        if _looks_like_header(cells):
            return index, delimiter
    return 0, sniff_delimiter(lines[0] if lines else "")


@dataclass(frozen=True)
class CsvTable:
    headers: list[str]
    rows: list[dict[str, str]]
    delimiter: str
    encoding: str
    #: 1-based line number of the header row in the file.
    header_line: int


def read_csv_table(raw: bytes) -> CsvTable:
    encoding = detect_encoding(raw)
    lines = raw.decode(encoding, errors="replace").splitlines(keepends=True)
    header_index, delimiter = _locate_header(lines)
    reader = csv_dict_reader("".join(lines[header_index:]), delimiter)
    headers = list(reader.fieldnames or [])
    rows = [
        {key: (value or "") for key, value in row.items() if key is not None}
        for row in reader
    ]
    return CsvTable(
        headers=headers,
        rows=rows,
        delimiter=delimiter,
        encoding=encoding,
        header_line=header_index + 1,
    )


@dataclass(frozen=True)
class RowAmount:
    #: Raw cell text ("" when every mapped amount cell is empty).
    raw: str
    amount: Decimal | None
    #: Currency code found inside the amount cell, if any.
    currency: str | None


def row_amount(row: Mapping[str, str], mapping: Mapping[str, str]) -> RowAmount:
    """Signed amount from ``amount`` or from ``debit_amount``/``credit_amount``.

    Debit values become negative and credit values positive regardless of the
    sign used in the export. ``amount`` wins when both styles are mapped.
    """
    amount_col = mapping.get("amount")
    if amount_col:
        raw = (row.get(amount_col) or "").strip()
        amount, currency = parse_amount_with_currency(raw)
        return RowAmount(raw, amount, currency)

    total = Decimal(0)
    currency = None
    raws: list[str] = []
    for field, sign in (("debit_amount", -1), ("credit_amount", 1)):
        column = mapping.get(field)
        raw = (row.get(column) or "").strip() if column else ""
        if not raw:
            continue
        raws.append(raw)
        value, cell_currency = parse_amount_with_currency(raw)
        if value is None:
            return RowAmount(" ".join(raws), None, None)
        total += sign * abs(value)
        currency = currency or cell_currency
    return RowAmount(" ".join(raws), total if raws else None, currency)


@dataclass(frozen=True)
class CsvPreview:
    """Result of inspecting an upload before ingest."""

    headers: list[str]
    sample_rows: list[dict[str, str]]
    delimiter: str
    encoding: str
    detected_mapping: dict[str, str | None]


def preview_csv(stream: IO[bytes], *, max_rows: int = 5) -> CsvPreview:
    table = read_csv_table(stream.read())
    return CsvPreview(
        headers=table.headers,
        sample_rows=table.rows[:max_rows],
        delimiter=table.delimiter,
        encoding=table.encoding,
        detected_mapping=auto_detect_columns(table.headers),
    )


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
class GenericCsvParser(BankParser):
    """Flexible CSV parser. Not auto-registered — instantiated per-request.

    Construct with an explicit ``column_map`` (logical → header name) when
    the user has confirmed it in the UI. Without one, headers are matched
    against PL/EN aliases.
    """

    source = BankSource.UNKNOWN

    def __init__(self, column_map: dict[str, str] | None = None) -> None:
        self.column_map = column_map or {}

    def parse(self, stream: IO[bytes], filename: str = "") -> list[TransactionDTO]:
        table = read_csv_table(stream.read())
        if not table.headers:
            raise ParseError("Empty CSV (no header row).")

        mapping = resolve_column_map(self.column_map, table.headers)
        missing_required = missing_required_fields(mapping)
        if missing_required:
            raise ParseError(
                f"Could not locate required columns {missing_required!r} in "
                f"{table.headers!r}. Provide an explicit column_map."
            )

        def cell(row: dict[str, str], field: str) -> str:
            column = mapping.get(field)
            return (row.get(column) or "").strip() if column else ""

        out: list[TransactionDTO] = []
        for row in table.rows:
            dt = parse_date(cell(row, "date"))
            if dt is None:
                continue
            parsed = row_amount(row, mapping)
            if parsed.amount is None:
                continue
            amount = parsed.amount
            direction = (
                TransactionDirection.CREDIT if amount > 0 else TransactionDirection.DEBIT
            )
            merchant = cell(row, "merchant")
            title = cell(row, "title")
            raw_category = cell(row, "category") or None

            out.append(
                TransactionDTO(
                    booking_date=dt.date(),
                    booking_datetime=dt if dt.time() != datetime.min.time() else None,
                    amount=amount,
                    currency=(cell(row, "currency") or parsed.currency or "PLN").upper(),
                    direction=direction,
                    merchant=merchant or title or "(brak)",
                    title=title,
                    raw_category=raw_category,
                    raw_transaction_type=cell(row, "transaction_type") or None,
                    category=map_source_category(raw_category),
                    source=BankSource.UNKNOWN,
                    external_id=cell(row, "external_id") or None,
                )
            )
        return out
