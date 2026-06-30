"""External FX rate providers."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import date, timedelta
from decimal import Decimal
from typing import Protocol

NBP_LOOKBACK_DAYS = 7


class FxRateProvider(Protocol):
    def fetch_rate(self, currency: str, rate_date: date) -> tuple[Decimal, date] | None:
        """Return provider rate and effective date, or None when unavailable."""


class NbpFxRateProvider:
    def fetch_rate(self, currency: str, rate_date: date) -> tuple[Decimal, date] | None:
        if currency == "PLN":
            return Decimal("1"), rate_date
        for table in ("a", "b"):
            for offset in range(NBP_LOOKBACK_DAYS + 1):
                day = rate_date - timedelta(days=offset)
                url = (
                    "https://api.nbp.pl/api/exchangerates/rates/"
                    f"{table}/{currency}/{day.isoformat()}/?format=json"
                )
                try:
                    with urllib.request.urlopen(url, timeout=5) as response:
                        payload = json.loads(response.read().decode("utf-8"))
                except urllib.error.HTTPError as exc:
                    if exc.code == 404:
                        continue
                    return None
                except Exception:  # noqa: BLE001
                    return None
                rates = payload.get("rates") if isinstance(payload, dict) else None
                if not rates:
                    continue
                rate = Decimal(str(rates[0]["mid"]))
                effective_date = date.fromisoformat(str(rates[0]["effectiveDate"]))
                return rate, effective_date
        return None
