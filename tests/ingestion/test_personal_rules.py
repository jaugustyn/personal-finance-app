"""Personal rules applied during import value construction."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from finance.domain.dto import TransactionDTO
from finance.domain.enums import BankSource, TransactionDirection
from finance.ingestion.service import transaction_values_for_dto
from finance.profile.service import create_rule


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


def test_personal_rule_suggests_category_without_ground_truth(db_session) -> None:
    create_rule(db_session, pattern="lidl", category="food", mode="suggest_only")

    values = transaction_values_for_dto(
        db_session,
        _dto(),
        import_id=1,
        dedup_hash="hash",
    )

    assert values["category"] is None
    assert values["category_predicted"] == "food"
    assert values["category_predicted_source"] == "rule"
    assert values["category_confidence"] == 0.95


def test_personal_rule_can_auto_apply_transfer_type(db_session) -> None:
    create_rule(
        db_session,
        pattern="broker",
        transaction_type="own_transfer",
        category="savings",
        mode="auto_apply",
    )

    values = transaction_values_for_dto(
        db_session,
        _dto(merchant="My Broker", title="Top up"),
        import_id=1,
        dedup_hash="hash",
    )

    assert values["transaction_type"] == "own_transfer"
    assert values["is_transfer"] is True
    assert values["category"] is None
    assert values["category_source"] is None


def test_personal_suggest_only_type_precedes_bank_mapping(db_session) -> None:
    create_rule(
        db_session,
        pattern="lidl",
        transaction_type="asset_allocation",
        mode="suggest_only",
    )

    values = transaction_values_for_dto(
        db_session,
        _dto(raw_transaction_type="PŁATNOŚĆ BLIK"),
        import_id=1,
        dedup_hash="bank-before-suggestion",
    )

    assert values["transaction_type"] is None
    assert values["transaction_type_source"] is None
    assert values["transaction_type_confirmation_method"] is None
    assert values["transaction_type_predicted"] == "asset_allocation"
    assert values["transaction_type_predicted_source"] == "rule"


def test_bank_mapping_stays_a_suggestion(db_session) -> None:
    values = transaction_values_for_dto(
        db_session,
        _dto(raw_transaction_type="PŁATNOŚĆ BLIK"),
        import_id=1,
        dedup_hash="bank-type-suggestion",
    )

    assert values["transaction_type"] is None
    assert values["transaction_type_source"] is None
    assert values["transaction_type_predicted"] == "expense"
    assert values["transaction_type_predicted_source"] == "bank"
    assert values["transaction_type_confidence"] is None


def test_personal_suggest_only_type_stays_a_suggestion(db_session) -> None:
    create_rule(
        db_session,
        pattern="cel oszczednosciowy",
        pattern_target="title",
        transaction_type="asset_allocation",
        mode="suggest_only",
    )

    values = transaction_values_for_dto(
        db_session,
        _dto(merchant="Bank", title="Cel oszczednosciowy"),
        import_id=1,
        dedup_hash="personal-type-suggestion",
    )

    assert values["transaction_type"] is None
    assert values["transaction_type_predicted"] == "asset_allocation"
    assert values["transaction_type_predicted_source"] == "rule"
    assert values["transaction_type_confidence"] is None


def test_rule_category_is_not_applied_to_credit_income(db_session) -> None:
    values = transaction_values_for_dto(
        db_session,
        _dto(
            amount=Decimal("15.00"),
            direction=TransactionDirection.CREDIT,
            merchant="Bank",
            title="Odsetki",
        ),
        import_id=1,
        dedup_hash="hash",
    )

    assert values["transaction_type"] is None
    assert values["transaction_type_predicted"] == "income"
    assert values["category"] is None
    assert values["category_source"] is None


def test_skip_categories_overrides_bank_category(db_session) -> None:
    from finance.domain.enums import Category
    values = transaction_values_for_dto(
        db_session,
        _dto(category=Category.FOOD),
        import_id=1,
        dedup_hash="hash",
        skip_categories=True,
    )
    assert values["category"] is None
    assert values["category_source"] is None


def test_skip_categories_default_does_not_override(db_session) -> None:
    from finance.domain.enums import Category
    values = transaction_values_for_dto(
        db_session,
        _dto(category=Category.FOOD),
        import_id=1,
        dedup_hash="hash",
        skip_categories=False,
    )
    assert values["category"] is None
    assert values["category_predicted"] == "food"
    assert values["category_confidence"] is None
    assert values["category_predicted_source"] == "bank"
