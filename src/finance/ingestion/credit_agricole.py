"""Credit Agricole CSV parser ("Historia operacji" export, semicolon-separated).

Notes:
- One wide row per operation; only the columns relevant to the operation
  kind (transfer, card, BLIK, tax, deposit, ...) are filled.
- Column names repeat (``Kwota``, ``Prowizja``, ``Okres``, ``Adres``, ...).
  Headers are de-duplicated by ``csv_dict_reader``, so ``Kwota`` is the first
  (main, signed) amount and ``Kwota (2)`` the FX section amount.
- Amount and currency share one cell: ``-45,99 PLN``.
- Date format: DD.MM.YYYY.
"""
from __future__ import annotations

from typing import IO

from finance.domain.category_mapping import map_source_category
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

_EXPECTED_HEADER = {
    "Na rachunek",
    "Kategoria transakcji",
    "Rodzaj transakcji",
    "Data operacji",
    "Data księgowania",
    "Kwota",
    "Saldo po operacji",
}


def _first(row: dict[str, str], *columns: str) -> str:
    for column in columns:
        value = (row.get(column) or "").strip()
        if value:
            return value
    return ""


@register_parser
class CreditAgricoleParser(BankParser):
    source = BankSource.CREDIT_AGRICOLE
    expected_headers = _EXPECTED_HEADER

    def parse(self, stream: IO[bytes], filename: str = "") -> list[TransactionDTO]:
        reader = csv_dict_reader(decode_csv(stream.read()))
        if reader.fieldnames is None:
            raise ParseError("Empty Credit Agricole CSV")
        missing = _EXPECTED_HEADER - set(reader.fieldnames)
        if missing:
            raise ParseError(f"Credit Agricole CSV missing columns: {sorted(missing)}")

        out: list[TransactionDTO] = []
        for row in reader:
            booking_dt = parse_date(_first(row, "Data księgowania", "Data operacji"))
            if booking_dt is None:
                continue

            raw_amount = _first(row, "Kwota")
            amount, currency = parse_amount_with_currency(raw_amount)
            if amount is None:
                raise ParseError(f"Invalid amount: {raw_amount!r}")
            direction = (
                TransactionDirection.CREDIT if amount > 0 else TransactionDirection.DEBIT
            )
            counterparty = "Nadawca" if direction is TransactionDirection.CREDIT else "Odbiorca"
            raw_category = _first(row, "Kategoria transakcji") or None

            out.append(
                TransactionDTO(
                    booking_date=booking_dt.date(),
                    booking_datetime=None,
                    amount=amount,
                    currency=currency or "PLN",
                    direction=direction,
                    merchant=_first(row, counterparty, "Miejsce transakcji", "Opis"),
                    title=_first(row, "Tytuł", "Opis szczegółowy", "Opis"),
                    raw_category=raw_category,
                    raw_transaction_type=_first(row, "Rodzaj transakcji") or None,
                    category=map_source_category(raw_category),
                    source=BankSource.CREDIT_AGRICOLE,
                    external_id=_first(
                        row, "Numer referencyjny", "Numer transakcji", "Numer transakcji BLIK"
                    )
                    or None,
                )
            )
        return out
