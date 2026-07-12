"""Tests for the Review Center data-quality aggregations."""
from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from finance.domain.enums import Category, TransactionDirection, TransactionType
from finance.domain.models import PersonalRule, Transaction
from finance.transactions import review


def _tx(**kwargs) -> Transaction:
    defaults = dict(
        booking_date=date(2026, 1, 1),
        amount=Decimal("20.00"),
        currency="PLN",
        direction=TransactionDirection.DEBIT.value,
        merchant="",
        title="",
        source="pekao",
        dedup_hash=f"h{_tx.counter}",
        transaction_type=TransactionType.EXPENSE.value,
        is_transfer=False,
    )
    _tx.counter += 1
    defaults.update(kwargs)
    if defaults.get("category") is not None:
        defaults.setdefault("category_confirmation_method", "manual")
        defaults.setdefault("category_confirmed_at", datetime.now(UTC))
    return Transaction(**defaults)


_tx.counter = 0


def test_review_counts_buckets(db_session: Session) -> None:
    db_session.add_all(
        [
            # categorized (confirmed)
            _tx(merchant="Biedronka", category=Category.FOOD.value),
            # no suggestion
            _tx(merchant="Nieznany 1"),
            # low confidence suggestion
            _tx(
                merchant="Nieznany 2",
                category_predicted=Category.FOOD.value,
                category_confidence=0.40,
            ),
            # ready to accept
            _tx(
                merchant="Nieznany 3",
                category_predicted=Category.TRANSPORT.value,
                category_confidence=0.80,
            ),
            # rejected suggestion
            _tx(merchant="Nieznany 4", category_suggestion_rejected=True),
            # transfer is ignored entirely
            _tx(merchant="Own", is_transfer=True),
            # personal transfers are not category-review candidates
            _tx(
                merchant="Jan",
                transaction_type=TransactionType.OTHER.value,
            ),
            # debt payments affect cashflow but are not category-review candidates
            _tx(
                merchant="Alior Bank",
                title="Rata kredytu gotówkowego",
                transaction_type=TransactionType.DEBT_PAYMENT.value,
            ),
        ]
    )
    db_session.commit()

    counts = review.review_counts(db_session)

    assert counts.categorized == 1
    assert counts.uncategorized == 4  # category-review candidates only
    assert counts.no_suggestion == 1
    assert counts.low_confidence == 1
    assert counts.ready_to_accept == 1
    assert counts.rejected == 1


def test_rare_classes_below_threshold(db_session: Session) -> None:
    db_session.add_all(
        [_tx(merchant=f"Food {i}", category=Category.FOOD.value) for i in range(5)]
        + [_tx(merchant="Apteka", category=Category.HEALTH.value)]
        + [
            _tx(
                merchant="Jan",
                category=Category.OTHER.value,
                transaction_type=TransactionType.OTHER.value,
            )
        ]
    )
    db_session.commit()

    rare = review.rare_classes(db_session, threshold=3)

    labels = {r.category: r.count for r in rare}
    assert Category.FOOD.value not in labels  # food (5) is above threshold
    assert labels[Category.HEALTH.value] == 1
    assert labels[Category.SHOPPING.value] == 0


def test_recurring_unruled_skips_merchants_with_rule(db_session: Session) -> None:
    db_session.add_all(
        [_tx(merchant="Spotify AB", title="sub") for _ in range(3)]
        + [_tx(merchant="Local Shop", title="x") for _ in range(3)]
        + [
            _tx(
                merchant="Jan Kowalski",
                title="przelew",
                transaction_type=TransactionType.OTHER.value,
            )
            for _ in range(3)
        ]
    )
    db_session.add(
        PersonalRule(
            pattern="Spotify",
            pattern_norm="spotify",
            pattern_target="merchant",
            active=True,
        )
    )
    db_session.commit()

    result = review.recurring_unruled_merchants(db_session, min_count=3)

    merchants = {r.merchant for r in result}
    assert "Local Shop" in merchants
    assert "Spotify AB" not in merchants  # already covered by a personal rule
    assert "Jan Kowalski" not in merchants
