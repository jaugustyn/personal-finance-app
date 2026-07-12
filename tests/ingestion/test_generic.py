"""Unit tests for the generic CSV parser (PL/EN heuristics + column-map)."""
import io

import pytest

from finance.ingestion.base import ParseError
from finance.ingestion.generic import (
    GenericCsvParser,
    auto_detect_columns,
    preview_csv,
)
from finance.ingestion.schema import (
    clean_column_map,
    import_quality_warnings,
    validate_column_map,
)


def test_auto_detect_polish_headers() -> None:
    headers = ["Data księgowania", "Kwota", "Waluta", "Tytułem", "Kategoria"]
    m = auto_detect_columns(headers)
    assert m["date"] == "Data księgowania"
    assert m["amount"] == "Kwota"
    assert m["currency"] == "Waluta"
    assert m["title"] == "Tytułem"
    assert m["category"] == "Kategoria"


def test_auto_detect_english_headers() -> None:
    headers = ["Date", "Amount", "Currency", "Description", "Memo"]
    m = auto_detect_columns(headers)
    assert m["date"] == "Date"
    assert m["amount"] == "Amount"
    assert m["currency"] == "Currency"
    assert m["merchant"] == "Description"
    assert m["title"] == "Memo"


def test_auto_detect_snake_case_headers() -> None:
    headers = ["booking_date", "amount", "currency", "merchant"]
    m = auto_detect_columns(headers)
    assert m["date"] == "booking_date"
    assert m["amount"] == "amount"
    assert m["currency"] == "currency"
    assert m["merchant"] == "merchant"


def test_preview_detects_delimiter_and_sample_rows() -> None:
    raw = (
        b"Date;Amount;Currency;Description\n"
        b"2026-04-01;-50,00;PLN;Carrefour\n"
        b"2026-04-02;3000,00;PLN;Salary\n"
    )
    p = preview_csv(io.BytesIO(raw))
    assert p.delimiter == ";"
    assert p.headers == ["Date", "Amount", "Currency", "Description"]
    assert len(p.sample_rows) == 2
    assert p.detected_mapping["date"] == "Date"


def test_generic_parser_parses_english_csv() -> None:
    raw = (
        b"Date,Amount,Currency,Description,Memo\n"
        b"2026-04-01,-50.00,PLN,Carrefour,Groceries\n"
        b"2026-04-02,3000.00,PLN,Acme Corp,Salary\n"
        b"2026-04-03,-29.99,USD,Spotify,Subscription\n"
    )
    dtos = GenericCsvParser().parse(io.BytesIO(raw))
    assert len(dtos) == 3
    assert dtos[0].direction.value == "debit"
    assert dtos[1].direction.value == "credit"
    assert dtos[2].currency == "USD"


def test_generic_parser_with_explicit_column_map() -> None:
    raw = (
        b"When|How much|Who|Note\n"
        b"01.04.2026|-50,00|Carrefour|Zakupy\n"
    )
    parser = GenericCsvParser({
        "date": "When",
        "amount": "How much",
        "merchant": "Who",
        "title": "Note",
    })
    dtos = parser.parse(io.BytesIO(raw))
    assert len(dtos) == 1
    assert dtos[0].merchant == "Carrefour"
    assert dtos[0].title == "Zakupy"
    assert dtos[0].amount == -50


def test_generic_parser_preserves_explicit_operation_type() -> None:
    raw = (
        b"Date,Amount,Merchant,Operation\n"
        b"2026-04-01,-50.00,Shop,CARD PAYMENT\n"
    )
    parser = GenericCsvParser(
        {
            "date": "Date",
            "amount": "Amount",
            "merchant": "Merchant",
            "transaction_type": "Operation",
        }
    )

    dtos = parser.parse(io.BytesIO(raw))

    assert dtos[0].raw_transaction_type == "CARD PAYMENT"


def test_generic_parser_maps_source_categories() -> None:
    raw = (
        b"Date,Amount,Currency,Description,Category\n"
        b"2026-04-01,-50.00,PLN,Allegro,shopping\n"
        b"2026-04-02,-40.00,PLN,Lidl,groceries\n"
        b"2026-04-03,3000.00,PLN,Client,income\n"
        b"2026-04-04,20.00,PLN,Shop,refund\n"
        b"2026-04-05,-100.00,PLN,ATM,cash\n"
        b"2026-04-06,-80.00,PLN,Nike,Zakupy\n"
        b"2026-04-07,-500.00,PLN,Booking.com,Travel\n"
        b"2026-04-08,-450.00,PLN,Hotel,Rezerwacja noclegu\n"
        b"2026-04-09,-300.00,PLN,Auto Serwis Kowalski,Serwis samochodowy\n"
    )

    dtos = GenericCsvParser().parse(io.BytesIO(raw))

    assert [dto.category.value if dto.category else None for dto in dtos] == [
        "shopping",
        "food",
        None,
        None,
        None,
        "shopping",
        "transport",
        "transport",
        "transport",
    ]


def test_generic_parser_handles_european_decimals() -> None:
    raw = b"Data,Kwota,Merchant\n2026-04-01,\"1 234,56\",Shop\n"
    dtos = GenericCsvParser().parse(io.BytesIO(raw))
    assert len(dtos) == 1
    assert float(dtos[0].amount) == 1234.56


def test_generic_parser_skips_unparseable_rows() -> None:
    raw = (
        b"Date,Amount,Merchant\n"
        b"not-a-date,-50.00,Shop\n"           # bad date → skipped
        b"2026-04-01,not-a-number,Shop\n"     # bad amount → skipped
        b"2026-04-02,-50.00,Shop\n"           # ok
    )
    dtos = GenericCsvParser().parse(io.BytesIO(raw))
    assert len(dtos) == 1


def test_generic_parser_raises_when_required_columns_missing() -> None:
    raw = b"Foo,Bar\n1,2\n"
    with pytest.raises(ParseError):
        GenericCsvParser().parse(io.BytesIO(raw))


def test_column_map_validation_and_quality_warnings() -> None:
    mapping = clean_column_map({
        "date": "Date",
        "amount": "Amount",
        "unknown": "Ignored",
        "merchant": "Merchant",
        "title": None,
    })

    assert mapping == {"date": "Date", "amount": "Amount", "merchant": "Merchant"}
    assert validate_column_map(mapping, headers=["Date", "Amount", "Merchant"]) == []
    assert validate_column_map({"date": "Missing", "amount": "Amount"}, headers=["Amount"])
    warnings = import_quality_warnings(mapping)
    assert any("Currency is optional" in warning for warning in warnings)


def test_generic_parser_decodes_cp1250() -> None:
    raw = "Data,Kwota,Opis\n2026-04-01,-50,Żółć\n".encode("cp1250")
    dtos = GenericCsvParser().parse(io.BytesIO(raw))
    assert len(dtos) == 1
    assert "Żółć" in dtos[0].merchant or "Żółć" in dtos[0].title
