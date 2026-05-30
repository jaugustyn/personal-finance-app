from __future__ import annotations

from datetime import date
from decimal import Decimal

from finance.domain.models import Transaction
from finance.transactions import service


def _tx(session, **overrides) -> Transaction:
    tx = Transaction(
        booking_date=date(2026, 4, 15),
        amount=Decimal("-50"),
        currency="PLN",
        direction="debit",
        merchant="Shop",
        title="Title",
        category=None,
        source="pekao",
        dedup_hash=f"h-{len(session.new)}-{overrides.get('merchant', 'shop')}",
    )
    for key, value in overrides.items():
        setattr(tx, key, value)
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def test_transaction_filters_exclude_transfers(db_session) -> None:
    keep = _tx(db_session, dedup_hash="keep", is_transfer=False)
    _tx(db_session, dedup_hash="transfer", is_transfer=True)

    rows = service.list_transactions(
        db_session,
        service.TransactionFilters(include_transfers=False),
        limit=10,
        offset=0,
    )

    assert [row.id for row in rows] == [keep.id]


def test_transaction_filters_needs_review_excludes_rejected(db_session) -> None:
    keep = _tx(db_session, dedup_hash="review-keep", category=None)
    _tx(
        db_session,
        dedup_hash="review-rejected",
        category=None,
        category_suggestion_rejected=True,
    )
    _tx(db_session, dedup_hash="review-done", category="food")

    rows = service.list_transactions(
        db_session,
        service.TransactionFilters(category_state="needs_review"),
        limit=10,
        offset=0,
    )

    assert [row.id for row in rows] == [keep.id]


def test_transaction_filters_review_priority_orders_uncertain_rows_first(
    db_session,
) -> None:
    high = _tx(
        db_session,
        dedup_hash="review-high",
        category=None,
        category_predicted="food",
        category_confidence=0.92,
        booking_date=date(2026, 4, 20),
    )
    missing = _tx(
        db_session,
        dedup_hash="review-missing",
        category=None,
        category_predicted=None,
        booking_date=date(2026, 4, 1),
    )
    low = _tx(
        db_session,
        dedup_hash="review-low",
        category=None,
        category_predicted="transport",
        category_confidence=0.30,
        booking_date=date(2026, 4, 10),
    )

    rows = service.list_transactions(
        db_session,
        service.TransactionFilters(
            category_state="needs_review",
            review_priority=True,
        ),
        limit=10,
        offset=0,
    )

    assert [row.id for row in rows] == [missing.id, low.id, high.id]


def test_transaction_filters_max_confidence(db_session) -> None:
    keep = _tx(
        db_session,
        dedup_hash="max-conf-keep",
        category=None,
        category_predicted="food",
        category_confidence=0.40,
    )
    _tx(
        db_session,
        dedup_hash="max-conf-drop",
        category=None,
        category_predicted="food",
        category_confidence=0.90,
    )

    rows = service.list_transactions(
        db_session,
        service.TransactionFilters(max_confidence=0.55),
        limit=10,
        offset=0,
    )

    assert [row.id for row in rows] == [keep.id]


def test_export_csv_lines_escapes_formula_cells(db_session) -> None:
    _tx(db_session, merchant="=cmd", title="+1+1", dedup_hash="csv")

    csv_text = "".join(
        service.export_csv_lines(db_session, service.TransactionFilters())
    )

    assert "'=cmd" in csv_text
    assert "'+1+1" in csv_text


def test_bulk_categorize_and_delete(db_session) -> None:
    first = _tx(db_session, merchant="Lidl", dedup_hash="b1")
    second = _tx(db_session, merchant="Lidl", dedup_hash="b2")

    affected = service.bulk_categorize(
        db_session,
        ids=None,
        merchant="Lidl",
        category="food",
        mark_transfer=True,
    )

    assert affected == 2
    assert service.bulk_delete(db_session, [first.id, second.id]) == 2


def test_accept_suggestions_promotes_high_confidence_predictions(db_session) -> None:
    high = _tx(
        db_session,
        dedup_hash="sug-high",
        category=None,
        category_predicted="food",
        category_confidence=0.91,
        category_predicted_source="model",
    )
    _tx(
        db_session,
        dedup_hash="sug-low",
        category=None,
        category_predicted="transport",
        category_confidence=0.20,
        category_predicted_source="model",
    )

    affected = service.accept_suggestions(db_session, ids=None, min_confidence=0.75)

    assert affected == 1
    db_session.refresh(high)
    assert high.category == "food"
    assert high.category_source == "model"


def test_reject_suggestions_clears_prediction_and_marks_rejected(db_session) -> None:
    tx = _tx(
        db_session,
        dedup_hash="reject-service",
        category=None,
        category_predicted="food",
        category_confidence=0.91,
        category_predicted_source="model",
    )

    affected = service.reject_suggestions(db_session, ids=[tx.id])

    assert affected == 1
    db_session.refresh(tx)
    assert tx.category_predicted is None
    assert tx.category_confidence is None
    assert tx.category_predicted_source is None
    assert tx.category_suggestion_rejected is True
