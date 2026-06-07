"""Pekao SA CSV parser ("Historia operacji" export, semicolon-separated).

Header (cp1250, observed on real export):
    Data księgowania;Data waluty;Nadawca / Odbiorca;Adres nadawcy / odbiorcy;
    Rachunek źródłowy;Rachunek docelowy;Tytułem;Kwota operacji;Waluta;
    Numer referencyjny;Typ operacji;Kategoria

Notes:
- Encoding is Windows-1250.
- Date format: DD.MM.YYYY.
- Decimal separator: comma.
- Account numbers in the export are prefixed with a single quote (Excel
  string-coercion); we strip it.
- The "Kategoria" column is the bank's own classification — used as the
  source of supervised labels via `map_pekao_category`.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import IO

from finance.domain.category_mapping import map_pekao_category
from finance.domain.dto import TransactionDTO
from finance.domain.enums import BankSource, TransactionDirection
from finance.ingestion.base import BankParser, ParseError
from finance.ingestion.registry import register_parser

_EXPECTED_HEADER = {
    "Data księgowania",
    "Nadawca / Odbiorca",
    "Tytułem",
    "Kwota operacji",
    "Waluta",
    "Kategoria",
}


def _parse_decimal(raw: str) -> Decimal:
    raw = raw.strip().replace(" ", "").replace(",", ".")
    if not raw:
        raise ParseError("Missing amount")
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise ParseError(f"Invalid amount: {raw!r}") from exc


def _parse_date(raw: str) -> datetime | None:
    raw = raw.strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%d.%m.%Y")
    except ValueError as exc:
        raise ParseError(f"Invalid date: {raw!r}") from exc


def _strip_quote(raw: str | None) -> str:
    """Remove the leading apostrophe Excel adds to account numbers."""
    if not raw:
        return ""
    return raw.lstrip("'").strip()


@register_parser
class PekaoParser(BankParser):
    source = BankSource.PEKAO
    expected_headers = _EXPECTED_HEADER

    def parse(self, stream: IO[bytes], filename: str = "") -> list[TransactionDTO]:
        text = stream.read().decode("cp1250", errors="replace")
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        if reader.fieldnames is None:
            raise ParseError("Empty Pekao CSV")
        missing = _EXPECTED_HEADER - set(reader.fieldnames)
        if missing:
            raise ParseError(f"Pekao CSV missing columns: {sorted(missing)}")

        out: list[TransactionDTO] = []
        for row in reader:
            booking_dt = _parse_date(row.get("Data księgowania") or "")
            if booking_dt is None:
                continue

            amount = _parse_decimal(row.get("Kwota operacji") or "")
            direction = (
                TransactionDirection.CREDIT if amount > 0 else TransactionDirection.DEBIT
            )

            merchant = (row.get("Nadawca / Odbiorca") or "").strip()
            title = (row.get("Tytułem") or "").strip()
            raw_category = (row.get("Kategoria") or "").strip() or None

            out.append(
                TransactionDTO(
                    booking_date=booking_dt.date(),
                    booking_datetime=None,
                    amount=amount,
                    currency=(row.get("Waluta") or "PLN").strip().upper() or "PLN",
                    direction=direction,
                    merchant=merchant,
                    title=title,
                    raw_category=raw_category,
                    category=map_pekao_category(raw_category),
                    source=BankSource.PEKAO,
                    external_id=_strip_quote(row.get("Numer referencyjny")) or None,
                )
            )
        return out
