"""Shared HTTP setup for Streamlit pages.

If AUTH_USERNAME / AUTH_PASSWORD are set in env, attaches HTTP Basic to every
`requests.*` call. Idempotent: safe to import multiple times.
"""
from __future__ import annotations

import os

import requests

_PATCHED_FLAG = "_finance_auth_patched"


def _install() -> None:
    user = os.environ.get("AUTH_USERNAME", "")
    pwd = os.environ.get("AUTH_PASSWORD", "")
    if not (user and pwd):
        return
    if getattr(requests, _PATCHED_FLAG, False):
        return
    auth = (user, pwd)
    original = requests.api.request

    def _request(method, url, **kwargs):
        kwargs.setdefault("auth", auth)
        return original(method, url, **kwargs)

    requests.api.request = _request  # type: ignore[assignment]
    setattr(requests, _PATCHED_FLAG, True)


_install()
