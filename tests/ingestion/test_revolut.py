"""Tests for the Polish-locale Revolut CSV parser."""
import io
from datetime import date
from decimal import Decimal

from finance.domain.enums import BankSource, TransactionDirection
from finance.ingestion.revolut import RevolutParser

SAMPLE = (
    "Rodzaj;Produkt;Data rozpoczęcia;Data zrealizowania;Opis;Kwota;"
    "Opłata;Waluta;State;Saldo\n"
    "Wymiana;Bieżące;06.08.2025 12:24;06.08.2025 12:24;Wymiana na USD;"
    "13.48;0.00;USD;ZAKOŃCZONO;13.48\n"
    "Płatność kartą;Bieżące;06.08.2025 12:25;06.08.2025 19:09;GitHub;"
    "-10.00;0.00;USD;ZAKOŃCZONO;3.48\n"
    "Płatność kartą;Bieżące;01.05.2026 10:00;;Pending Cafe;"
    "-5.00;0.00;PLN;OCZEKUJE;0.00\n"
).encode()

SAMPLE_COMMA_ISO = (
    "Rodzaj,Produkt,Data rozpoczęcia,Data zrealizowania,Opis,Kwota,"
    "Opłata,Waluta,State,Saldo\n"
    "Zasilenie,Bieżące,2025-08-06 12:21:18,2025-08-06 12:21:43,"
    "Zasilenie o *2874,100.00,0.00,PLN,ZAKOŃCZONO,100.00\n"
    "Płatność kartą,Bieżące,2025-11-17 21:50:15,2025-11-19 03:40:01,"
    "Nike,-119.99,0.00,PLN,ZAKOŃCZONO,132.77\n"
).encode()


def test_revolut_parser_polish() -> None:
    parser = RevolutParser()
    out = parser.parse(io.BytesIO(SAMPLE), filename="revolut.csv")

    assert len(out) == 2  # pending row dropped

    exchange, payment = out
    assert exchange.source is BankSource.REVOLUT
    assert exchange.booking_date == date(2025, 8, 6)
    assert exchange.amount == Decimal("13.48")
    assert exchange.direction is TransactionDirection.CREDIT
    assert exchange.currency == "USD"
    assert exchange.title == "Wymiana"
    assert exchange.raw_transaction_type == "Wymiana"
    assert exchange.category is None  # exchange rows must not be auto-labelled

    assert payment.amount == Decimal("-10.00")
    assert payment.direction is TransactionDirection.DEBIT
    assert payment.raw_transaction_type == "Płatność kartą"
    assert "GitHub" in payment.merchant


def test_revolut_parser_comma_iso_dates() -> None:
    parser = RevolutParser()
    out = parser.parse(io.BytesIO(SAMPLE_COMMA_ISO), filename="revolut.csv")

    assert len(out) == 2
    assert out[0].booking_date == date(2025, 8, 6)
    assert out[0].amount == Decimal("100.00")
    assert out[1].booking_date == date(2025, 11, 19)
    assert out[1].amount == Decimal("-119.99")
