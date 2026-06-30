"""Report and timestamp helpers for classifier status."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from finance.ml.classification.constants import REPORTS_DIR


def iso_mtime(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def latest_report_path(reports_dir: Path = REPORTS_DIR) -> Path | None:
    reports = sorted(reports_dir.glob("classification_*.json"))
    if not reports:
        return None
    return max(reports, key=lambda path: path.stat().st_mtime)


def load_latest_report(reports_dir: Path = REPORTS_DIR) -> dict[str, Any]:
    path = latest_report_path(reports_dir)
    if path is None:
        return {"path": None, "updated_at": None, "report": None}
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        report = {"error": str(exc)}
    return {
        "path": str(path),
        "updated_at": iso_mtime(path),
        "report": report,
    }
