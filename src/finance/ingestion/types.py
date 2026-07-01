"""Shared ingestion service contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

FxRateMode = Literal["require_existing", "prefetch_missing"]
IssueSeverity = Literal["error", "warning"]


@dataclass(frozen=True)
class ImportQualityIssue:
    code: str
    severity: IssueSeverity
    count: int
    sample_rows: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class ImportQualityReport:
    total_rows: int
    valid_rows: int
    blocking_issues: int
    warnings: int
    issues: list[ImportQualityIssue]
