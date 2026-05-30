"""Tests for transfer-detection heuristic in ingestion service."""
from finance.ingestion.service import detect_transfer


def test_detects_polish_own_transfer() -> None:
    assert detect_transfer("", "Przelew własny na konto oszczędnościowe")
    assert detect_transfer("Rachunek własny", "")
    assert detect_transfer("", "PRZELEW WEWNĘTRZNY MIĘDZY RACHUNKAMI")


def test_detects_english_own_transfer() -> None:
    assert detect_transfer("Revolut", "Transfer to my account")
    assert detect_transfer("", "Between accounts")
    assert detect_transfer("", "Transfer to savings")


def test_does_not_flag_normal_purchase() -> None:
    assert not detect_transfer("Carrefour", "Zakupy spożywcze")
    assert not detect_transfer("Netflix", "Subscription payment")
    assert not detect_transfer("Uber", "Trip 12345")


def test_case_insensitive() -> None:
    assert detect_transfer("PRZELEW WŁASNY", "")
    assert detect_transfer("Przelew Własny", "")
