"""Tests for transaction type rules separate from expense categories."""
from finance.domain.enums import Category, TransactionDirection, TransactionType
from finance.transactions.rules import (
    detect_transaction_type,
    detect_transfer,
    is_category_suggestion_candidate,
    rule_category_for_type,
)


def test_detects_own_transfer() -> None:
    tx_type = detect_transaction_type(
        "Rachunek własny",
        "Przelew między rachunkami",
        TransactionDirection.DEBIT,
    )
    assert tx_type == TransactionType.OWN_TRANSFER
    assert detect_transfer("Rachunek własny", "")


def test_detects_person_transfer() -> None:
    tx_type = detect_transaction_type(
        "Jan Kowalski",
        "Przelew za bilety",
        TransactionDirection.DEBIT,
    )
    assert tx_type == TransactionType.PERSON_TRANSFER
    assert not is_category_suggestion_candidate(tx_type)


def test_detects_salary_refund_and_cash() -> None:
    assert (
        detect_transaction_type("ACME", "Wynagrodzenie maj", TransactionDirection.CREDIT)
        == TransactionType.SALARY
    )
    assert (
        detect_transaction_type("Shop", "Zwrot płatności", TransactionDirection.CREDIT)
        == TransactionType.REFUND
    )
    assert (
        detect_transaction_type("ATM", "Wypłata gotówki", TransactionDirection.DEBIT)
        == TransactionType.CASH_WITHDRAWAL
    )


def test_rule_category_for_bank_fee_and_savings() -> None:
    assert rule_category_for_type(TransactionType.BANK_FEE) == Category.OTHER
    assert rule_category_for_type(TransactionType.SAVINGS_INVESTMENT) == Category.SAVINGS
    assert rule_category_for_type(TransactionType.PERSON_TRANSFER) is None


def test_ike_investment_rule_does_not_match_ikea() -> None:
    assert (
        detect_transaction_type("IKE", "Wpłata długoterminowa", TransactionDirection.DEBIT)
        == TransactionType.SAVINGS_INVESTMENT
    )
    assert (
        detect_transaction_type("IKEA Kraków", "Zakupy domowe", TransactionDirection.DEBIT)
        == TransactionType.PURCHASE
    )
