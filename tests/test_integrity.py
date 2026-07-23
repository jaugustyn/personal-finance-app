"""Privacy-safe data integrity diagnostics."""
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from finance.categories import seed_system_categories
from finance.domain.models import CategoryDef, Transaction, UserProfile
from finance.integrity import check_data_integrity


@pytest.fixture(autouse=True)
def _system_category_catalog(db_session: Session) -> None:
    seed_system_categories(db_session)
    db_session.commit()


def test_integrity_reports_ids_without_private_transaction_content(
    db_session: Session,
) -> None:
    invalid_fx = Transaction(
        booking_date=date(2026, 1, 1),
        amount=Decimal("-10.00"),
        currency="USD",
        direction="debit",
        merchant="PRIVATE MERCHANT",
        title="PRIVATE TITLE",
        source="unknown",
        dedup_hash="integrity-invalid-fx",
        is_transfer=False,
    )
    incomplete_category = Transaction(
        booking_date=date(2026, 1, 2),
        amount=Decimal("-20.00"),
        currency="PLN",
        direction="debit",
        merchant="Category",
        title="",
        category="food",
        category_source="manual",
        category_confirmation_method="manual",
        category_confirmed_at=None,
        source="unknown",
        dedup_hash="integrity-category",
        is_transfer=False,
    )
    inconsistent_fx = Transaction(
        booking_date=date(2026, 1, 2),
        amount=Decimal("-10.00"),
        currency="EUR",
        amount_base=Decimal("-99.00"),
        base_currency="PLN",
        fx_rate=Decimal("4.00"),
        direction="debit",
        merchant="FX",
        title="",
        source="unknown",
        dedup_hash="integrity-inconsistent-fx",
        is_transfer=False,
    )
    incomplete_type = Transaction(
        booking_date=date(2026, 1, 2),
        amount=Decimal("-20.00"),
        currency="PLN",
        direction="debit",
        merchant="Type",
        title="",
        transaction_type="expense",
        transaction_type_source="manual",
        transaction_type_confirmation_method="manual",
        transaction_type_confirmed_at=None,
        source="unknown",
        dedup_hash="integrity-type",
        is_transfer=False,
    )
    transfer_mismatch = Transaction(
        booking_date=date(2026, 1, 3),
        amount=Decimal("-30.00"),
        currency="PLN",
        direction="debit",
        merchant="Transfer",
        title="",
        transaction_type="own_transfer",
        transaction_type_source="manual",
        transaction_type_confirmation_method="manual",
        transaction_type_confirmed_at=datetime.now(UTC),
        source="unknown",
        dedup_hash="integrity-transfer",
        is_transfer=False,
    )
    db_session.add_all(
        [
            invalid_fx,
            inconsistent_fx,
            incomplete_category,
            incomplete_type,
            transfer_mismatch,
        ]
    )
    db_session.add(UserProfile(id=1, base_currency="EUR"))
    db_session.commit()

    issues = check_data_integrity(db_session)
    payload = {issue.code: issue for issue in issues}

    assert invalid_fx.id in payload["invalid_or_missing_fx_conversion"].sample_ids
    assert inconsistent_fx.id in payload[
        "invalid_or_missing_fx_conversion"
    ].sample_ids
    assert incomplete_category.id in payload[
        "incomplete_confirmed_category_provenance"
    ].sample_ids
    assert incomplete_type.id in payload[
        "incomplete_confirmed_transaction_type_provenance"
    ].sample_ids
    assert transfer_mismatch.id in payload["transfer_marker_mismatch"].sample_ids
    assert payload["profile_base_currency_not_pln"].sample_ids == (1,)
    assert "PRIVATE MERCHANT" not in repr(issues)
    assert "PRIVATE TITLE" not in repr(issues)


def test_integrity_accepts_consistent_pln_transaction(db_session: Session) -> None:
    db_session.add(
        Transaction(
            booking_date=date(2026, 1, 1),
            amount=Decimal("-10.00"),
            currency="PLN",
            direction="debit",
            merchant="Local",
            title="",
            source="unknown",
            dedup_hash="integrity-ok",
            is_transfer=False,
        )
    )
    db_session.commit()

    assert check_data_integrity(db_session) == []


def test_integrity_reports_missing_system_categories_without_repairing_them(
    db_session: Session,
) -> None:
    food = db_session.scalar(select(CategoryDef).where(CategoryDef.name == "food"))
    assert food is not None
    db_session.delete(food)
    db_session.commit()

    issues = {issue.code: issue for issue in check_data_integrity(db_session)}

    assert issues["missing_system_categories"].count == 1
    assert db_session.scalar(
        select(CategoryDef).where(CategoryDef.name == "food")
    ) is None
