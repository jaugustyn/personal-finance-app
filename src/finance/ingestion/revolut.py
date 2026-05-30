"""Revolut CSV parser (Polish locale export).

Header (semicolon-separated):
    Rodzaj;Produkt;Data rozpoczęcia;Data zrealizowania;Opis;Kwota;Opłata;
    Waluta;State;Saldo

Notes:
- Date format: DD.MM.YYYY HH:MM (no seconds in the export).
- State value for completed: "ZAKOŃCZONO".
- "Wymiana" rows (currency exchange between own wallets) appear in BOTH
  wallets. We keep them but leave `category` null — they are not real
  expenses and must not pollute the training set.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import IO

from finance.domain.dto import TransactionDTO
from finance.domain.enums import BankSource, TransactionDirection
from finance.ingestion.base import BankParser, ParseError
from finance.ingestion.registry import register_parser

_EXPECTED_HEADER = {
    "Rodzaj",
    "Data rozpoczęcia",
    "Data zrealizowania",
    "Opis",
    "Kwota",
    "Waluta",
    "State",
}
_COMPLETED = "ZAKOŃCZONO"


def _parse_decimal(raw: str) -> Decimal:
    raw = raw.strip().replace(" ", "").replace(",", ".")
    if not raw:
        raise ParseError("Missing amount")
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise ParseError(f"Invalid amount: {raw!r}") from exc


def _parse_dt(raw: str) -> datetime | None:
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M", "%d.%m.%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise ParseError(f"Invalid date: {raw!r}")


@register_parser
class RevolutParser(BankParser):
    source = BankSource.REVOLUT
    expected_headers = _EXPECTED_HEADER

    def parse(self, stream: IO[bytes], filename: str = "") -> list[TransactionDTO]:
        text = stream.read().decode("utf-8-sig", errors="replace")
        reader = csv.DictReader(io.StringIO(text), delimiter=";")
        if reader.fieldnames is None:
            raise ParseError("Empty Revolut CSV")
        missing = _EXPECTED_HEADER - set(reader.fieldnames)
        if missing:
            raise ParseError(f"Revolut CSV missing columns: {sorted(missing)}")

        out: list[TransactionDTO] = []
        for row in reader:
            if (row.get("State") or "").strip().upper() != _COMPLETED:
                continue

            booking_dt = _parse_dt(row.get("Data zrealizowania") or "") or _parse_dt(
                row.get("Data rozpoczęcia") or ""
            )
            if booking_dt is None:
                continue

            amount = _parse_decimal(row.get("Kwota") or "")
            direction = (
                TransactionDirection.CREDIT if amount > 0 else TransactionDirection.DEBIT
            )

            out.append(
                TransactionDTO(
                    booking_date=booking_dt.date(),
                    booking_datetime=booking_dt,
                    amount=amount,
                    currency=(row.get("Waluta") or "").strip().upper() or "PLN",
                    direction=direction,
                    merchant=(row.get("Opis") or "").strip(),
                    title=(row.get("Rodzaj") or "").strip(),
                    raw_category=(row.get("Rodzaj") or "").strip() or None,
                    source=BankSource.REVOLUT,
                )
            )
        return out
