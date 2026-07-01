"""Bank statement parsers + ingestion service."""
# Import parser modules so their @register_parser decorators run.
from finance.ingestion import pekao as _pekao  # noqa: F401, E402
from finance.ingestion import revolut as _revolut  # noqa: F401, E402
from finance.ingestion.base import BankParser, ParseError
from finance.ingestion.registry import available_sources, get_parser, register_parser
from finance.ingestion.types import (
    FxRateMode,
    ImportQualityIssue,
    ImportQualityReport,
    IssueSeverity,
)

__all__ = [
    "BankParser",
    "FxRateMode",
    "ImportQualityIssue",
    "ImportQualityReport",
    "IssueSeverity",
    "ParseError",
    "available_sources",
    "get_parser",
    "register_parser",
]
