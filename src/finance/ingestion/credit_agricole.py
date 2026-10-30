"""Credit Agricole CSV parser ("Historia operacji" export, semicolon-separated).

Notes:
- One wide row per operation; only the columns relevant to the operation
  kind (transfer, card, BLIK, tax, deposit, ...) are filled.
- Column names repeat (``Kwota``, ``Prowizja``, ``Okres``, ``Adres``, ...).
  Headers are de-duplicated by ``csv_dict_reader`` (``Kwota``, ``Kwota (2)``).
  The signed operation amount is ``Kwota (2)`` (just before
  ``Saldo po operacji``); the first ``Kwota`` is used as a fallback.
- Amount and currency share one cell: ``-41,00 PLN``.
- Dates: ``DD.MM.YYYY`` or ``DD.MM.YYYY HH:MM:SS``.
- ``Kategoria transakcji`` holds the operation kind (``Przelew na telefon
  BLIK``), not a spending category, so it feeds ``raw_transaction_type``.
- Polish letters in headers may arrive broken (wrong encoding, ``Tytu ``), so
  columns are looked up by an ASCII-only key that ignores them.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import IO

from finance.domain.dto import TransactionDTO
from finance.domain.enums import BankSource, TransactionDirection
from finance.ingestion.base import BankParser, ParseError
from finance.ingestion.csv_utils import (
    csv_dict_reader,
    decode_csv,
    parse_amount_with_currency,
    parse_date,
)
from finance.ingestion.registry import register_parser

# ASCII-only names, so auto-detection works even when Polish letters are broken.
_EXPECTED_HEADER = {
    "Na rachunek",
    "Kategoria transakcji",
    "Rodzaj transakcji",
    "Data operacji",
    "Kwota",
    "Saldo po operacji",
    "Opis",
}


def _key(header: str) -> str:
    """ASCII letters and digits only: ``Tytuł``, ``Tytu `` and ``Tytu?`` match."""
    return re.sub(r"[^a-z0-9]", "", header.lower())


@register_parser
class CreditAgricoleParser(BankParser):
    source = BankSource.CREDIT_AGRICOLE
    expected_headers = _EXPECTED_HEADER

    def parse(self, stream: IO[bytes], filename: str = "") -> list[TransactionDTO]:
        reader = csv_dict_reader(decode_csv(stream.read()))
        if reader.fieldnames is None:
            raise ParseError("Empty Credit Agricole CSV")
        columns: dict[str, str] = {}
        for header in reader.fieldnames:
            columns.setdefault(_key(header), header)
        missing = {name for name in _EXPECTED_HEADER if _key(name) not in columns}
        if missing:
            raise ParseError(f"Credit Agricole CSV missing columns: {sorted(missing)}")

        def first(row: dict[str, str], *names: str) -> str:
            for name in names:
                column = columns.get(_key(name))
                value = (row.get(column) or "").strip() if column else ""
                if value:
                    return value
            return ""

        out: list[TransactionDTO] = []
        for row in reader:
            booking_dt = parse_date(first(row, "Data księgowania", "Data operacji"))
            if booking_dt is None:
                continue

            raw_amount = first(row, "Kwota (2)", "Kwota")
            if not raw_amount:
                continue
            amount, currency = parse_amount_with_currency(raw_amount)
            if amount is None:
                raise ParseError(f"Invalid amount: {raw_amount!r}")
            direction = (
                TransactionDirection.CREDIT if amount > 0 else TransactionDirection.DEBIT
            )
            counterparty = "Nadawca" if direction is TransactionDirection.CREDIT else "Odbiorca"

            out.append(
                TransactionDTO(
                    booking_date=booking_dt.date(),
                    booking_datetime=(
                        booking_dt if booking_dt.time() != datetime.min.time() else None
                    ),
                    amount=amount,
                    currency=currency or "PLN",
                    direction=direction,
                    merchant=first(row, counterparty, "Miejsce transakcji", "Opis"),
                    title=first(row, "Tytuł", "Opis szczegółowy", "Opis"),
                    raw_category=None,
                    raw_transaction_type=(
                        first(row, "Rodzaj transakcji", "Kategoria transakcji", "Opis")
                        or None
                    ),
                    category=None,
                    source=BankSource.CREDIT_AGRICOLE,
                    external_id=(
                        first(
                            row, "Numer referencyjny", "Numer transakcji",
                            "Numer transakcji BLIK",
                        )
                        or None
                    ),
                )
            )
        return out
