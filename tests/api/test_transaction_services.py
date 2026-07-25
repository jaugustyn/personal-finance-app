from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select

from finance.domain.models import MlFeedbackEvent, Transaction
from finance.ml.classification.policy import ClassificationPolicy
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


def test_transaction_filters_assignable_includes_rejected_expense_candidates(
    db_session,
) -> None:
    active = _tx(db_session, dedup_hash="assignable-active", category=None)
    rejected = _tx(
        db_session,
        dedup_hash="assignable-rejected",
        category=None,
        category_predicted="shopping",
        category_suggestion_rejected=True,
    )
    _tx(
        db_session,
        dedup_hash="assignable-income",
        amount=Decimal("1220"),
        direction="credit",
        category=None,
        category_predicted="food",
        category_suggestion_rejected=True,
        transaction_type="income",
    )
    _tx(
        db_session,
        dedup_hash="assignable-transfer",
        category=None,
        category_predicted="food",
        category_suggestion_rejected=True,
        is_transfer=True,
    )
    _tx(db_session, dedup_hash="assignable-done", category="food")

    rows = service.list_transactions(
        db_session,
        service.TransactionFilters(category_state="assignable"),
        limit=10,
        offset=0,
    )

    assert {row.id for row in rows} == {active.id, rejected.id}


def test_transaction_filters_rejected_only_expense_candidates(db_session) -> None:
    keep = _tx(
        db_session,
        dedup_hash="rejected-keep",
        category=None,
        category_predicted="shopping",
        category_suggestion_rejected=True,
    )
    _tx(
        db_session,
        dedup_hash="rejected-income",
        amount=Decimal("1220"),
        direction="credit",
        category=None,
        category_predicted="food",
        category_suggestion_rejected=True,
        transaction_type="income",
    )
    _tx(
        db_session,
        dedup_hash="rejected-transfer",
        category=None,
        category_predicted="food",
        category_suggestion_rejected=True,
        is_transfer=True,
    )

    rows = service.list_transactions(
        db_session,
        service.TransactionFilters(category_state="rejected"),
        limit=10,
        offset=0,
    )

    assert [row.id for row in rows] == [keep.id]


def test_transaction_filters_needs_review_only_expense_candidates(db_session) -> None:
    keep = _tx(db_session, dedup_hash="review-shopping", merchant="Allegro")
    _tx(
        db_session,
        dedup_hash="review-income",
        amount=Decimal("1220"),
        direction="credit",
        merchant="WSEI",
        title="Stypendium rektora student",
        transaction_type="income",
    )
    _tx(
        db_session,
        dedup_hash="review-person",
        merchant="Anna Nowak",
        title="Przelew na telefon",
        transaction_type="other",
    )
    _tx(
        db_session,
        dedup_hash="review-own",
        merchant="Wymiana na USD",
        title="Wymiana",
        transaction_type="own_transfer",
        is_transfer=True,
    )
    refund = _tx(
        db_session,
        dedup_hash="review-refund",
        amount=Decimal("100"),
        direction="credit",
        merchant="Allegro",
        title="Zwrot środków Allegro",
        transaction_type="refund",
    )
    _tx(
        db_session,
        dedup_hash="review-cash",
        merchant="ATM",
        title="Wypłata gotówki",
        transaction_type="cash_withdrawal",
    )
    _tx(
        db_session,
        dedup_hash="review-debt",
        merchant="Alior Bank",
        title="Rata kredytu gotówkowego",
        transaction_type="debt_payment",
    )

    rows = service.list_transactions(
        db_session,
        service.TransactionFilters(category_state="needs_review"),
        limit=10,
        offset=0,
    )

    assert [row.id for row in rows] == [refund.id, keep.id]


def test_merchant_groups_only_uncategorized_returns_expense_candidates(db_session) -> None:
    _tx(db_session, dedup_hash="group-allegro-1", merchant="Allegro")
    _tx(db_session, dedup_hash="group-allegro-2", merchant="Allegro")
    for i in range(2):
        _tx(
            db_session,
            dedup_hash=f"group-income-{i}",
            amount=Decimal("1220"),
            direction="credit",
            merchant="WSEI",
            title="Stypendium rektora student",
            transaction_type="income",
        )
        _tx(
            db_session,
            dedup_hash=f"group-transfer-{i}",
            merchant="Anna Nowak",
            title="Przelew na telefon",
            transaction_type="other",
        )
        _tx(
            db_session,
            dedup_hash=f"group-refund-{i}",
            amount=Decimal("100"),
            direction="credit",
            merchant="Zalando",
            title="Zwrot za zamówienie Zalando",
            transaction_type="refund",
        )
        _tx(
            db_session,
            dedup_hash=f"group-cash-{i}",
            merchant="ATM",
            title="Wypłata gotówki",
            transaction_type="cash_withdrawal",
        )
        _tx(
            db_session,
            dedup_hash=f"group-debt-{i}",
            merchant="Alior Bank",
            title="Rata kredytu gotówkowego",
            transaction_type="debt_payment",
        )

    groups = service.merchant_groups(
        db_session,
        only_uncategorized=True,
        min_count=2,
        limit=10,
    )

    assert [group.merchant for group in groups] == ["Allegro", "Zalando"]
    assert groups[0].sample_merchants == ["Allegro"]


def test_merchant_groups_sort_before_limit(db_session) -> None:
    for index in range(3):
        _tx(
            db_session,
            dedup_hash=f"group-frequent-{index}",
            merchant="Częsty sklep",
            amount=Decimal("-10"),
        )
    for index in range(2):
        _tx(
            db_session,
            dedup_hash=f"group-expensive-{index}",
            merchant="Duży wydatek",
            amount=Decimal("-1000"),
        )

    groups = service.merchant_groups(
        db_session,
        only_uncategorized=True,
        min_count=2,
        limit=1,
        sort_by="amount",
        sort_direction="asc",
    )

    assert [group.merchant for group in groups] == ["Duży wydatek"]

    second_page = service.merchant_groups(
        db_session,
        only_uncategorized=True,
        min_count=2,
        limit=1,
        offset=1,
        sort_by="count",
        sort_direction="desc",
    )

    assert [group.merchant for group in second_page] == ["Duży wydatek"]


def test_merchant_groups_can_sort_by_common_category(db_session) -> None:
    for index in range(2):
        _tx(
            db_session,
            dedup_hash=f"group-housing-{index}",
            merchant="Czynsz",
            category="housing",
        )
        _tx(
            db_session,
            dedup_hash=f"group-food-{index}",
            merchant="Sklep",
            category="food",
        )

    groups = service.merchant_groups(
        db_session,
        only_uncategorized=False,
        min_count=2,
        limit=10,
        sort_by="category",
        sort_direction="asc",
    )

    assert [group.common_category for group in groups] == ["food", "housing"]


def test_merchant_sort_hydrates_only_the_requested_page(db_session) -> None:
    for index, merchant in enumerate(["Zulu", "Alfa", "Market", "Beta", "Omega"]):
        _tx(
            db_session,
            dedup_hash=f"merchant-projection-{index}",
            merchant=merchant,
        )
    db_session.expunge_all()

    rows = service.list_transactions(
        db_session,
        service.TransactionFilters(),
        limit=2,
        offset=1,
        sort_by="merchant",
        sort_direction="asc",
    )

    loaded_transactions = [
        value
        for value in db_session.identity_map.values()
        if isinstance(value, Transaction)
    ]
    assert [row.merchant for row in rows] == ["Beta", "Market"]
    assert {row.id for row in loaded_transactions} == {row.id for row in rows}


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
    _tx(
        db_session,
        booking_datetime=datetime(2026, 4, 15, 13, 45, tzinfo=UTC),
        merchant="=cmd",
        title="+1+1",
        dedup_hash="csv",
        notes="private note",
        tags=["ważne", "2026"],
        raw_category="bank category",
        raw_transaction_type="card payment",
        external_id="bank-123",
        transaction_type="expense",
        transaction_type_source="manual",
        transaction_type_confirmation_method="manual",
        transaction_type_confirmed_at=datetime(2026, 4, 16, tzinfo=UTC),
    )

    csv_text = "".join(
        service.export_csv_lines(db_session, service.TransactionFilters())
    )

    assert "'=cmd" in csv_text
    assert "'+1+1" in csv_text
    row = next(csv.DictReader(io.StringIO(csv_text)))
    assert row["tags"] == '["ważne","2026"]'
    assert row["notes"] == "private note"
    assert row["raw_category"] == "bank category"
    assert row["raw_transaction_type"] == "card payment"
    assert row["booking_datetime"].startswith("2026-04-15 13:45:00")
    assert row["external_id"] == "bank-123"
    assert "amount_base" in row
    assert row["transaction_type_confirmation_method"] == "manual"


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


def test_bulk_categorize_confirms_credit_as_refund(db_session) -> None:
    purchase = _tx(db_session, dedup_hash="bulk-purchase")
    income = _tx(
        db_session,
        dedup_hash="bulk-income",
        amount=Decimal("500"),
        direction="credit",
        transaction_type="income",
    )

    affected = service.bulk_categorize(
        db_session,
        ids=[purchase.id, income.id],
        merchant=None,
        category="shopping",
        mark_transfer=None,
    )

    assert affected == 2
    db_session.refresh(purchase)
    db_session.refresh(income)
    assert purchase.category == "shopping"
    assert income.category == "shopping"
    assert income.transaction_type == "refund"


def test_update_type_to_non_candidate_clears_category_and_prediction(db_session) -> None:
    tx = _tx(
        db_session,
        dedup_hash="type-clear",
        category="food",
        category_source="manual",
        category_predicted="shopping",
        category_confidence=0.91,
        category_predicted_source="model",
    )

    updated = service.update_transaction_type(db_session, tx.id, "debt_payment")

    assert updated is not None
    db_session.refresh(tx)
    assert tx.transaction_type == "debt_payment"
    assert tx.category is None
    assert tx.category_source is None
    assert tx.category_predicted is None
    assert tx.category_suggestion_rejected is False


def test_bulk_set_transaction_type_keeps_category_when_still_candidate(db_session) -> None:
    first = _tx(
        db_session,
        dedup_hash="bulk-type-1",
        category="food",
        category_source="manual",
    )
    second = _tx(
        db_session,
        dedup_hash="bulk-type-2",
        category="shopping",
        category_source="manual",
    )

    affected = service.bulk_categorize(
        db_session,
        ids=[first.id, second.id],
        merchant=None,
        transaction_type="expense",
    )

    assert affected == 2
    db_session.refresh(first)
    db_session.refresh(second)
    assert first.transaction_type == "expense"
    assert second.transaction_type == "expense"
    assert first.category == "food"
    assert second.category == "shopping"


def test_bulk_set_transaction_type_clears_category_for_non_candidate(db_session) -> None:
    tx = _tx(
        db_session,
        dedup_hash="bulk-type-clear",
        category="food",
        category_source="manual",
        category_predicted="shopping",
        category_confidence=0.88,
        category_predicted_source="model",
    )

    affected = service.bulk_categorize(
        db_session,
        ids=[tx.id],
        merchant=None,
        transaction_type="other",
    )

    assert affected == 1
    db_session.refresh(tx)
    assert tx.transaction_type == "other"
    assert tx.category is None
    assert tx.category_predicted is None
    assert tx.category_suggestion_rejected is False


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
    event = db_session.execute(
        select(MlFeedbackEvent).where(
            MlFeedbackEvent.event_type == "accept_suggestion"
        )
    ).scalar_one()
    assert event.event_type == "accept_suggestion"
    assert event.transaction_id == high.id
    assert event.predicted_category == "food"
    assert event.final_category == "food"
    assert event.confidence == 0.91


def test_accept_suggestions_promotes_only_expense_candidates(db_session) -> None:
    high = _tx(
        db_session,
        dedup_hash="sug-expense",
        category=None,
        category_predicted="shopping",
        category_confidence=0.91,
        category_predicted_source="model",
        transaction_type="expense",
    )
    credit = _tx(
        db_session,
        dedup_hash="sug-credit",
        amount=Decimal("500"),
        direction="credit",
        category=None,
        category_predicted="food",
        category_confidence=0.99,
        category_predicted_source="model",
        transaction_type="income",
    )
    transfer = _tx(
        db_session,
        dedup_hash="sug-transfer",
        category=None,
        category_predicted="food",
        category_confidence=0.99,
        category_predicted_source="model",
        is_transfer=True,
    )
    debt = _tx(
        db_session,
        dedup_hash="sug-debt",
        category=None,
        category_predicted="other",
        category_confidence=0.99,
        category_predicted_source="model",
        transaction_type="debt_payment",
    )

    affected = service.accept_suggestions(db_session, ids=None, min_confidence=0.75)

    assert affected == 1
    db_session.refresh(high)
    db_session.refresh(credit)
    db_session.refresh(transfer)
    db_session.refresh(debt)
    assert high.category == "shopping"
    assert credit.category is None
    assert transfer.category is None
    assert debt.category is None


def test_accept_suggestions_uses_policy_and_skips_other(db_session) -> None:
    food = _tx(
        db_session,
        dedup_hash="sug-policy-food",
        category=None,
        category_predicted="food",
        category_confidence=0.80,
        category_predicted_source="model",
    )
    other = _tx(
        db_session,
        dedup_hash="sug-policy-other",
        category=None,
        category_predicted="other",
        category_confidence=0.99,
        category_predicted_source="model",
    )
    high_threshold = _tx(
        db_session,
        dedup_hash="sug-policy-threshold",
        category=None,
        category_predicted="transport",
        category_confidence=0.80,
        category_predicted_source="model",
    )
    policy = ClassificationPolicy(
        default_threshold=0.55,
        per_category_thresholds={"transport": 0.90},
    )

    affected = service.accept_suggestions(
        db_session,
        ids=None,
        min_confidence=0,
        policy=policy,
    )

    assert affected == 1
    db_session.refresh(food)
    db_session.refresh(other)
    db_session.refresh(high_threshold)
    assert food.category == "food"
    assert other.category is None
    assert high_threshold.category is None


def test_accept_suggestions_skips_rejected_predictions(db_session) -> None:
    tx = _tx(
        db_session,
        dedup_hash="sug-rejected",
        category=None,
        category_predicted="food",
        category_confidence=0.99,
        category_predicted_source="model",
        category_suggestion_rejected=True,
    )

    affected = service.accept_suggestions(db_session, ids=None, min_confidence=0.75)

    assert affected == 0
    db_session.refresh(tx)
    assert tx.category is None
    assert tx.category_suggestion_rejected is True


def test_reject_suggestions_keeps_prediction_and_marks_rejected(db_session) -> None:
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
    assert tx.category_predicted == "food"
    assert tx.category_confidence == 0.91
    assert tx.category_predicted_source == "model"
    assert tx.category_suggestion_rejected is True
    event = db_session.execute(
        select(MlFeedbackEvent).where(MlFeedbackEvent.event_type == "reject_suggestion")
    ).scalar_one()
    assert event.event_type == "reject_suggestion"
    assert event.transaction_id == tx.id
    assert event.predicted_category == "food"
    assert event.final_category is None


def test_reject_suggestions_skips_non_candidates(db_session) -> None:
    credit = _tx(
        db_session,
        dedup_hash="reject-credit",
        amount=Decimal("500"),
        direction="credit",
        category=None,
        category_predicted="food",
        category_confidence=0.99,
        transaction_type="income",
    )
    transfer = _tx(
        db_session,
        dedup_hash="reject-transfer",
        category=None,
        category_predicted="food",
        category_confidence=0.99,
        is_transfer=True,
    )

    affected = service.reject_suggestions(db_session, ids=None)

    assert affected == 0
    db_session.refresh(credit)
    db_session.refresh(transfer)
    assert credit.category_suggestion_rejected is False
    assert transfer.category_suggestion_rejected is False


def test_restore_suggestions_reactivates_rejected_prediction(db_session) -> None:
    tx = _tx(
        db_session,
        dedup_hash="restore-service",
        category=None,
        category_predicted="food",
        category_confidence=0.91,
        category_predicted_source="model",
        category_suggestion_rejected=True,
    )

    affected = service.restore_suggestions(db_session, ids=[tx.id])

    assert affected == 1
    db_session.refresh(tx)
    assert tx.category_predicted == "food"
    assert tx.category_suggestion_rejected is False


def test_update_category_records_manual_feedback(db_session) -> None:
    tx = _tx(
        db_session,
        dedup_hash="manual-feedback",
        category=None,
        category_predicted="transport",
        category_confidence=0.44,
        category_predicted_source="model",
    )

    updated = service.update_category(db_session, tx.id, "food")

    assert updated is not None
    event = db_session.execute(
        select(MlFeedbackEvent).where(MlFeedbackEvent.event_type == "manual_category")
    ).scalar_one()
    assert event.event_type == "manual_category"
    assert event.transaction_id == tx.id
    assert event.predicted_category == "transport"
    assert event.final_category == "food"
    assert event.confidence == 0.44
