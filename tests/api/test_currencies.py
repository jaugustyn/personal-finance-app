"""Currency API is fixed to PLN as the analytical base."""
from datetime import date

from finance.domain.models import UserProfile


def test_currency_status_ignores_legacy_profile_base(client, db_session) -> None:
    db_session.add(UserProfile(id=1, base_currency="EUR"))
    db_session.commit()

    response = client.get("/currencies/status")

    assert response.status_code == 200
    assert response.json()["base_currency"] == "PLN"


def test_manual_rate_payload_cannot_override_base_currency(client) -> None:
    response = client.post(
        "/currencies/rates",
        json={
            "currency": "USD",
            "base_currency": "EUR",
            "rate_date": date(2026, 1, 10).isoformat(),
            "rate": "4.00",
        },
    )

    assert response.status_code == 422


def test_manual_rate_rejects_pln_to_pln_pair(client) -> None:
    response = client.post(
        "/currencies/rates",
        json={
            "currency": "PLN",
            "rate_date": date(2026, 1, 10).isoformat(),
            "rate": "1.00",
        },
    )

    assert response.status_code == 400
