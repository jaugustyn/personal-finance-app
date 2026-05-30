"""Rule-based transaction metadata classification.

These rules intentionally classify *transaction type* separately from expense
category. They are conservative: a doubtful card/payment row stays ``purchase``
so the ML category suggester can handle it.
"""
from __future__ import annotations

import re

from finance.domain.enums import Category, TransactionDirection, TransactionType

_OWN_TRANSFER_KEYWORDS: tuple[str, ...] = (
    "przelew własny",
    "przelew wlasny",
    "rachunek własny",
    "rachunek wlasny",
    "przelew wewnętrzny",
    "przelew wewnetrzny",
    "przelew między rachunkami",
    "przelew miedzy rachunkami",
    "między rachunkami",
    "miedzy rachunkami",
    "to my account",
    "from my account",
    "between accounts",
    "account top-up",
    "transfer to savings",
    "transfer from savings",
    "top up by bank card",
)
_PERSON_TRANSFER_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bprzelew\b", re.I),
    re.compile(r"\bblik(?:\s+przelew|\s+na\s+telefon|\s+p2p)?\b", re.I),
    re.compile(r"\btransfer\b", re.I),
    re.compile(r"\bwire\b", re.I),
)
_SALARY_KEYWORDS = ("wynagrodzenie", "salary", "payroll", "pensja")
_REFUND_KEYWORDS = ("zwrot", "refund", "cashback", "reversal")
_CASH_KEYWORDS = ("bankomat", "atm", "wypłata gotówki", "wyplata gotowki", "cash withdrawal")
_BANK_FEE_KEYWORDS = ("opłata", "oplata", "prowizja", "bank fee", "fee", "commission")
_SAVINGS_KEYWORDS = (
    "oszczędności",
    "oszczednosci",
    "lokata",
    "inwest",
    "maklerski",
    "broker",
    "xtb",
    "trading",
)
_SAVINGS_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bike\b", re.I),
    re.compile(r"\bikze\b", re.I),
)


def _text(merchant: str | None, title: str | None, raw_category: str | None = None) -> str:
    return f"{merchant or ''} {title or ''} {raw_category or ''}".lower()


def detect_transaction_type(
    merchant: str | None,
    title: str | None,
    direction: str | TransactionDirection,
    *,
    raw_category: str | None = None,
) -> TransactionType:
    haystack = _text(merchant, title, raw_category)
    direction_value = str(direction)

    if any(keyword in haystack for keyword in _OWN_TRANSFER_KEYWORDS):
        return TransactionType.OWN_TRANSFER
    if direction_value == TransactionDirection.CREDIT and any(
        keyword in haystack for keyword in _SALARY_KEYWORDS
    ):
        return TransactionType.SALARY
    if any(keyword in haystack for keyword in _REFUND_KEYWORDS):
        return TransactionType.REFUND
    if direction_value == TransactionDirection.DEBIT and any(
        keyword in haystack for keyword in _CASH_KEYWORDS
    ):
        return TransactionType.CASH_WITHDRAWAL
    if any(keyword in haystack for keyword in _BANK_FEE_KEYWORDS):
        return TransactionType.BANK_FEE
    if any(keyword in haystack for keyword in _SAVINGS_KEYWORDS) or any(
        pattern.search(haystack) for pattern in _SAVINGS_PATTERNS
    ):
        return TransactionType.SAVINGS_INVESTMENT
    if direction_value == TransactionDirection.DEBIT and any(
        pattern.search(haystack) for pattern in _PERSON_TRANSFER_PATTERNS
    ):
        return TransactionType.PERSON_TRANSFER
    if direction_value == TransactionDirection.DEBIT:
        return TransactionType.PURCHASE
    return TransactionType.OTHER


def detect_transfer(merchant: str | None, title: str | None) -> bool:
    return detect_transaction_type(
        merchant,
        title,
        TransactionDirection.DEBIT,
    ) == TransactionType.OWN_TRANSFER


def rule_category_for_type(transaction_type: TransactionType) -> Category | None:
    if transaction_type == TransactionType.BANK_FEE:
        return Category.OTHER
    if transaction_type == TransactionType.SAVINGS_INVESTMENT:
        return Category.SAVINGS
    return None


def is_category_suggestion_candidate(transaction_type: str | TransactionType | None) -> bool:
    if transaction_type is None:
        return True
    value = str(transaction_type)
    return value in {
        TransactionType.PURCHASE.value,
        TransactionType.BANK_FEE.value,
        TransactionType.SAVINGS_INVESTMENT.value,
        TransactionType.OTHER.value,
    }
