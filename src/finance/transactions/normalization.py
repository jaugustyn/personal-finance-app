"""Shared text normalization for merchants, rules and ML features."""
from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_POLISH_TRANSLATION = str.maketrans("łŁ", "lL")


def normalize_text(value: str | None) -> str:
    text = (value or "").translate(_POLISH_TRANSLATION)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    return _NON_ALNUM.sub(" ", text).strip()


def normalize_merchant(value: str | None) -> str:
    return normalize_text(value)
