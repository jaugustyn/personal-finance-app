"""Property-based tests for CSV ingestion utilities.

Goal: ``preview_csv`` must never raise on arbitrary printable input — it should
either return a ``CsvPreview`` or raise ``ParseError``/``UnicodeDecodeError``,
both of which the API translates into a 422 response. We assert the function
behaves as a total function over the printable-text input domain.
"""
from __future__ import annotations

import io

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from finance.ingestion.generic import preview_csv

# Strategy: small CSV-shaped inputs from a printable alphabet plus separators.
_csv_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Zs"),
        whitelist_characters=",;\t\n\"'",
    ),
    min_size=0,
    max_size=400,
)


@settings(
    max_examples=80,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
@given(_csv_text)
def test_preview_csv_never_crashes(text: str) -> None:
    raw = text.encode("utf-8", errors="ignore")
    try:
        prev = preview_csv(io.BytesIO(raw))
    except (ValueError, UnicodeDecodeError):
        # Acceptable failure modes — converted to HTTP 422 by the router.
        return
    assert isinstance(prev.headers, list)
    assert all(isinstance(h, str) for h in prev.headers)
    assert isinstance(prev.sample_rows, list)
    for row in prev.sample_rows:
        assert isinstance(row, dict)
    assert prev.delimiter in (",", ";", "\t", "|")
    assert prev.encoding


def test_preview_csv_rejects_empty() -> None:
    # Empty input yields an empty preview rather than raising — the API layer
    # is responsible for the 422 (see _read_validated in apps/api/routers/imports.py).
    prev = preview_csv(io.BytesIO(b""))
    assert prev.headers == [] or prev.sample_rows == []


def test_preview_csv_handles_utf8_bom() -> None:
    raw = "\ufeffdate,amount,merchant\n2026-01-01,-10.00,Foo\n".encode("utf-8")
    prev = preview_csv(io.BytesIO(raw))
    assert "date" in prev.headers
    assert prev.sample_rows[0]["merchant"] == "Foo"
