"""Parser registry — maps a BankSource to a concrete parser."""
from finance.domain.enums import BankSource
from finance.ingestion.base import BankParser

_REGISTRY: dict[BankSource, type[BankParser]] = {}


def register_parser(parser_cls: type[BankParser]) -> type[BankParser]:
    """Class decorator: register a parser under its declared source."""
    _REGISTRY[parser_cls.source] = parser_cls
    return parser_cls


def get_parser(source: BankSource) -> BankParser:
    if source not in _REGISTRY:
        raise KeyError(f"No parser registered for source={source}")
    return _REGISTRY[source]()


def available_sources() -> list[BankSource]:
    return list(_REGISTRY.keys())


def detect_source(headers: list[str]) -> BankSource | None:
    """Identify a registered parser by matching its expected headers.

    Returns the source whose ``expected_headers`` is fully contained in
    ``headers``. If multiple parsers match, the one with the most specific
    (largest) header set wins. Returns ``None`` when no parser claims it.
    """
    header_set = {h for h in headers if h}
    best: tuple[int, BankSource] | None = None
    for source, cls in _REGISTRY.items():
        expected: set[str] = getattr(cls, "expected_headers", set())
        if not expected:
            continue
        if expected.issubset(header_set):
            score = len(expected)
            if best is None or score > best[0]:
                best = (score, source)
    return best[1] if best else None
