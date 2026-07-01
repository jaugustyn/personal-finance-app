"""Generic CSV parser with column-mapping (PL/EN header heuristics).

Goal: accept arbitrary bank exports without bespoke code per institution.
The parser either:
  1. Receives an explicit ``column_map`` (preferred — no ambiguity), or
  2. Auto-detects columns by matching header names against PL/EN aliases.

Encoding and delimiter are sniffed (utf-8 / utf-8-sig / cp1250 / latin1;
``,`` / ``;`` / ``\t``). Date format is inferred from the first non-empty
value (DD.MM.YYYY, YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY).

Note: this is the **flexible** path. Bank-specific parsers (``pekao``,
``revolut``) remain registered first so users with vendor-exact exports get
deterministic mapping; the generic parser is the fallback / "any CSV" entry.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime
from typing import IO

from finance.domain.category_mapping import map_source_category
from finance.domain.dto import TransactionDTO
from finance.domain.enums import BankSource, TransactionDirection
from finance.ingestion.base import BankParser, ParseError
from finance.ingestion.csv_utils import (
    decode_csv,
    parse_date,
    parse_decimal,
    sniff_delimiter,
)
from finance.ingestion.schema import REQUIRED_IMPORT_FIELDS, clean_column_map

# ---------------------------------------------------------------------------
# Header aliases — case-insensitive, whitespace-collapsed match.
# ---------------------------------------------------------------------------
_DATE_ALIASES = {
    "data księgowania", "data ksiegowania", "data operacji", "data transakcji",
    "data zrealizowania", "data", "date", "booking date", "transaction date",
    "booking_date", "transaction_date", "posted date", "posted_date",
    "value date", "value_date", "data waluty",
}
_AMOUNT_ALIASES = {
    "kwota", "kwota operacji", "kwota transakcji", "wartość", "wartosc",
    "amount", "value", "total",
}
_CURRENCY_ALIASES = {"waluta", "currency", "ccy"}
_MERCHANT_ALIASES = {
    "nadawca / odbiorca", "kontrahent", "odbiorca", "sprzedawca", "merchant",
    "payee", "description", "opis", "counterparty", "nazwa odbiorcy",
}
_TITLE_ALIASES = {
    "tytułem", "tytulem", "tytuł", "tytul", "opis operacji", "title",
    "memo", "details", "narrative", "rodzaj", "type",
}
_CATEGORY_ALIASES = {"kategoria", "category", "tag"}
_EXTERNAL_ID_ALIASES = {
    "numer referencyjny", "referencja", "reference", "transaction id",
    "id", "external id",
}

# Each "logical" column → set of accepted header names.
_FIELD_ALIASES: dict[str, set[str]] = {
    "date": _DATE_ALIASES,
    "amount": _AMOUNT_ALIASES,
    "currency": _CURRENCY_ALIASES,
    "merchant": _MERCHANT_ALIASES,
    "title": _TITLE_ALIASES,
    "category": _CATEGORY_ALIASES,
    "external_id": _EXTERNAL_ID_ALIASES,
}


def _norm(s: str) -> str:
    return " ".join(s.strip().lower().split())


def auto_detect_columns(headers: list[str]) -> dict[str, str | None]:
    """Map logical fields → actual header name (case-preserving) or None."""
    norm_to_orig = {_norm(h): h for h in headers if h}
    out: dict[str, str | None] = {}
    for field, aliases in _FIELD_ALIASES.items():
        match = None
        for alias in aliases:
            if alias in norm_to_orig:
                match = norm_to_orig[alias]
                break
        out[field] = match
    return out


@dataclass(frozen=True)
class CsvPreview:
    """Result of inspecting an upload before ingest."""

    headers: list[str]
    sample_rows: list[dict[str, str]]
    delimiter: str
    encoding: str
    detected_mapping: dict[str, str | None]


def preview_csv(stream: IO[bytes], *, max_rows: int = 5) -> CsvPreview:
    raw = stream.read()
    text = decode_csv(raw)
    encoding = "utf-8" if raw.startswith(b"\xef\xbb\xbf") or _try("utf-8", raw) else "cp1250"
    delimiter = sniff_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    headers = list(reader.fieldnames or [])
    rows: list[dict[str, str]] = []
    for i, row in enumerate(reader):
        if i >= max_rows:
            break
        rows.append({k: (v or "") for k, v in row.items() if k is not None})
    return CsvPreview(
        headers=headers,
        sample_rows=rows,
        delimiter=delimiter,
        encoding=encoding,
        detected_mapping=auto_detect_columns(headers),
    )


def _try(enc: str, raw: bytes) -> bool:
    try:
        raw.decode(enc)
        return True
    except UnicodeDecodeError:
        return False


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
        text = decode_csv(stream.read())
        delimiter = sniff_delimiter(text)
        reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
        headers = list(reader.fieldnames or [])
        if not headers:
            raise ParseError("Empty CSV (no header row).")

        mapping = clean_column_map(self.column_map) if self.column_map else {
            k: v for k, v in auto_detect_columns(headers).items() if v is not None
        }
        missing_required = sorted(REQUIRED_IMPORT_FIELDS - set(mapping))
        if missing_required:
            raise ParseError(
                f"Could not locate required columns {missing_required!r} in {headers!r}. "
                "Provide an explicit column_map."
            )

        date_col = mapping["date"]
        amount_col = mapping["amount"]
        currency_col = mapping.get("currency")
        merchant_col = mapping.get("merchant")
        title_col = mapping.get("title")
        category_col = mapping.get("category")
        ext_col = mapping.get("external_id")

        out: list[TransactionDTO] = []
        for row in reader:
            dt = parse_date(row.get(date_col, "") or "")
            if dt is None:
                continue
            amount = parse_decimal(row.get(amount_col, "") or "")
            if amount is None:
                continue
            direction = (
                TransactionDirection.CREDIT if amount > 0 else TransactionDirection.DEBIT
            )
            currency = (row.get(currency_col, "PLN") if currency_col else "PLN").strip().upper()
            merchant = (row.get(merchant_col, "") if merchant_col else "").strip()
            title = (row.get(title_col, "") if title_col else "").strip()
            raw_category = (row.get(category_col, "") if category_col else "").strip() or None
            external_id = (row.get(ext_col, "") if ext_col else "").strip() or None

            out.append(
                TransactionDTO(
                    booking_date=dt.date(),
                    booking_datetime=dt if dt.time() != datetime.min.time() else None,
                    amount=amount,
                    currency=currency or "PLN",
                    direction=direction,
                    merchant=merchant or title or "(brak)",
                    title=title,
                    raw_category=raw_category,
                    category=map_source_category(raw_category),
                    source=BankSource.UNKNOWN,
                    external_id=external_id,
                )
            )
        return out
