"""Tests for the Pekao SA CSV parser using a small cp1250 fixture."""
import io
from datetime import date
from decimal import Decimal

from finance.domain.enums import BankSource, Category, TransactionDirection
from finance.ingestion.pekao import PekaoParser

HEADER = (
    "Data księgowania;Data waluty;Nadawca / Odbiorca;Adres nadawcy / odbiorcy;"
    "Rachunek źródłowy;Rachunek docelowy;Tytułem;Kwota operacji;Waluta;"
    "Numer referencyjny;Typ operacji;Kategoria"
)
ROWS = [
    "30.04.2026;30.04.2026;Orange Flex; flex.orange.pl;'91...;;BLIK REF 1;"
    "-350;PLN;'C99261201;PŁATNOŚĆ BLIK;Internet, TV, telefon",
    "18.04.2026;18.04.2026;CARREFOUR KRAKOW;;'91...;;*****;-31,41;PLN;"
    "'C99261082;TRANSAKCJA KARTĄ PŁATNICZĄ;Artykuły spożywcze",
    "03.04.2026;03.04.2026;PRACODAWCA;;'761910...;'91...;Wynagrodzenie;"
    "6290;PLN;'0DC0000;PRZELEW KRAJOWY;Wynagrodzenie",
    "01.04.2026;01.04.2026;NIEZNANY;;'91...;;BLIK;-50;PLN;'C9;PŁATNOŚĆ BLIK;"
    "Bez kategorii",
]
SAMPLE = ("\n".join([HEADER, *ROWS]) + "\n").encode("cp1250")


def test_pekao_parser_basic() -> None:
    parser = PekaoParser()
    out = parser.parse(io.BytesIO(SAMPLE), filename="pekao.csv")
    assert len(out) == 4

    orange, carrefour, salary, unknown = out

    assert orange.source is BankSource.PEKAO
    assert orange.booking_date == date(2026, 4, 30)
    assert orange.amount == Decimal("-350")
    assert orange.direction is TransactionDirection.DEBIT
    assert orange.raw_category == "Internet, TV, telefon"
    assert orange.category is Category.SUBSCRIPTIONS

    # Comma decimals, mapped to FOOD.
    assert carrefour.amount == Decimal("-31.41")
    assert carrefour.category is Category.FOOD

    # Wynagrodzenie is intentionally unmapped (None) — it's income, not an expense.
    assert salary.direction is TransactionDirection.CREDIT
    assert salary.raw_category == "Wynagrodzenie"
    assert salary.category is None

    # "Bez kategorii" is left unmapped so it doesn't pollute training.
    assert unknown.category is None


def test_pekao_parser_does_not_require_operation_type() -> None:
    header = (
        "Data księgowania;Data waluty;Nadawca / Odbiorca;Adres nadawcy / odbiorcy;"
        "Rachunek źródłowy;Rachunek docelowy;Tytułem;Kwota operacji;Waluta;"
        "Numer referencyjny;Kategoria"
    )
    row = (
        "01.04.2026;01.04.2026;CARREFOUR;;'91...;;Zakupy;-31,41;PLN;"
        "'C99261082;Artykuły spożywcze"
    )
    sample = f"{header}\n{row}\n".encode("cp1250")

    out = PekaoParser().parse(io.BytesIO(sample), filename="pekao.csv")

    assert len(out) == 1
    assert out[0].merchant == "CARREFOUR"
    assert out[0].category is Category.FOOD


def test_pekao_parser_accepts_utf8_bom_exports() -> None:
    header = (
        "Data księgowania;Data waluty;Nadawca / Odbiorca;Adres nadawcy / odbiorcy;"
        "Rachunek źródłowy;Rachunek docelowy;Tytułem;Kwota operacji;Waluta;"
        "Numer referencyjny;Typ operacji;Kategoria"
    )
    row = (
        "01.04.2026;01.04.2026;CARREFOUR;;'91...;;Zakupy;-31,41;PLN;"
        "'C99261082;TRANSAKCJA KARTĄ PŁATNICZĄ;Artykuły spożywcze"
    )
    sample = f"{header}\n{row}\n".encode("utf-8-sig")

    out = PekaoParser().parse(io.BytesIO(sample), filename="pekao-utf8.csv")

    assert len(out) == 1
    assert out[0].merchant == "CARREFOUR"
    assert out[0].title == "Zakupy"
    assert out[0].category is Category.FOOD
