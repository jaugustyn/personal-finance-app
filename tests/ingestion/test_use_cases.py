"""Application-level import orchestration tests."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import event

from finance.currencies import add_manual_rate
from finance.domain.dto import ImportSummary, TransactionDTO
from finance.domain.enums import BankSource, TransactionDirection
from finance.domain.models import Import
from finance.ingestion import service as ingestion_service
from finance.ingestion import use_cases
from finance.ingestion.generic import GenericCsvParser
from finance.ingestion.quality import assess_import_quality
from finance.profile.service import create_rule


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
    parse_calls = 0
    original_parse = GenericCsvParser.parse

    def counting_parse(self, stream, *, filename=None):
        nonlocal parse_calls
        parse_calls += 1
        return original_parse(self, stream, filename=filename)

    def fake_ingest_transactions(session, **kwargs):
        captured["parsed_rows"] = len(kwargs["dtos"])
        return ImportSummary(
            import_id=1,
            account_id=1,
            account_name="Test account",
            source=BankSource.UNKNOWN,
            inserted=1,
            duplicates=0,
            total_rows=1,
        )

    monkeypatch.setattr(GenericCsvParser, "parse", counting_parse)
    monkeypatch.setattr(use_cases, "ingest_transactions", fake_ingest_transactions)

    result = use_cases.upload_import(
        db_session,
        filename="generic.csv",
        raw=raw,
        requested_source="generic",
        column_map=None,
        skip_categories=False,
        fx_mode="require_existing",
        account_id=1,
    )

    assert parse_calls == 1
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

    def failing_ingest_transactions(session, **_kwargs):
        row = Import(
            account_id=1,
            source=BankSource.UNKNOWN,
            filename="generic.csv",
            total_rows=1,
        )
        session.add(row)
        session.flush()
        raise RuntimeError("failure after helper record")

    monkeypatch.setattr(use_cases, "ingest_transactions", failing_ingest_transactions)

    with pytest.raises(RuntimeError, match="failure after helper record"):
        use_cases.upload_import(
            db_session,
            filename="generic.csv",
            raw=raw,
            requested_source="generic",
            column_map=None,
            skip_categories=False,
            fx_mode="require_existing",
            account_id=1,
        )

    assert db_session.query(Import).count() == 0


def test_batch_ingestion_loads_rules_and_fx_once(
    db_engine,
    db_session,
    monkeypatch,
) -> None:
    booking_date = date(2026, 4, 10)
    rate_date = date(2026, 4, 9)
    add_manual_rate(
        db_session,
        currency="EUR",
        base_currency="PLN",
        rate_date=rate_date,
        rate=Decimal("4.50"),
    )
    create_rule(
        db_session,
        pattern="sklep",
        category="shopping",
        mode="suggest_only",
    )
    inserted_values: list[dict[str, object]] = []

    class FakeRepository:
        def __init__(self, session) -> None:
            self.next_id = 1

        def create_import(self, **_kwargs):
            return SimpleNamespace(
                id=1,
                account=SimpleNamespace(name="Test account"),
            )

        def insert_transaction_values(self, values):
            inserted_values.append(values)
            transaction_id = self.next_id
            self.next_id += 1
            return transaction_id

        def finalize_import(self, _row, **_kwargs) -> None:
            return None

    monkeypatch.setattr(
        ingestion_service,
        "TransactionImportRepository",
        FakeRepository,
    )
    statements: list[str] = []

    def record_statement(_conn, _cursor, statement, _parameters, _context, _many) -> None:
        statements.append(statement.lower())

    event.listen(db_engine, "before_cursor_execute", record_statement)
    try:
        result = ingestion_service.ingest_transactions(
            db_session,
            source=BankSource.UNKNOWN,
            account_id=1,
            filename="batch.csv",
            dtos=[
                TransactionDTO(
                    booking_date=booking_date,
                    amount=Decimal("-10.00"),
                    currency="EUR",
                    direction=TransactionDirection.DEBIT,
                    merchant="Sklep",
                    title="Zakupy",
                    source=BankSource.UNKNOWN,
                    external_id=f"batch-{index}",
                )
                for index in range(25)
            ],
            fx_mode="require_existing",
        )
    finally:
        event.remove(db_engine, "before_cursor_execute", record_statement)

    selects = [
        statement
        for statement in statements
        if statement.lstrip().startswith("select")
    ]
    assert result.inserted == 25
    assert inserted_values[0]["amount_base"] == Decimal("-45.00")
    assert inserted_values[0]["fx_rate_date"] == rate_date
    assert sum("fx_rates" in statement for statement in selects) == 1
    assert sum("personal_rules" in statement for statement in selects) == 1


def test_quality_report_handles_invalid_currency_without_fx_lookup_error(
    db_session,
) -> None:
    raw = b"Date,Amount,Currency,Description\n2026-04-02,-20.00,US,Shop\n"

    report = assess_import_quality(
        db_session,
        filename="invalid-currency.csv",
        raw=raw,
        parser=GenericCsvParser(),
    )

    assert any(issue.code == "invalid_currency" for issue in report.issues)
