from __future__ import annotations

from datetime import date

from finance.stats.types import month_bucket


def test_month_bucket_is_stable_yyyy_mm() -> None:
    assert month_bucket(date(2026, 1, 31)) == "2026-01"
    assert month_bucket(date(2026, 12, 1)) == "2026-12"
