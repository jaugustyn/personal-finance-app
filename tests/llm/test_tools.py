"""Tests for LLM tools with an in-memory SQLite session."""
from datetime import date
from decimal import Decimal

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from finance.domain.models import Base, Transaction
from finance.llm.tools import (
    cashflow_overview,
    category_review_summary,
    compare_periods,
    get_spending,
    list_anomalies,
    list_subscriptions,
    recommend_savings,
    top_categories,
    top_merchants,
)
from finance.profile.service import update_profile


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _add_tx(s: Session, **kw) -> None:
    defaults = {
        "currency": "PLN",
        "direction": "debit",
        "merchant": "Shop",
        "title": "",
        "source": "pko",
        "dedup_hash": kw.get("merchant", "x") + str(kw.get("amount", 0)) + str(kw.get("booking_date")),
    }
    defaults.update(kw)
    s.add(Transaction(**defaults))


def test_get_spending_filters_period_and_category(session):
    _add_tx(session, booking_date=date(2026, 4, 1), amount=Decimal("-100"), category="food")
    _add_tx(session, booking_date=date(2026, 4, 2), amount=Decimal("-50"), category="food")
    _add_tx(session, booking_date=date(2026, 3, 31), amount=Decimal("-999"), category="food")
    _add_tx(session, booking_date=date(2026, 4, 3), amount=Decimal("-30"), category="transport")
    _add_tx(
        session,
        booking_date=date(2026, 4, 4),
        amount=Decimal("-999"),
        category="food",
        is_transfer=True,
        dedup_hash="llm-transfer-food",
    )
    _add_tx(
        session,
        booking_date=date(2026, 4, 5),
        amount=Decimal("-999"),
        category=None,
        category_predicted="food",
        dedup_hash="llm-predicted-food",
    )
    session.commit()

    res = get_spending(session, {"period": "2026-04", "category": "food"})
    assert res["transactions"] == 2
    assert res["total"] == pytest.approx(150.0)


def test_top_merchants_orders_by_total(session):
    for i in range(3):
        _add_tx(session, booking_date=date(2026, 4, i + 1),
                amount=Decimal("-20"), merchant="Lidl")
    _add_tx(session, booking_date=date(2026, 4, 5),
            amount=Decimal("-200"), merchant="OpenAI")
    _add_tx(
        session,
        booking_date=date(2026, 4, 6),
        amount=Decimal("-999"),
        merchant="Own Broker",
        is_transfer=True,
        dedup_hash="llm-top-transfer",
    )
    session.commit()

    res = top_merchants(session, {"period": "2026-04", "limit": 2})
    names = [m["merchant"] for m in res["merchants"]]
    assert names[0] == "OpenAI"
    assert "Lidl" in names


def test_top_categories_uses_confirmed_candidate_expenses_only(session):
    _add_tx(
        session,
        booking_date=date(2026, 4, 1),
        amount=Decimal("-100"),
        category="food",
        transaction_type="purchase",
        dedup_hash="llm-cat-food",
    )
    _add_tx(
        session,
        booking_date=date(2026, 4, 2),
        amount=Decimal("-50"),
        category="shopping",
        transaction_type="purchase",
        dedup_hash="llm-cat-shopping",
    )
    _add_tx(
        session,
        booking_date=date(2026, 4, 3),
        amount=Decimal("-70"),
        category=None,
        category_predicted="food",
        transaction_type="purchase",
        dedup_hash="llm-cat-predicted-only",
    )
    _add_tx(
        session,
        booking_date=date(2026, 4, 4),
        amount=Decimal("-999"),
        category="food",
        is_transfer=True,
        transaction_type="own_transfer",
        dedup_hash="llm-cat-transfer",
    )
    _add_tx(
        session,
        booking_date=date(2026, 4, 5),
        amount=Decimal("-888"),
        category="food",
        transaction_type="refund",
        dedup_hash="llm-cat-refund",
    )
    _add_tx(
        session,
        booking_date=date(2026, 4, 6),
        amount=Decimal("-777"),
        category="housing",
        transaction_type="debt_payment",
        dedup_hash="llm-cat-debt",
    )
    _add_tx(
        session,
        booking_date=date(2026, 4, 7),
        amount=Decimal("-666"),
        category="other",
        transaction_type="cash_withdrawal",
        dedup_hash="llm-cat-cash",
    )
    session.commit()

    res = top_categories(session, {"period": "2026-04", "limit": 5})

    assert res["total_candidate_spend"] == pytest.approx(220.0)
    assert res["categorized_total"] == pytest.approx(150.0)
    assert res["uncategorized_total"] == pytest.approx(70.0)
    assert res["category_coverage"] == pytest.approx(150.0 / 220.0)
    assert [row["category"] for row in res["categories"]] == ["food", "shopping"]


def test_cashflow_overview_excludes_transfers(session):
    _add_tx(
        session,
        booking_date=date(2026, 4, 1),
        amount=Decimal("1000"),
        direction="credit",
        merchant="Employer",
        dedup_hash="llm-cashflow-income",
    )
    _add_tx(
        session,
        booking_date=date(2026, 4, 2),
        amount=Decimal("-300"),
        merchant="Market",
        dedup_hash="llm-cashflow-expense",
    )
    _add_tx(
        session,
        booking_date=date(2026, 4, 3),
        amount=Decimal("-500"),
        merchant="Own account",
        is_transfer=True,
        dedup_hash="llm-cashflow-transfer",
    )
    session.commit()

    res = cashflow_overview(session, {"period": "2026-04"})

    assert res["income"] == pytest.approx(1000.0)
    assert res["expenses"] == pytest.approx(300.0)
    assert res["net"] == pytest.approx(700.0)
    assert res["savings_rate"] == pytest.approx(0.7)
    assert res["transactions"] == 2


def test_compare_periods_delta(session):
    _add_tx(session, booking_date=date(2026, 3, 5), amount=Decimal("-100"))
    _add_tx(session, booking_date=date(2026, 4, 5), amount=Decimal("-150"))
    session.commit()

    res = compare_periods(session, {"period_a": "2026-04", "period_b": "2026-03"})
    assert res["a"]["total"] == pytest.approx(150.0)
    assert res["b"]["total"] == pytest.approx(100.0)
    assert res["delta"] == pytest.approx(50.0)
    assert res["delta_pct"] == pytest.approx(50.0)


def test_list_subscriptions_picks_whitelisted(session):
    for i in range(4):
        _add_tx(session, booking_date=date(2026, i + 1, 5),
                amount=Decimal("-19.99"), merchant="Spotify")
    session.commit()

    res = list_subscriptions(session, {"min_confidence": 0.5})
    assert any(s["merchant"].lower() == "spotify" for s in res["subscriptions"])


def test_list_subscriptions_honors_hidden_feedback(session):
    from finance.ml.subscriptions.service import record_subscription_feedback

    for i in range(4):
        _add_tx(
            session,
            booking_date=date(2026, i + 1, 5),
            amount=Decimal("-19.99"),
            merchant="Spotify",
            dedup_hash=f"hidden-spotify-{i}",
        )
    session.commit()

    record_subscription_feedback(session, merchant="Spotify", action="hide")

    res = list_subscriptions(session, {"min_confidence": 0.0})
    assert all(s["merchant"].lower() != "spotify" for s in res["subscriptions"])


def test_list_anomalies_empty_db(session):
    res = list_anomalies(session, {"period": "2026-04"})
    assert res["anomalies"] == []


def test_list_anomalies_returns_reason_list(session, monkeypatch):
    _add_tx(
        session,
        id=1,
        booking_date=date(2026, 4, 10),
        amount=Decimal("-500"),
        merchant="Odd merchant",
    )
    session.commit()

    class _Result:
        df = pd.DataFrame(
            [
                {
                    "id": 1,
                    "booking_date": date(2026, 4, 10),
                    "amount": -500.0,
                    "direction": "debit",
                    "merchant": "Odd merchant",
                    "title": "",
                    "category": "food",
                    "anomaly": True,
                    "severity": 0.9,
                    "reasons": "nietypowo wysoka kwota, nowy odbiorca",
                }
            ]
        )

    from finance.llm import insight_tools

    monkeypatch.setattr(
        insight_tools.anomaly_service,
        "detect_anomalies",
        lambda *_args, **_kwargs: _Result(),
    )

    res = list_anomalies(session, {"period": "2026-04"})
    assert res["anomalies"][0]["reasons"] == [
        "nietypowo wysoka kwota",
        "nowy odbiorca",
    ]


def test_list_anomalies_honors_ignore_feedback(session, monkeypatch):
    from finance.llm import insight_tools
    from finance.ml.anomaly.service import record_anomaly_feedback

    _add_tx(
        session,
        id=1,
        booking_date=date(2026, 4, 10),
        amount=Decimal("-500"),
        merchant="Odd merchant",
        dedup_hash="ignored-anomaly",
    )
    session.commit()

    class _Result:
        df = pd.DataFrame(
            [
                {
                    "id": 1,
                    "booking_date": date(2026, 4, 10),
                    "amount": -500.0,
                    "direction": "debit",
                    "merchant": "Odd merchant",
                    "title": "",
                    "category": "food",
                    "anomaly": True,
                    "severity": 0.9,
                    "reasons": "nietypowo wysoka kwota",
                }
            ]
        )

    monkeypatch.setattr(
        insight_tools.anomaly_service,
        "detect_anomalies",
        lambda *_args, **_kwargs: _Result(),
    )

    record_anomaly_feedback(session, transaction_id=1, action="ignore_merchant")

    res = list_anomalies(session, {"period": "2026-04"})
    assert res["anomalies"] == []


def test_recommend_savings_uses_deterministic_facts(session, monkeypatch):
    _add_tx(
        session,
        booking_date=date(2026, 3, 10),
        amount=Decimal("-100"),
        category="food",
        merchant="Market",
        dedup_hash="rec-prev-food",
    )
    _add_tx(
        session,
        booking_date=date(2026, 4, 10),
        amount=Decimal("-180"),
        category="food",
        merchant="Market",
        dedup_hash="rec-current-food",
    )
    _add_tx(
        session,
        booking_date=date(2026, 4, 11),
        amount=Decimal("-50"),
        category="transport",
        merchant="Fuel",
        dedup_hash="rec-current-transport",
    )
    session.commit()

    from finance.llm import recommendation_tools

    monkeypatch.setattr(recommendation_tools, "list_subscription_rows", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(recommendation_tools, "list_anomaly_rows", lambda *_args, **_kwargs: [])

    res = recommend_savings(session, {"period": "2026-04", "limit": 3})

    assert res["total_current"] == pytest.approx(230.0)
    assert res["total_previous"] == pytest.approx(100.0)
    assert res["category_opportunities"][0]["category"] == "food"
    assert res["category_opportunities"][0]["delta"] == pytest.approx(80.0)


def test_recommend_savings_uses_profile_goals_and_limits(session, monkeypatch):
    update_profile(
        session,
        monthly_savings_goal=Decimal("500.00"),
        category_limits={"food": 150.0},
    )
    _add_tx(
        session,
        booking_date=date(2026, 4, 1),
        amount=Decimal("1000.00"),
        direction="credit",
        category=None,
        merchant="Employer",
        dedup_hash="profile-income",
    )
    _add_tx(
        session,
        booking_date=date(2026, 4, 10),
        amount=Decimal("-180.00"),
        category="food",
        merchant="Market",
        dedup_hash="profile-food",
    )
    session.commit()

    from finance.llm import recommendation_tools

    monkeypatch.setattr(recommendation_tools, "list_subscription_rows", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(recommendation_tools, "list_anomaly_rows", lambda *_args, **_kwargs: [])

    res = recommend_savings(session, {"period": "2026-04", "limit": 3})

    assert res["savings_goal"]["target"] == pytest.approx(500.0)
    assert res["savings_goal"]["actual_savings"] == pytest.approx(820.0)
    assert res["savings_goal"]["met"] is True
    assert res["category_limit_alerts"][0]["category"] == "food"
    assert res["category_limit_alerts"][0]["over_by"] == pytest.approx(30.0)


def test_category_review_summary_counts_uncertain_suggestions(session):
    _add_tx(
        session,
        booking_date=date(2026, 4, 1),
        amount=Decimal("-40"),
        category=None,
        category_predicted=None,
        dedup_hash="review-no-suggestion",
    )
    _add_tx(
        session,
        booking_date=date(2026, 4, 2),
        amount=Decimal("-50"),
        category=None,
        category_predicted="food",
        category_confidence=0.40,
        dedup_hash="review-low",
    )
    _add_tx(
        session,
        booking_date=date(2026, 4, 3),
        amount=Decimal("-60"),
        category=None,
        category_predicted="transport",
        category_confidence=0.90,
        dedup_hash="review-high",
    )
    session.commit()

    res = category_review_summary(session, {"threshold": 0.55, "accept_threshold": 0.75})

    assert res["total_uncategorized"] == 3
    assert res["without_suggestion"] == 1
    assert res["low_confidence"] == 1
    assert res["high_confidence"] == 1
    assert res["by_predicted_category"][0]["count"] == 1
