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


def test_single_linear_alembic_history() -> None:
    scripts = _script_directory()
    heads = scripts.get_heads()
    bases = scripts.get_bases()
    revisions = list(scripts.walk_revisions())

    assert len(heads) == 1, f"expected a single migration head, found: {heads}"
    assert len(bases) == 1, f"expected a single migration base, found: {bases}"

    child_counts: dict[str, int] = {}
    revision_ids = {revision.revision for revision in revisions}
    for revision in revisions:
        parent = revision.down_revision
        assert not isinstance(parent, tuple), (
            f"merge revision is not allowed in linear history: {revision.revision}"
        )
        if parent is None:
            continue
        assert parent in revision_ids, (
            f"missing parent {parent!r} for revision {revision.revision!r}"
        )
        child_counts[parent] = child_counts.get(parent, 0) + 1

    branches = [revision for revision, count in child_counts.items() if count > 1]
    assert not branches, f"migration history contains branches after: {branches}"
