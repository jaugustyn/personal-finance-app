"""Tests for /transactions endpoints (list, summary, PATCH category)."""
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.api.routers import transactions as transactions_router
from finance.domain.models import MerchantAlias, Transaction
from finance.ml.classification.policy import DEFAULT_POLICY


@pytest.fixture(autouse=True)
def _isolated_classification_policy(monkeypatch):
    monkeypatch.setattr(
        transactions_router,
        "active_classification_policy",
        lambda **_kwargs: DEFAULT_POLICY,
    )


def _seed(session, **overrides) -> Transaction:
    tx = Transaction(
        booking_date=date(2026, 4, 15),
        amount=Decimal("-50.00"),
        currency="PLN",
        direction="debit",
        merchant="Carrefour",
        title="Zakupy",
        category="food",
        category_predicted=None,
        category_confidence=None,
        source="pekao",
        dedup_hash="hash-1",
    )
    for k, v in overrides.items():
        setattr(tx, k, v)
    if tx.category is not None and tx.category_confirmation_method is None:
        tx.category_confirmation_method = "manual"
        tx.category_confirmed_at = datetime.now(UTC)
    session.add(tx)
    session.commit()
    session.refresh(tx)
    return tx


def test_list_transactions_empty(client) -> None:
    r = client.get("/transactions")
    assert r.status_code == 200
    assert r.json() == []


def test_list_transactions_returns_seeded(client, db_session) -> None:
    _seed(db_session)
    r = client.get("/transactions")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["merchant"] == "Carrefour"
    assert body[0]["category"] == "food"
    assert body[0]["category_suggestion_rejected"] is False
    assert body[0]["transaction_type"] is None
    assert body[0]["transaction_type_effective"] == "expense"
    assert body[0]["classification_decision"]["action"] == "manual"


def test_list_order_is_stable_for_equal_dates_after_mutation_and_filter(
    client, db_session
) -> None:
    first = _seed(
        db_session,
        transaction_type="expense",
        transaction_type_source="bank",
        dedup_hash="h-stable-order-first",
    )
    second = _seed(
        db_session,
        transaction_type="expense",
        transaction_type_source="bank",
        dedup_hash="h-stable-order-second",
    )
    older = _seed(
        db_session,
        booking_date=date(2026, 4, 14),
        transaction_type="expense",
        transaction_type_source="bank",
        dedup_hash="h-stable-order-older",
    )
    expected = [second.id, first.id, older.id]

    before = client.get("/transactions").json()
    accepted = client.post(f"/transactions/{first.id}/type-suggestion/accept")
    after = client.get("/transactions").json()
    filtered = client.get("/transactions?category=food").json()

    assert accepted.status_code == 200
    assert [row["id"] for row in before] == expected
    assert [row["id"] for row in after] == expected
    assert [row["id"] for row in filtered] == expected


def test_list_date_sort_is_global_and_stable(client, db_session) -> None:
    first = _seed(
        db_session,
        booking_date=date(2026, 4, 15),
        dedup_hash="h-date-sort-first",
    )
    second = _seed(
        db_session,
        booking_date=date(2026, 4, 15),
        dedup_hash="h-date-sort-second",
    )
    older = _seed(
        db_session,
        booking_date=date(2026, 4, 1),
        dedup_hash="h-date-sort-older",
    )

    first_page = client.get(
        "/transactions?sort_by=date&sort_direction=asc&limit=2"
    ).json()
    second_page = client.get(
        "/transactions?sort_by=date&sort_direction=asc&limit=2&offset=2"
    ).json()

    assert [row["id"] for row in first_page] == [older.id, first.id]
    assert [row["id"] for row in second_page] == [second.id]


def test_list_amount_sort_is_global_and_uses_base_currency(client, db_session) -> None:
    income = _seed(
        db_session,
        amount=Decimal("50"),
        amount_base=Decimal("50"),
        direction="credit",
        dedup_hash="h-amount-sort-income",
    )
    foreign_expense = _seed(
        db_session,
        amount=Decimal("-100"),
        amount_base=Decimal("-400"),
        currency="USD",
        base_currency="PLN",
        fx_rate=Decimal("4"),
        dedup_hash="h-amount-sort-foreign",
    )
    local_expense = _seed(
        db_session,
        amount=Decimal("-200"),
        amount_base=Decimal("-200"),
        dedup_hash="h-amount-sort-local",
    )
    invalid_foreign = _seed(
        db_session,
        amount=Decimal("999"),
        amount_base=None,
        currency="EUR",
        merchant="Unconverted",
        dedup_hash="h-amount-sort-unconverted",
    )

    first_page = client.get(
        "/transactions?sort_by=amount&sort_direction=desc&limit=2"
    ).json()
    second_page = client.get(
        "/transactions?sort_by=amount&sort_direction=desc&limit=2&offset=2"
    ).json()

    assert [row["id"] for row in first_page] == [income.id, local_expense.id]
    assert [row["id"] for row in second_page] == [
        foreign_expense.id,
        invalid_foreign.id,
    ]
    assert Decimal(str(second_page[1]["amount"])) == Decimal("999.00")
    assert second_page[1]["currency"] == "EUR"
    assert second_page[1]["amount_base"] is None


def test_filter_summary_reports_and_excludes_unconverted_amount(
    client, db_session
) -> None:
    _seed(
        db_session,
        amount=Decimal("-10"),
        currency="PLN",
        dedup_hash="h-summary-local",
    )
    _seed(
        db_session,
        amount=Decimal("-500"),
        amount_base=None,
        currency="USD",
        dedup_hash="h-summary-unconverted",
    )

    summary = client.get("/transactions/filter-summary").json()

    assert summary["count"] == 2
    assert Decimal(summary["total_expenses"]) == Decimal("10")
    assert summary["unconverted_count"] == 1


def test_list_merchant_sort_is_global(client, db_session) -> None:
    db_session.add_all(
        [
            MerchantAlias(
                alias_key="aaa raw",
                alias_label="AAA RAW",
                canonical_key="zulu",
                canonical_label="Zulu",
            ),
            MerchantAlias(
                alias_key="zzz raw",
                alias_label="ZZZ RAW",
                canonical_key="alfa",
                canonical_label="Alfa",
            ),
        ]
    )
    db_session.commit()
    zulu = _seed(
        db_session,
        merchant="AAA RAW",
        dedup_hash="h-merchant-sort-zulu",
    )
    alfa = _seed(
        db_session,
        merchant="ZZZ RAW",
        dedup_hash="h-merchant-sort-alfa",
    )
    market = _seed(
        db_session,
        merchant="Market",
        dedup_hash="h-merchant-sort-market",
    )

    first_page = client.get(
        "/transactions?sort_by=merchant&sort_direction=asc&limit=2"
    ).json()
    second_page = client.get(
        "/transactions?sort_by=merchant&sort_direction=asc&limit=2&offset=2"
    ).json()

    assert [row["merchant_display"] for row in first_page] == ["Alfa", "Market"]
    assert [row["id"] for row in first_page] == [alfa.id, market.id]
    assert [row["merchant_display"] for row in second_page] == ["Zulu"]
    assert [row["id"] for row in second_page] == [zulu.id]


def test_list_rejects_unknown_sort_field(client) -> None:
    response = client.get("/transactions?sort_by=category")

    assert response.status_code == 422


def test_list_transactions_date_filter(client, db_session) -> None:
    _seed(db_session, booking_date=date(2026, 4, 1), dedup_hash="h-april")
    _seed(db_session, booking_date=date(2026, 1, 1), dedup_hash="h-jan")
    r = client.get("/transactions?date_from=2026-03-01")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["booking_date"] == "2026-04-01"


def test_amount_range_uses_absolute_amount_in_base_currency(
    client, db_session
) -> None:
    _seed(
        db_session,
        amount=Decimal("-100"),
        amount_base=Decimal("-100"),
        merchant="Small local payment",
        dedup_hash="h-amount-range-small",
    )
    matched = _seed(
        db_session,
        amount=Decimal("-40"),
        amount_base=Decimal("-160"),
        currency="USD",
        base_currency="PLN",
        fx_rate=Decimal("4"),
        merchant="Foreign payment",
        dedup_hash="h-amount-range-match",
    )
    _seed(
        db_session,
        amount=Decimal("250"),
        amount_base=Decimal("250"),
        direction="credit",
        merchant="Large income",
        dedup_hash="h-amount-range-large",
    )

    rows = client.get("/transactions?min_amount=120&max_amount=200").json()
    summary = client.get(
        "/transactions/filter-summary?min_amount=120&max_amount=200"
    ).json()
    exported = client.get(
        "/transactions/export.csv?min_amount=120&max_amount=200"
    ).text

    assert [row["id"] for row in rows] == [matched.id]
    assert summary["count"] == 1
    assert "Foreign payment" in exported
    assert "Small local payment" not in exported
    assert "Large income" not in exported


def test_list_transactions_filters_suggestions_and_type(client, db_session) -> None:
    suggested = _seed(
        db_session,
        category=None,
        category_predicted="food",
        category_confidence=0.91,
        category_predicted_source="model",
        dedup_hash="h-suggested",
    )
    empty = _seed(db_session, category=None, category_predicted=None, dedup_hash="h-empty")
    low = _seed(
        db_session,
        category=None,
        category_predicted="transport",
        category_confidence=0.40,
        category_predicted_source="model",
        dedup_hash="h-low",
    )
    _seed(
        db_session,
        category=None,
        category_predicted="other",
        category_suggestion_rejected=True,
        dedup_hash="h-rejected",
    )

    r = client.get("/transactions?category_state=suggested&min_confidence=0.75")

    assert r.status_code == 200
    assert [row["id"] for row in r.json()] == [suggested.id]

    r2 = client.get("/transactions?category_state=rejected")
    assert r2.status_code == 200
    assert len(r2.json()) == 1
    assert r2.json()[0]["category_suggestion_rejected"] is True

    r3 = client.get("/transactions?category_state=assignable")
    assert r3.status_code == 200
    assert {row["id"] for row in r3.json()} == {
        empty.id,
        low.id,
        r2.json()[0]["id"],
        suggested.id,
    }


def test_list_transactions_filters_effective_type_state(client, db_session) -> None:
    confirmed = _seed(
        db_session,
        category=None,
        transaction_type="expense",
        transaction_type_source="manual",
        transaction_type_confirmation_method="manual",
        transaction_type_confirmed_at=datetime.now(UTC),
        dedup_hash="h-type-state-confirmed",
    )
    provisional = _seed(
        db_session,
        category=None,
        transaction_type_predicted="cash_withdrawal",
        transaction_type_predicted_source="bank",
        dedup_hash="h-type-state-provisional",
    )
    personal_auto = _seed(
        db_session,
        category=None,
        transaction_type="cash_withdrawal",
        transaction_type_source="rule",
        transaction_type_origin_ref="personal_rule:1",
        dedup_hash="h-type-state-personal-auto",
    )
    suggested = _seed(
        db_session,
        category=None,
        transaction_type_predicted="asset_allocation",
        transaction_type_predicted_source="rule",
        dedup_hash="h-type-state-suggested",
    )
    confirmed_rows = client.get(
        "/transactions?transaction_type_state=confirmed"
    ).json()
    provisional_rows = client.get(
        "/transactions?transaction_type_state=provisional"
    ).json()
    needs_review_rows = client.get(
        "/transactions?transaction_type_state=needs_review"
    ).json()
    bank_rows = client.get(
        "/transactions?transaction_type_state=needs_review"
        "&transaction_type_source=bank"
    ).json()
    suggested_rows = client.get(
        "/transactions?transaction_type_state=suggested"
    ).json()
    allocation_rows = client.get(
        "/transactions?transaction_type_state=needs_review"
        "&transaction_type=asset_allocation"
    ).json()
    effective_rows = client.get(
        "/transactions?transaction_type=asset_allocation"
    ).json()

    assert [row["id"] for row in confirmed_rows] == [confirmed.id]
    assert {row["id"] for row in provisional_rows} == {
        provisional.id,
        personal_auto.id,
        suggested.id,
    }
    assert {row["id"] for row in needs_review_rows} == {
        provisional.id,
        suggested.id,
    }
    assert [row["id"] for row in bank_rows] == [provisional.id]
    assert {row["id"] for row in suggested_rows} == {
        provisional.id,
        suggested.id,
    }
    assert [row["id"] for row in allocation_rows] == [suggested.id]
    assert effective_rows == []
    assert next(
        row for row in needs_review_rows if row["id"] == provisional.id
    )["transaction_type_needs_review"] is True
    assert all(row["id"] != personal_auto.id for row in needs_review_rows)


def test_directional_fallback_does_not_enter_type_review(client, db_session) -> None:
    debit = _seed(
        db_session,
        category=None,
        transaction_type_predicted="expense",
        transaction_type_predicted_source="rule",
        dedup_hash="h-type-fallback-debit",
    )
    credit = _seed(
        db_session,
        amount=Decimal("100.00"),
        direction="credit",
        category=None,
        transaction_type_predicted="income",
        transaction_type_predicted_source="rule",
        dedup_hash="h-type-fallback-credit",
    )
    salary = _seed(
        db_session,
        amount=Decimal("5000.00"),
        direction="credit",
        category=None,
        transaction_type_predicted="salary",
        transaction_type_predicted_source="rule",
        dedup_hash="h-type-special-credit",
    )

    rows = client.get("/transactions?transaction_type_state=needs_review").json()
    suggested_rows = client.get(
        "/transactions?transaction_type_state=suggested"
    ).json()

    assert [row["id"] for row in rows] == [salary.id]
    assert [row["id"] for row in suggested_rows] == [salary.id]
    all_rows = client.get("/transactions").json()
    review_state = {
        row["id"]: row["transaction_type_needs_review"] for row in all_rows
    }
    assert review_state[debit.id] is False
    assert review_state[credit.id] is False
    assert review_state[salary.id] is True


def test_list_transactions_rejects_invalid_direction(client) -> None:
    response = client.get("/transactions", params={"direction": "outgoing"})

    assert response.status_code == 422


def test_list_transactions_search_direction_and_category_filters(
    client, db_session
) -> None:
    allegro = _seed(
        db_session,
        merchant="Allegro",
        title="Płatność online Allegro",
        category=None,
        category_predicted="shopping",
        category_confidence=0.86,
        category_predicted_source="model",
        dedup_hash="h-filter-allegro",
    )
    income = _seed(
        db_session,
        amount=Decimal("5000"),
        direction="credit",
        merchant="ACME Sp. z o.o.",
        title="Wynagrodzenie za pracę",
        category=None,
        transaction_type="income",
        dedup_hash="h-filter-income",
    )
    _seed(
        db_session,
        amount=Decimal("-1200"),
        direction="debit",
        merchant="Anna Nowak",
        title="Przelew na telefon",
        category=None,
        category_predicted="shopping",
        category_confidence=0.99,
        transaction_type="other",
        dedup_hash="h-filter-stale-prediction",
    )
    transport = _seed(
        db_session,
        merchant="Uber",
        title="Przejazd",
        category="transport",
        dedup_hash="h-filter-transport",
    )

    search = client.get("/transactions?search=allegro")
    assert search.status_code == 200
    assert [row["id"] for row in search.json()] == [allegro.id]

    netflix = _seed(
        db_session,
        merchant="NETFLIX.COM AMSTERDAM",
        title="Card payment",
        category="subscriptions",
        dedup_hash="h-filter-netflix",
    )
    punctuation_free = client.get("/transactions?search=netflix com")
    assert punctuation_free.status_code == 200
    assert [row["id"] for row in punctuation_free.json()] == [netflix.id]

    direction = client.get("/transactions?direction=credit")
    assert direction.status_code == 200
    assert [row["id"] for row in direction.json()] == [income.id]

    predicted_category = client.get("/transactions?category=shopping")
    assert predicted_category.status_code == 200
    assert [row["id"] for row in predicted_category.json()] == [allegro.id]

    confirmed_shopping = client.get(
        "/transactions?category=shopping&category_state=categorized"
    )
    assert confirmed_shopping.status_code == 200
    assert confirmed_shopping.json() == []

    assigned_category = client.get("/transactions?category=transport")
    assert assigned_category.status_code == 200
    assert [row["id"] for row in assigned_category.json()] == [transport.id]

    export = client.get("/transactions/export.csv?category=shopping")
    assert export.status_code == 200
    assert "Allegro" in export.text
    assert "Uber" not in export.text


def test_export_csv_streams_attachment(client, db_session) -> None:
    _seed(db_session)
    r = client.get("/transactions/export.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    text = r.text
    lines = text.strip().splitlines()
    assert lines[0].startswith(
        "id,booking_date,booking_datetime,amount,currency,amount_base,"
    )
    assert len(lines) == 2
    assert "Carrefour" in lines[1]


def test_export_csv_escapes_formula_injection(client, db_session) -> None:
    """Cells starting with =/+/-/@ must be prefixed with ' to neutralise
    spreadsheet formula injection (CWE-1236)."""
    _seed(
        db_session,
        merchant="=cmd|'/c calc'!A1",
        title="+1+1",
        dedup_hash="h-injection",
    )
    r = client.get("/transactions/export.csv")
    assert r.status_code == 200
    text = r.text
    # Leading "'" is inserted by _safe(); the raw "=cmd" / "+1+1" cells must
    # not appear unprefixed.
    assert "'=cmd" in text
    assert "'+1+1" in text
    assert ",=cmd" not in text
    assert ",+1+1" not in text


def test_review_summary_buckets_and_recurring(client, db_session) -> None:
    # confirmed label
    _seed(db_session, merchant="Biedronka", category="health", dedup_hash="h-conf")
    # ready to accept
    _seed(
        db_session,
        merchant="Uber",
        category=None,
        category_predicted="transport",
        category_confidence=0.90,
        dedup_hash="h-ready",
    )
    # recurring uncategorized merchant (3x) with no rule
    for i in range(3):
        _seed(db_session, merchant="Local Cafe", category=None, dedup_hash=f"h-cafe-{i}")

    r = client.get("/transactions/review-summary?rare_class_threshold=5&recurring_min_count=3")

    assert r.status_code == 200
    body = r.json()
    assert body["counts"]["categorized"] == 1
    assert body["counts"]["ready_to_accept"] == 1
    assert body["counts"]["uncategorized"] == 4
    # health has 1 label -> below threshold 5
    assert {"category": "health", "count": 1} in body["rare_classes"]
    # Local Cafe appears 3x uncategorized with no personal rule
    assert any(m["merchant"] == "Local Cafe" for m in body["recurring_unruled"])
    assert body["feedback_quality"]["total_events"] == 0
    assert body["confusion_hotspots"] == []
    assert body["anomaly_feedback"]["reviewed"] == 0
    assert body["subscription_feedback"]["rejected"] == 0


def test_patch_category_updates(client, db_session) -> None:
    tx = _seed(db_session, category=None, dedup_hash="h-patch")
    r = client.patch(f"/transactions/{tx.id}/category", json={"category": "transport"})
    assert r.status_code == 200
    assert r.json()["category"] == "transport"
    assert r.json()["category_source"] == "manual"

    # Persistence check via fresh GET
    r2 = client.get("/transactions")
    assert r2.json()[0]["category"] == "transport"


def test_patch_category_on_credit_confirms_refund(client, db_session) -> None:
    tx = _seed(
        db_session,
        amount=Decimal("500"),
        direction="credit",
        transaction_type="income",
        category=None,
        dedup_hash="h-patch-income",
    )

    r = client.patch(f"/transactions/{tx.id}/category", json={"category": "food"})

    assert r.status_code == 200
    assert r.json()["transaction_type"] == "refund"
    assert r.json()["category"] == "food"


def test_patch_category_derives_parent_from_subcategory(client, db_session) -> None:
    tx = _seed(db_session, category=None, dedup_hash="h-patch-sub")

    r = client.patch(
        f"/transactions/{tx.id}/category",
        json={"category": None, "subcategory": "fuel"},
    )

    assert r.status_code == 200
    assert r.json()["category"] == "transport"
    assert r.json()["subcategory"] == "fuel"


def test_patch_category_rejects_mismatched_subcategory(client, db_session) -> None:
    tx = _seed(db_session, category=None, dedup_hash="h-patch-bad-sub")

    r = client.patch(
        f"/transactions/{tx.id}/category",
        json={"category": "food", "subcategory": "fuel"},
    )

    assert r.status_code == 422


def test_patch_category_can_remember_merchant_rule(client, db_session) -> None:
    tx = _seed(db_session, category=None, merchant="Lidl", dedup_hash="h-remember")

    r = client.patch(
        f"/transactions/{tx.id}/category",
        json={"category": "food", "remember_rule": True},
    )

    assert r.status_code == 200
    rules = client.get("/profile/rules").json()
    assert len(rules) == 1
    assert rules[0]["pattern"] == "Lidl"
    assert rules[0]["category"] == "food"
    assert rules[0]["mode"] == "suggest_only"


def test_patch_category_clears_with_null(client, db_session) -> None:
    tx = _seed(db_session, category="food", dedup_hash="h-clear")
    r = client.patch(f"/transactions/{tx.id}/category", json={"category": None})
    assert r.status_code == 200
    assert r.json()["category"] is None


def test_patch_category_404_on_missing(client) -> None:
    r = client.patch("/transactions/9999/category", json={"category": "food"})
    assert r.status_code == 404


def test_patch_type_updates_and_sets_transfer(client, db_session) -> None:
    tx = _seed(db_session, category=None, dedup_hash="h-type")
    r = client.patch(
        f"/transactions/{tx.id}/type",
        json={"transaction_type": "other"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["transaction_type"] == "other"
    assert body["is_transfer"] is False

    r2 = client.patch(
        f"/transactions/{tx.id}/type", json={"transaction_type": "own_transfer"}
    )
    assert r2.status_code == 200
    assert r2.json()["is_transfer"] is True


def test_patch_type_422_on_invalid(client, db_session) -> None:
    tx = _seed(db_session, category=None, dedup_hash="h-type-bad")
    r = client.patch(
        f"/transactions/{tx.id}/type", json={"transaction_type": "nonsense"}
    )
    assert r.status_code == 422


def test_patch_type_requires_direction_mismatch_confirmation(client, db_session) -> None:
    tx = _seed(db_session, category=None, dedup_hash="h-type-direction")

    warning = client.patch(
        f"/transactions/{tx.id}/type",
        json={"transaction_type": "salary"},
    )
    confirmed = client.patch(
        f"/transactions/{tx.id}/type",
        json={
            "transaction_type": "salary",
            "allow_direction_mismatch": True,
        },
    )

    assert warning.status_code == 409
    assert warning.json()["detail"]["code"] == "transaction_type_direction_mismatch"
    assert confirmed.status_code == 200
    assert confirmed.json()["transaction_type"] == "salary"


def test_bulk_type_suggestion_accepts_without_reject_restore_workflow(
    client, db_session
) -> None:
    accepted = _seed(
        db_session,
        category=None,
        transaction_type_predicted="expense",
        transaction_type_predicted_source="model",
        transaction_type_predicted_ref="type_model_version:test",
        transaction_type_confidence=0.93,
        dedup_hash="h-type-accept",
    )
    accept_response = client.post(
        "/transactions/bulk/type-suggestions/accept",
        json={"ids": [accepted.id]},
    )
    assert accept_response.status_code == 200
    assert accept_response.json()["affected"] == 1
    db_session.refresh(accepted)
    assert accepted.transaction_type == "expense"
    assert accepted.transaction_type_confirmation_method == "accepted_suggestion"
    assert (
        client.post(
            "/transactions/bulk/type-suggestions/reject",
            json={"ids": [accepted.id]},
        ).status_code
        == 404
    )


def test_quick_accept_confirms_active_provisional_type(client, db_session) -> None:
    tx = _seed(
        db_session,
        category=None,
        transaction_type="cash_withdrawal",
        transaction_type_source="bank",
        transaction_type_origin_ref="bank_type:pekao:v1:wyplata gotowki",
        dedup_hash="h-type-provisional-accept",
    )

    response = client.post(f"/transactions/{tx.id}/type-suggestion/accept")

    assert response.status_code == 200
    body = response.json()
    assert body["transaction_type"] == "cash_withdrawal"
    assert body["transaction_type_confirmation_method"] == "accepted_suggestion"
    assert body["transaction_type_is_provisional"] is False
    assert body["transaction_type_source"] == "bank"


def test_patch_annotations_sets_notes_and_dedup_tags(client, db_session) -> None:
    tx = _seed(db_session, category=None, dedup_hash="h-annot")
    r = client.patch(
        f"/transactions/{tx.id}/annotations",
        json={"notes": "  split with flatmate  ", "tags": ["Food", "food", " gift "]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["notes"] == "split with flatmate"
    assert body["tags"] == ["Food", "gift"]

    # Omitted fields stay unchanged; blank/null notes clear the note.
    r2 = client.patch(
        f"/transactions/{tx.id}/annotations", json={"notes": "   "}
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["notes"] is None
    assert body2["tags"] == ["Food", "gift"]

    r3 = client.patch(
        f"/transactions/{tx.id}/annotations", json={"notes": "again"}
    )
    assert r3.status_code == 200
    assert r3.json()["notes"] == "again"

    r4 = client.patch(
        f"/transactions/{tx.id}/annotations", json={"notes": None}
    )
    assert r4.status_code == 200
    assert r4.json()["notes"] is None

    r5 = client.patch(
        f"/transactions/{tx.id}/annotations", json={"tags": ["keep"]}
    )
    assert r5.status_code == 200
    assert r5.json()["notes"] is None
    assert r5.json()["tags"] == ["keep"]


def test_patch_annotations_404(client, db_session) -> None:
    r = client.patch("/transactions/999999/annotations", json={"notes": "x"})
    assert r.status_code == 404


def test_summary_by_category(client, db_session) -> None:
    _seed(db_session, category="food", amount=Decimal("-30.00"), dedup_hash="s1")
    _seed(
        db_session,
        category="food",
        amount=Decimal("-20.00"),
        dedup_hash="s2",
        booking_date=date(2026, 4, 16),
    )
    _seed(
        db_session,
        category="transport",
        amount=Decimal("-15.00"),
        dedup_hash="s3",
        booking_date=date(2026, 4, 17),
    )
    r = client.get("/transactions/summary/by-category")
    assert r.status_code == 200
    body = r.json()
    cats = {row["category"]: row for row in body}
    assert "food" in cats and "transport" in cats
    assert cats["food"]["count"] == 2
    assert cats["transport"]["count"] == 1


def test_accept_suggestions_endpoint(client, db_session) -> None:
    tx = _seed(
        db_session,
        category=None,
        category_predicted="food",
        category_confidence=0.88,
        category_predicted_source="model",
        dedup_hash="h-suggest",
    )

    r = client.post(
        "/transactions/bulk/accept-suggestions",
        json={"ids": [tx.id], "min_confidence": 0.75},
    )

    assert r.status_code == 200
    assert r.json()["affected"] == 1
    db_session.refresh(tx)
    assert tx.category == "food"
    assert tx.category_source == "model"


def test_accept_suggestions_endpoint_does_not_override_policy_manual(
    client, db_session
) -> None:
    tx = _seed(
        db_session,
        category=None,
        category_predicted="shopping",
        category_confidence=0.18,
        category_predicted_source="model",
        dedup_hash="h-suggest-low-override",
    )

    r = client.post(
        "/transactions/bulk/accept-suggestions",
        json={"ids": [tx.id], "min_confidence": 0},
    )

    assert r.status_code == 200
    assert r.json()["affected"] == 0
    db_session.refresh(tx)
    assert tx.category is None


def test_accept_suggestions_endpoint_manual_accepts_explicit_review_suggestion(
    client, db_session
) -> None:
    tx = _seed(
        db_session,
        category=None,
        category_predicted="shopping",
        category_confidence=0.18,
        category_predicted_source="model",
        dedup_hash="h-suggest-low-manual",
    )

    r = client.post(
        "/transactions/bulk/accept-suggestions",
        json={"ids": [tx.id], "min_confidence": 0, "manual": True},
    )

    assert r.status_code == 200
    assert r.json()["affected"] == 1
    db_session.refresh(tx)
    assert tx.category == "shopping"
    assert tx.category_source == "model"


def test_reject_suggestions_endpoint(client, db_session) -> None:
    tx = _seed(
        db_session,
        category=None,
        category_predicted="food",
        category_confidence=0.88,
        category_predicted_source="model",
        dedup_hash="h-reject",
    )

    r = client.post("/transactions/bulk/reject-suggestions", json={"ids": [tx.id]})

    assert r.status_code == 200
    assert r.json()["affected"] == 1
    db_session.refresh(tx)
    assert tx.category is None
    assert tx.category_predicted == "food"
    assert tx.category_confidence == 0.88
    assert tx.category_predicted_source == "model"
    assert tx.category_suggestion_rejected is True


def test_restore_suggestions_endpoint(client, db_session) -> None:
    tx = _seed(
        db_session,
        category=None,
        category_predicted="food",
        category_confidence=0.88,
        category_predicted_source="model",
        category_suggestion_rejected=True,
        dedup_hash="h-restore",
    )

    r = client.post("/transactions/bulk/restore-suggestions", json={"ids": [tx.id]})

    assert r.status_code == 200
    assert r.json()["affected"] == 1
    db_session.refresh(tx)
    assert tx.category_predicted == "food"
    assert tx.category_suggestion_rejected is False
