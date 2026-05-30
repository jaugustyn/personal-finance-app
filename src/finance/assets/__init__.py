"""Asset pricing via yfinance with FX conversion to PLN.

Resilient: catches network errors and returns ``None`` so callers can fall back
to last known price.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from typing import TYPE_CHECKING

from finance.observability import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("assets.pricing")


@dataclass(frozen=True)
class Quote:
    symbol: str
    price: Decimal
    currency: str


def _decimal(value: float | int | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:  # noqa: BLE001
        return None


def fetch_quote(symbol: str) -> Quote | None:
    """Fetch latest price for ``symbol`` using yfinance fast_info."""
    try:
        import yfinance as yf  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("yfinance_missing")
        return None

    try:
        ticker = yf.Ticker(symbol)
        fast = ticker.fast_info
        price = _decimal(getattr(fast, "last_price", None))
        currency = (getattr(fast, "currency", None) or "USD").upper()
        if price is None or price <= 0:
            hist = ticker.history(period="5d")
            if not hist.empty:
                price = _decimal(float(hist["Close"].iloc[-1]))
        if price is None:
            return None
        return Quote(symbol=symbol, price=price, currency=currency)
    except Exception as exc:  # noqa: BLE001
        logger.warning("quote_fetch_failed", symbol=symbol, error=str(exc))
        return None


@lru_cache(maxsize=32)
def _fx_rate_cached(currency: str) -> Decimal | None:
    """USD->PLN, EUR->PLN, etc. Returns rate per 1 unit of ``currency`` in PLN."""
    if currency.upper() == "PLN":
        return Decimal("1")
    pair = f"{currency.upper()}PLN=X"
    quote = fetch_quote(pair)
    if quote is None:
        return None
    return quote.price


def fx_to_pln(currency: str) -> Decimal:
    """Returns FX rate to PLN, falling back to 1.0 if unavailable."""
    rate = _fx_rate_cached(currency.upper())
    if rate is None or rate <= 0:
        logger.info("fx_fallback", currency=currency)
        return Decimal("1")
    return rate


def value_in_pln(price: Decimal, quantity: Decimal, currency: str) -> Decimal:
    rate = fx_to_pln(currency)
    return (price * quantity * rate).quantize(Decimal("0.01"))
