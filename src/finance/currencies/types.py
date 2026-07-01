"""Currency conversion contracts and domain errors."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal


def _normalize_currency_code(value: str | None) -> str:
    code = (value or "").strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise ValueError(f"Invalid currency code: {value!r}")
    return code


class MissingFxRate(ValueError):
    """Raised when a non-base transaction cannot be converted."""

    def __init__(self, currency: str, base_currency: str, rate_date: date) -> None:
        self.currency = _normalize_currency_code(currency)
        self.base_currency = _normalize_currency_code(base_currency)
        self.rate_date = rate_date
        super().__init__(
            f"missing_fx_rate: {self.currency}/{self.base_currency} for {rate_date.isoformat()}"
        )


@dataclass(frozen=True)
class ConversionResult:
    amount_base: Decimal
    base_currency: str
    fx_rate: Decimal
    fx_rate_date: date
    fx_rate_source: str
