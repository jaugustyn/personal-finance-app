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

    PURCHASE = "purchase"
    OWN_TRANSFER = "own_transfer"
    PERSON_TRANSFER = "person_transfer"
    SALARY = "salary"
    INCOME = "income"
    REFUND = "refund"
    CASH_WITHDRAWAL = "cash_withdrawal"
    DEBT_PAYMENT = "debt_payment"
    BANK_FEE = "bank_fee"
    SAVINGS_INVESTMENT = "savings_investment"
    OTHER = "other"


class CategorySource(StrEnum):
    BANK = "bank"
    RULE = "rule"
    MODEL = "model"
    LLM = "llm"
    MANUAL = "manual"


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
