"""Enumerations for the unified transaction schema."""
from enum import StrEnum


class Category(StrEnum):
    """Unified expense categories used as the ML target."""

    FOOD = "food"
    TRANSPORT = "transport"
    SUBSCRIPTIONS = "subscriptions"
    HEALTH = "health"
    ENTERTAINMENT = "entertainment"
    HOUSING = "housing"
    SAVINGS = "savings"
    SHOPPING = "shopping"
    OTHER = "other"


class TransactionType(StrEnum):
    """Semantic transaction type, separate from expense category."""

    EXPENSE = "expense"
    SALARY = "salary"
    INCOME = "income"
    REFUND = "refund"
    OWN_TRANSFER = "own_transfer"
    CASH_WITHDRAWAL = "cash_withdrawal"
    DEBT_PAYMENT = "debt_payment"
    ASSET_ALLOCATION = "asset_allocation"
    OTHER = "other"


class CategorySource(StrEnum):
    BANK = "bank"
    RULE = "rule"
    MODEL = "model"
    LLM = "llm"
    MANUAL = "manual"


class CategoryConfirmationMethod(StrEnum):
    """User action that makes a category eligible as an ML gold label."""

    MANUAL = "manual"
    ACCEPTED_SUGGESTION = "accepted_suggestion"
    PERSONAL_RULE_AUTO = "personal_rule_auto"


class TransactionDirection(StrEnum):
    DEBIT = "debit"   # money out
    CREDIT = "credit"  # money in


class BankSource(StrEnum):
    PKO = "pko"
    PEKAO = "pekao"
    REVOLUT = "revolut"
    MBANK = "mbank"
    ING = "ing"
    UNKNOWN = "unknown"


CATEGORY_VALUES = frozenset(item.value for item in Category)
CATEGORY_SOURCE_VALUES = frozenset(item.value for item in CategorySource)
CATEGORY_CONFIRMATION_METHOD_VALUES = frozenset(
    {
        CategoryConfirmationMethod.MANUAL.value,
        CategoryConfirmationMethod.ACCEPTED_SUGGESTION.value,
    }
)
TRANSACTION_DIRECTION_VALUES = frozenset(item.value for item in TransactionDirection)
TRANSACTION_TYPE_VALUES = frozenset(item.value for item in TransactionType)
BANK_SOURCE_VALUES = frozenset(item.value for item in BankSource)
