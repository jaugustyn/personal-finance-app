"""Bank statement parsers + ingestion service."""
# Import parser modules so their @register_parser decorators run.
from finance.ingestion import pekao as _pekao  # noqa: F401, E402
from finance.ingestion import revolut as _revolut  # noqa: F401, E402
from finance.ingestion.base import BankParser, ParseError
from finance.ingestion.registry import available_sources, get_parser, register_parser

__all__ = [
    "BankParser",
    "ParseError",
    "available_sources",
    "get_parser",
    "register_parser",
]
