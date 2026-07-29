"""Configuration invariants validated before application startup."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from finance.config import Settings


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("ollama_timeout_s", 0),
        ("ollama_num_ctx", 0),
        ("ollama_num_predict", -1),
        ("rate_limit_per_minute", -1),
        ("database_url", ""),
    ],
)
def test_runtime_settings_reject_invalid_values(field, value) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})


def test_basic_auth_accepts_both_credentials_or_neither() -> None:
    disabled = Settings(_env_file=None, auth_username="", auth_password="")
    enabled = Settings(
        _env_file=None,
        auth_username="alice",
        auth_password="secret",
    )

    assert not disabled.auth_username
    assert enabled.auth_username == "alice"


@pytest.mark.parametrize("trusted_hosts", ["", "*", "localhost,*"])
def test_trusted_hosts_require_explicit_values(trusted_hosts: str) -> None:
    with pytest.raises(ValidationError, match="explicit host names"):
        Settings(_env_file=None, api_trusted_hosts=trusted_hosts)


@pytest.mark.parametrize(
    "cors_origins",
    [
        "*",
        "http://*.example.test",
        "localhost:3000",
        "ftp://localhost:3000",
        "http://localhost:3000/api",
        "http://localhost:3000?debug=true",
        "http://localhost:3000#fragment",
        "http://user:password@localhost:3000",
        "http://localhost:invalid",
    ],
)
def test_cors_requires_explicit_http_origins(cors_origins: str) -> None:
    with pytest.raises(ValidationError, match="CORS_ALLOW_ORIGINS"):
        Settings(_env_file=None, cors_allow_origins=cors_origins)


def test_cors_accepts_multiple_origins_or_can_be_disabled() -> None:
    configured = Settings(
        _env_file=None,
        cors_allow_origins=" http://localhost:3000,https://finance.example.test ",
    )
    disabled = Settings(_env_file=None, cors_allow_origins="")

    assert configured.cors_origins == [
        "http://localhost:3000",
        "https://finance.example.test",
    ]
    assert disabled.cors_origins == []
