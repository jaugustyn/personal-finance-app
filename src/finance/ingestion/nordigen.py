"""GoCardless Bank Account Data (formerly Nordigen) — minimal client.

Public endpoint base: https://bankaccountdata.gocardless.com/api/v2/

Auth: client posts {secret_id, secret_key} to /token/new/, gets a 24h access
token + 30d refresh token. We cache the token in-memory only; persistence is
the user's responsibility (env vars / secrets manager).

Used only for the Phase 2 decision gate — we list PL institutions and dry-run
the requisition flow against the sandbox.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import requests

logger = logging.getLogger(__name__)

API_BASE = "https://bankaccountdata.gocardless.com/api/v2"
DEFAULT_TIMEOUT = 15


class NordigenError(RuntimeError):
    """Raised when the API returns a non-2xx response."""


@dataclass
class NordigenClient:
    secret_id: str
    secret_key: str
    base_url: str = API_BASE
    timeout: int = DEFAULT_TIMEOUT
    _access_token: str | None = field(default=None, init=False, repr=False)
    _refresh_token: str | None = field(default=None, init=False, repr=False)

    @classmethod
    def from_env(cls) -> NordigenClient:
        sid = os.environ.get("NORDIGEN_SECRET_ID")
        skey = os.environ.get("NORDIGEN_SECRET_KEY")
        if not sid or not skey:
            raise NordigenError(
                "Set NORDIGEN_SECRET_ID and NORDIGEN_SECRET_KEY env vars."
            )
        return cls(secret_id=sid, secret_key=skey)

    # ---------------------------- auth ---------------------------------
    def authenticate(self) -> str:
        url = f"{self.base_url}/token/new/"
        r = requests.post(
            url,
            json={"secret_id": self.secret_id, "secret_key": self.secret_key},
            timeout=self.timeout,
        )
        if r.status_code != 200:
            raise NordigenError(f"Auth failed: {r.status_code} {r.text}")
        data = r.json()
        self._access_token = data["access"]
        self._refresh_token = data.get("refresh")
        return self._access_token

    def _headers(self) -> dict[str, str]:
        if self._access_token is None:
            self.authenticate()
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        r = requests.get(
            f"{self.base_url}{path}",
            headers=self._headers(),
            params=params,
            timeout=self.timeout,
        )
        if r.status_code == 401 and self._refresh_token:
            # Force a fresh login and retry once.
            self._access_token = None
            r = requests.get(
                f"{self.base_url}{path}",
                headers=self._headers(),
                params=params,
                timeout=self.timeout,
            )
        if r.status_code >= 300:
            raise NordigenError(f"GET {path} -> {r.status_code} {r.text}")
        return r.json()

    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        r = requests.post(
            f"{self.base_url}{path}",
            headers=self._headers(),
            json=payload,
            timeout=self.timeout,
        )
        if r.status_code >= 300:
            raise NordigenError(f"POST {path} -> {r.status_code} {r.text}")
        return r.json()

    # --------------------------- API ----------------------------------
    def list_institutions(self, country: str = "PL") -> list[dict[str, Any]]:
        return self._get("/institutions/", params={"country": country})

    def create_requisition(
        self,
        institution_id: str,
        redirect_url: str,
        reference: str,
        user_language: str = "PL",
    ) -> dict[str, Any]:
        return self._post(
            "/requisitions/",
            {
                "institution_id": institution_id,
                "redirect": redirect_url,
                "reference": reference,
                "user_language": user_language,
            },
        )

    def get_requisition(self, requisition_id: str) -> dict[str, Any]:
        return self._get(f"/requisitions/{requisition_id}/")

    def get_account_transactions(
        self, account_id: str, date_from: str | None = None, date_to: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        return self._get(f"/accounts/{account_id}/transactions/", params=params or None)
