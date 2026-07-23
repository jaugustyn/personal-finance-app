"""Application-level import orchestration tests."""
from __future__ import annotations

import pytest

from finance.domain.dto import ImportSummary
from finance.domain.enums import BankSource
from finance.domain.models import Import
from finance.ingestion import use_cases


def test_generic_upload_reports_rows_skipped_for_invalid_date_and_amount(
    db_session,
    monkeypatch,
) -> None:
    raw = (
        b"Date,Amount,Currency,Description\n"
        b"not-a-date,-50.00,PLN,Shop\n"
        b"2026-04-01,not-a-number,PLN,Shop\n"
        b"2026-04-02,-20.00,PLN,Shop\n"
    )
    captured: dict[str, object] = {}

    def fake_ingest_file(session, **kwargs):
        parser = kwargs["parser"]
        captured["parsed_rows"] = len(parser.parse(kwargs["stream"]))
        return ImportSummary(
            import_id=1,
            source=BankSource.UNKNOWN,
            inserted=1,
            duplicates=0,
            total_rows=1,
        )

    monkeypatch.setattr(use_cases, "ingest_file", fake_ingest_file)

    result = use_cases.upload_import(
        db_session,
        filename="generic.csv",
        raw=raw,
        requested_source="generic",
        column_map=None,
        skip_categories=False,
        fx_mode="require_existing",
    )

    assert captured["parsed_rows"] == 1
    assert result.skipped_rows == 2
    assert result.quality_report.total_rows == 3
    assert result.quality_report.valid_rows == 1
    issues = {issue.code: issue for issue in result.quality_report.issues}
    assert issues["invalid_date"].sample_rows == [2]
    assert issues["invalid_amount"].sample_rows == [3]


def test_upload_rolls_back_records_flushed_by_the_ingestion_component(
    db_session,
    monkeypatch,
) -> None:
    raw = b"Date,Amount,Currency,Description\n2026-04-02,-20.00,PLN,Shop\n"

    def failing_ingest_file(session, **_kwargs):
        row = Import(
            source=BankSource.UNKNOWN,
            filename="generic.csv",
            total_rows=1,
        )
        session.add(row)
        session.flush()
        raise RuntimeError("failure after helper record")

    monkeypatch.setattr(use_cases, "ingest_file", failing_ingest_file)

    with pytest.raises(RuntimeError, match="failure after helper record"):
        use_cases.upload_import(
            db_session,
            filename="generic.csv",
            raw=raw,
            requested_source="generic",
            column_map=None,
            skip_categories=False,
            fx_mode="require_existing",
        )

    assert db_session.query(Import).count() == 0
