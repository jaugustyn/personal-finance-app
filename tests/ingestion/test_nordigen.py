"""Unit tests for the Nordigen client (no network — uses requests mocks)."""
from unittest.mock import patch

import pytest

from finance.ingestion.nordigen import API_BASE, NordigenClient, NordigenError


class _FakeResp:
    def __init__(self, status_code: int, payload: object | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


def test_authenticate_caches_token() -> None:
    client = NordigenClient(secret_id="sid", secret_key="skey")
    with patch("finance.ingestion.nordigen.requests.post") as p:
        p.return_value = _FakeResp(200, {"access": "tok123", "refresh": "ref"})
        token = client.authenticate()
    assert token == "tok123"
    assert client._access_token == "tok123"
    assert client._refresh_token == "ref"


def test_authenticate_raises_on_error() -> None:
    client = NordigenClient(secret_id="sid", secret_key="skey")
    with patch("finance.ingestion.nordigen.requests.post") as p:
        p.return_value = _FakeResp(401, text="bad creds")
        with pytest.raises(NordigenError):
            client.authenticate()


def test_list_institutions_uses_country_param() -> None:
    client = NordigenClient(secret_id="sid", secret_key="skey")
    client._access_token = "tok"
    payload = [{"id": "PKO_BPKOPLPW", "name": "PKO BP"}]
    with patch("finance.ingestion.nordigen.requests.get") as g:
        g.return_value = _FakeResp(200, payload)
        out = client.list_institutions("PL")
    assert out == payload
    assert g.call_args.args == (f"{API_BASE}/institutions/",)
    assert g.call_args.kwargs["params"] == {"country": "PL"}


def test_get_account_transactions_with_dates() -> None:
    client = NordigenClient(secret_id="sid", secret_key="skey")
    client._access_token = "tok"
    with patch("finance.ingestion.nordigen.requests.get") as g:
        g.return_value = _FakeResp(200, {"transactions": {"booked": []}})
        client.get_account_transactions("acc-1", date_from="2026-01-01", date_to="2026-04-30")
    assert g.call_args.kwargs["params"] == {
        "date_from": "2026-01-01",
        "date_to": "2026-04-30",
    }
