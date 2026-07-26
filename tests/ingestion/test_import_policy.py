"""Pure import policy tests without database access."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from finance.currencies import ConversionResult
from finance.domain.dto import TransactionDTO
from finance.domain.enums import BankSource, Category, TransactionDirection
from finance.ingestion.policy import TransactionImportPolicy, build_transaction_values
from finance.profile.service import RuleEffect


def _dto(**overrides) -> TransactionDTO:
    base = {
        "booking_date": date(2026, 4, 10),
        "amount": Decimal("-42.00"),
        "currency": "PLN",
        "direction": TransactionDirection.DEBIT,
        "merchant": "Lidl",
        "title": "Zakupy",
        "source": BankSource.PEKAO,
    }
    base.update(overrides)
    return TransactionDTO(**base)


def _conversion(**overrides) -> ConversionResult:
    base = {
        "amount_base": Decimal("-42.00"),
        "base_currency": "PLN",
        "fx_rate": Decimal("1.000000"),
        "fx_rate_date": date(2026, 4, 10),
        "fx_rate_source": "base",
    }
    base.update(overrides)
    return ConversionResult(**base)


def _rule_effect(**overrides) -> RuleEffect:
    base = {
        "rule": None,
        "category": None,
        "transaction_type": None,
        "is_transfer": None,
        "mode": "suggest_only",
        "confidence": 0.95,
    }
    base.update(overrides)
    return RuleEffect(**base)


def test_policy_suggests_personal_category_without_database() -> None:
    values = build_transaction_values(
        _dto(),
        converted=_conversion(),
        personal=_rule_effect(category="food"),
        account_id=1,
        import_id=1,
        dedup_hash="hash",
    )

    assert values["category"] is None
    assert values["category_predicted"] == "food"
    assert values["category_predicted_source"] == "rule"
    assert values["category_confidence"] == 0.95


def test_policy_auto_transfer_blocks_expense_category() -> None:
    values = build_transaction_values(
        _dto(merchant="My Broker", title="Top up"),
        converted=_conversion(),
        personal=_rule_effect(
            transaction_type="own_transfer",
            is_transfer=True,
            category="savings",
            mode="auto_apply",
        ),
        account_id=1,
        import_id=1,
        dedup_hash="hash",
    )

    assert values["transaction_type"] == "own_transfer"
    assert values["is_transfer"] is True
    assert values["category"] is None
    assert values["category_source"] is None


def test_policy_skip_categories_overrides_bank_category() -> None:
    policy = TransactionImportPolicy(skip_categories=True)

    values = policy.build_transaction_values(
        _dto(category=Category.FOOD),
        converted=_conversion(),
        personal=None,
        account_id=1,
        import_id=1,
        dedup_hash="hash",
    )

    assert values["category"] is None
    assert values["category_source"] is None


def test_policy_preserves_fx_values_from_conversion_input() -> None:
    converted = _conversion(
        amount_base=Decimal("-9.99"),
        base_currency="EUR",
        fx_rate=Decimal("0.237857"),
        fx_rate_source="manual",
    )

    values = build_transaction_values(
        _dto(currency="PLN"),
        converted=converted,
        personal=None,
        account_id=1,
        import_id=7,
        dedup_hash="hash-7",
    )

    assert values["amount_base"] == Decimal("-9.99")
    assert values["base_currency"] == "EUR"
    assert values["fx_rate"] == Decimal("0.237857")
    assert values["fx_rate_source"] == "manual"
    assert values["import_id"] == 7
    assert values["dedup_hash"] == "hash-7"


def test_policy_preserves_unconverted_foreign_transaction_without_fake_pln() -> None:
    values = build_transaction_values(
        _dto(currency="USD", amount=Decimal("-10.00")),
        converted=None,
        personal=None,
        account_id=1,
        import_id=8,
        dedup_hash="hash-unconverted",
    )

    assert values["amount"] == Decimal("-10.00")
    assert values["currency"] == "USD"
    assert values["amount_base"] is None
    assert values["base_currency"] is None
    assert values["fx_rate"] is None
