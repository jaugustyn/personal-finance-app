"""Regression guard for Alembic migration history.

A branched history (multiple heads) makes ``alembic upgrade head`` fail at
container start, which previously surfaced as a 502 from the web proxy.
"""
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _script_directory() -> ScriptDirectory:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    return ScriptDirectory.from_config(config)


def test_single_alembic_head() -> None:
    heads = _script_directory().get_heads()
    assert len(heads) == 1, f"expected a single migration head, found: {heads}"
