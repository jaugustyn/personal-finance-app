"""Public CSV helpers shared by generic import and quality checks."""
from __future__ import annotations

import csv
import io
import re
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal, InvalidOperation


def decode_csv(raw: bytes) -> str:
    """Best-effort decode: utf-8-sig -> utf-8 -> cp1250 -> latin1."""
    for enc in ("utf-8-sig", "utf-8", "cp1250", "latin1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin1", errors="replace")


def sniff_delimiter(sample: str) -> str:
    """Pick the delimiter that yields the most columns on the first line."""
    head = sample.splitlines()[0] if sample else ""
    counts = {d: head.count(d) for d in (";", ",", "\t", "|")}
    delimiter, count = max(counts.items(), key=lambda item: item[1])
    return delimiter if count > 0 else ","


def unique_headers(headers: Sequence[str | None]) -> list[str]:
    """Clean header names and suffix repeated ones: ``Kwota``, ``Kwota (2)``.

    Some bank exports (e.g. Credit Agricole) repeat column names; without
    this, ``csv.DictReader`` silently keeps only the last repeated column.
    """
    seen: Counter[str] = Counter()
    out: list[str] = []
    for header in headers:
        name = (header or "").replace("﻿", "").replace("\xa0", " ").strip()
        seen[name] += 1
        out.append(f"{name} ({seen[name]})" if name and seen[name] > 1 else name)
    return out


def csv_dict_reader(text: str, delimiter: str | None = None) -> csv.DictReader[str]:
    """DictReader with a sniffed delimiter and unique, cleaned header names."""
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter or sniff_delimiter(text))
    if reader.fieldnames is not None:
        reader.fieldnames = unique_headers(reader.fieldnames)
    return reader


DATE_FORMATS = (
    "%d.%m.%Y",
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
)


def parse_date(raw: str) -> datetime | None:
    raw = raw.strip()
    if not raw:
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def parse_decimal(raw: str) -> Decimal | None:
    raw = raw.strip().replace(" ", "").replace(" ", "").replace("−", "-")
    if not raw:
        return None
    # If both ',' and '.' are present, the rightmost one is the decimal separator.
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", ".")
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


_AMOUNT_WITH_CURRENCY = re.compile(r"([A-Za-z]{3})?([^A-Za-z]*?)([A-Za-z]{3})?")


def parse_amount_with_currency(raw: str) -> tuple[Decimal | None, str | None]:
    """Parse ``-45,99 PLN`` / ``PLN -45,99`` / ``-45,99`` into (amount, currency)."""
    match = _AMOUNT_WITH_CURRENCY.fullmatch(raw.strip())
    if match is None:
        return None, None
    prefix, number, suffix = match.groups()
    if prefix and suffix:
        return None, None
    currency = (prefix or suffix or "").upper() or None
    return parse_decimal(number), currency
