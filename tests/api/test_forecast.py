"""API tests for forecast data readiness and diagnostics."""
from decimal import Decimal

import pandas as pd

from finance.domain.models import Transaction


def _seed_months(db_session, count: int) -> None:
    current_month = pd.Timestamp.today().to_period("M").to_timestamp()
    first_month = current_month - pd.offsets.MonthBegin(count)
    for index in range(count):
        booking_date = (first_month + pd.offsets.MonthBegin(index)).date()
        db_session.add(
            Transaction(
                booking_date=booking_date,
                amount=Decimal(str(-(1000 + index * 25))),
                currency="PLN",
                amount_base=Decimal(str(-(1000 + index * 25))),
                base_currency="PLN",
                direction="debit",
                transaction_type="expense",
                merchant="Forecast merchant",
                title="Monthly spending",
                category="food",
                source="generic",
                dedup_hash=f"forecast-{count}-{index}",
                is_transfer=False,
            )
        )
    db_session.commit()


def test_forecast_reports_data_not_ready(client, db_session) -> None:
    _seed_months(db_session, 10)

    response = client.get("/forecast?horizon=3")

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "forecast_data_not_ready"
    assert detail["history_months"] == 10
    assert detail["required_history_months"] == 14
    assert detail["active_months"] == 10


def test_forecast_returns_validation_diagnostics(client, db_session) -> None:
    _seed_months(db_session, 14)

    response = client.get("/forecast?horizon=3")

    assert response.status_code == 200
    body = response.json()
    assert body["base_currency"] == "PLN"
    assert body["history_months"] == 14
    assert body["active_months"] == 14
    assert body["required_history_months"] == 14
    assert body["validation_folds"] >= 6
    assert isinstance(body["is_baseline"], bool)
    assert len(body["forecast"]) == 3
