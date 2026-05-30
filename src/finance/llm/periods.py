"""Period parsing/extraction utilities for the Polish finance assistant."""
from __future__ import annotations

import re
from datetime import date, timedelta

import pandas as pd

PERIOD_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(ten|tym|tego|bie[zż][aą]c\w*)\s+miesi\w+", re.I), "this_month"),
    (re.compile(r"\b(zesz[lł]\w*|poprzedni\w*|ubieg[lł]\w*)\s+miesi\w+", re.I), "last_month"),
    (re.compile(r"\bostatni\w*\s+3\s+miesi\w+", re.I), "last_3_months"),
    (re.compile(r"\bostatni\w*\s+6\s+miesi\w+", re.I), "last_6_months"),
    (re.compile(r"\bostatni\w*\s+rok|ostatni\w*\s+12\s+miesi\w+", re.I), "last_12_months"),
]
YEAR_MONTH = re.compile(r"\b(20\d{2})[-/.](0?[1-9]|1[0-2])\b")
MONTH_STEMS = (
    "stycz",
    "lut",
    "marc",
    "marz",
    "kwiet",
    "kwiec",
    "maj",
    "czerw",
    "lip",
    "sierp",
    "wrze",
    "pa[zż]dziernik",
    "listopad",
    "grud",
)
MONTH_NAME = re.compile(r"\b(" + "|".join(MONTH_STEMS) + r")\w*\s+(20\d{2})\b", re.I)
MONTH_ONLY = re.compile(r"\b(" + "|".join(MONTH_STEMS) + r")\w*\b", re.I)

MONTHS_PL = {
    "styczeń": 1,
    "stycznia": 1,
    "luty": 2,
    "lutego": 2,
    "marzec": 3,
    "marca": 3,
    "kwiecień": 4,
    "kwietnia": 4,
    "maj": 5,
    "maja": 5,
    "czerwiec": 6,
    "czerwca": 6,
    "lipiec": 7,
    "lipca": 7,
    "sierpień": 8,
    "sierpnia": 8,
    "wrzesień": 9,
    "września": 9,
    "październik": 10,
    "października": 10,
    "listopad": 11,
    "listopada": 11,
    "grudzień": 12,
    "grudnia": 12,
}

MONTH_STEMS_PL: list[tuple[str, int]] = [
    ("stycz", 1),
    ("lut", 2),
    ("marc", 3),
    ("marz", 3),
    ("kwiet", 4),
    ("kwiec", 4),
    ("maja", 5),
    ("maj", 5),
    ("czerw", 6),
    ("lip", 7),
    ("sierp", 8),
    ("wrze", 9),
    ("pazdziernik", 10),
    ("październik", 10),
    ("listopad", 11),
    ("grud", 12),
]


def extract_period(question: str) -> str | None:
    for pattern, label in PERIOD_PATTERNS:
        if pattern.search(question):
            return label
    match = YEAR_MONTH.search(question)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}"
    match = MONTH_NAME.search(question)
    if match:
        return f"{match.group(1).lower()} {match.group(2)}"
    match = MONTH_ONLY.search(question)
    if match:
        return match.group(1).lower()
    return None


def extract_all_periods(question: str) -> list[str]:
    periods: list[str] = []
    for match in YEAR_MONTH.finditer(question):
        periods.append(f"{match.group(1)}-{int(match.group(2)):02d}")
    for match in MONTH_NAME.finditer(question):
        periods.append(f"{match.group(1).lower()} {match.group(2)}")
    for match in MONTH_ONLY.finditer(question):
        periods.append(match.group(1).lower())
    for pattern, label in PERIOD_PATTERNS:
        if pattern.search(question):
            periods.append(label)

    seen: set[str] = set()
    unique: list[str] = []
    for period in periods:
        if period not in seen:
            seen.add(period)
            unique.append(period)
    return unique


def month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year + (month // 12), (month % 12) + 1, 1) - timedelta(days=1)
    return start, end


def parse_period(period: str | None, *, today: date | None = None) -> tuple[date, date]:
    """Parse a Polish period descriptor into [start, end] inclusive."""
    today = today or date.today()
    p = (period or "").strip().lower().replace("_", " ")
    if not p or p == "all":
        return today - timedelta(days=365), today
    if p in {"this month", "ten miesiac", "ten miesiąc", "biezacy", "bieżący"}:
        return month_bounds(today.year, today.month)
    if p in {"last month", "poprzedni miesiac", "poprzedni miesiąc", "zeszly", "zeszły"}:
        prev = today.replace(day=1) - timedelta(days=1)
        return month_bounds(prev.year, prev.month)
    for n in (3, 6, 12):
        if p in {f"last {n} months", f"ostatnie {n} miesiace", f"ostatnie {n} miesiące"}:
            start = (today.replace(day=1) - pd.DateOffset(months=n - 1)).date()
            return start, today
    if len(p) == 7 and p[4] == "-":
        try:
            year, month = int(p[:4]), int(p[5:])
            return month_bounds(year, month)
        except ValueError:
            pass
    parts = p.split()
    if len(parts) == 1:
        if parts[0] in MONTHS_PL:
            return month_bounds(today.year, MONTHS_PL[parts[0]])
        for stem, parsed_month in MONTH_STEMS_PL:
            if parts[0].startswith(stem):
                return month_bounds(today.year, parsed_month)
    if len(parts) == 2:
        parsed_year: int | None
        try:
            parsed_year = int(parts[1])
        except ValueError:
            parsed_year = None
        if parsed_year is not None:
            if parts[0] in MONTHS_PL:
                return month_bounds(parsed_year, MONTHS_PL[parts[0]])
            for stem, parsed_month in MONTH_STEMS_PL:
                if parts[0].startswith(stem):
                    return month_bounds(parsed_year, parsed_month)
    return today - timedelta(days=365), today
