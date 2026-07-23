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
    ],
)
def test_numeric_runtime_settings_reject_invalid_values(field, value) -> None:
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
