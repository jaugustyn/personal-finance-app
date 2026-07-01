"""Public CSV helpers shared by generic import and quality checks."""
from __future__ import annotations

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
    raw = raw.strip().replace(" ", "").replace("\u00a0", "")
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
