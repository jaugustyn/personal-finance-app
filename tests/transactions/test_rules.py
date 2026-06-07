"""Tests for transaction type rules separate from expense categories."""
from finance.domain.enums import Category, TransactionDirection, TransactionType
from finance.transactions.rules import (
    detect_transaction_type,
    detect_transfer,
    explain_transaction_type,
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


def test_detects_debt_payment_as_non_category_candidate() -> None:
    tx_type = detect_transaction_type(
        "Alior Bank",
        "Rata kredytu gotówkowego",
        TransactionDirection.DEBIT,
    )
    assert tx_type == TransactionType.DEBT_PAYMENT
    assert not is_category_suggestion_candidate(tx_type)
    decision = explain_transaction_type(
        "Alior Bank",
        "Rata kredytu gotówkowego",
        TransactionDirection.DEBIT,
    )
    assert decision.result == TransactionType.DEBT_PAYMENT.value
    assert decision.rule_id == "tx_type.debt_payment.debit_keywords"
    assert decision.matched == "rata kredytu"
    assert (
        detect_transaction_type(
            "Alior Bank",
            "Przelew rata kredytu gotówkowego",
            TransactionDirection.DEBIT,
            raw_category="transfer",
        )
        == TransactionType.DEBT_PAYMENT
    )


def test_detects_other_income_examples() -> None:
    assert (
        detect_transaction_type(
            "WYŻSZA SZKOŁA EKONOMII I INFORMATYK",
            "Stypendium rektora student",
            TransactionDirection.CREDIT,
        )
        == TransactionType.INCOME
    )
    assert (
        detect_transaction_type(
            "BUD SPÓŁKA Z OGRANICZONĄ ODPOWI",
            "RACH/BUD/2026/03/1",
            TransactionDirection.CREDIT,
        )
        == TransactionType.INCOME
    )


def test_detects_top_up_and_currency_exchange_as_own_transfer() -> None:
    assert (
        detect_transaction_type(
            "Wymiana na USD",
            "Wymiana",
            TransactionDirection.DEBIT,
        )
        == TransactionType.OWN_TRANSFER
    )
    assert (
        detect_transaction_type(
            "Zasilenie o *2874",
            "Zasilenie",
            TransactionDirection.CREDIT,
        )
        == TransactionType.OWN_TRANSFER
    )


def test_detects_phone_blik_and_person_refunds_as_person_transfer() -> None:
    assert (
        detect_transaction_type(
            "KLAUDIA DĄB",
            "Przelew na telefon 48797***131. Przelew na telefon",
            TransactionDirection.CREDIT,
        )
        == TransactionType.PERSON_TRANSFER
    )
    assert (
        detect_transaction_type(
            "PAYMENTWALL INC",
            "BLIK REF 93725335503",
            TransactionDirection.DEBIT,
        )
        == TransactionType.PERSON_TRANSFER
    )
    assert (
        detect_transaction_type(
            "Michał Wiśniewski",
            "Przelew BLIK · Zwrot za zakupy",
            TransactionDirection.CREDIT,
        )
        == TransactionType.PERSON_TRANSFER
    )


def test_store_refunds_remain_refunds() -> None:
    assert (
        detect_transaction_type(
            "Allegro",
            "Zwrot środków Allegro · Płatność online Allegro",
            TransactionDirection.CREDIT,
        )
        == TransactionType.REFUND
    )
    assert (
        detect_transaction_type(
            "Zalando",
            "ZALANDO SE płatność · Zwrot za zamówienie Zalando",
            TransactionDirection.CREDIT,
        )
        == TransactionType.REFUND
    )


def test_merchant_subscription_fee_is_not_bank_fee() -> None:
    assert (
        detect_transaction_type(
            "Orange",
            "Opłata abonament Orange · ORANGE POLSKA faktura",
            TransactionDirection.DEBIT,
        )
        == TransactionType.PURCHASE
    )


def test_rule_category_for_bank_fee_and_savings() -> None:
    assert rule_category_for_type(TransactionType.BANK_FEE) == Category.OTHER
    assert rule_category_for_type(TransactionType.SAVINGS_INVESTMENT) == Category.SAVINGS
    assert rule_category_for_type(TransactionType.PERSON_TRANSFER) is None
    assert rule_category_for_type(TransactionType.DEBT_PAYMENT) is None


def test_ike_investment_rule_does_not_match_ikea() -> None:
    assert (
        detect_transaction_type("IKE", "Wpłata długoterminowa", TransactionDirection.DEBIT)
        == TransactionType.SAVINGS_INVESTMENT
    )
    assert (
        detect_transaction_type("IKEA Kraków", "Zakupy domowe", TransactionDirection.DEBIT)
        == TransactionType.PURCHASE
    )


def test_detects_incoming_person_transfer() -> None:
    assert (
        detect_transaction_type(
            "Anna Nowak", "BLIK na telefon", TransactionDirection.CREDIT
        )
        == TransactionType.PERSON_TRANSFER
    )


def test_currency_exchange_is_own_transfer() -> None:
    assert (
        detect_transaction_type(
            "Revolut", "Exchanged to USD", TransactionDirection.DEBIT
        )
        == TransactionType.OWN_TRANSFER
    )
