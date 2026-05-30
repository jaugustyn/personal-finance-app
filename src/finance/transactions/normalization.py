"""Shared text normalization for merchants, rules and ML features."""
from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_text(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    return _NON_ALNUM.sub(" ", text).strip()


def normalize_merchant(value: str | None) -> str:
    return normalize_text(value)

