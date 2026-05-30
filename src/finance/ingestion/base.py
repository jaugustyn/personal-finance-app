"""Abstract bank parser interface."""
from abc import ABC, abstractmethod
from typing import IO

from finance.domain.dto import TransactionDTO
from finance.domain.enums import BankSource


class ParseError(Exception):
    """Raised when a CSV/file cannot be parsed by the chosen parser."""


class BankParser(ABC):
    """Parses a single bank export into a list of normalized TransactionDTOs.

    Implementations must be deterministic for the same input bytes — the
    ingestion layer relies on this to compute stable deduplication hashes.
    """

    source: BankSource
    #: Header names that must appear in the CSV for this parser to claim it.
    #: Used by the auto-detection helper in the registry. Empty for parsers
    #: that should never match automatically (e.g. the generic fallback).
    expected_headers: set[str] = set()

    @abstractmethod
    def parse(self, stream: IO[bytes], filename: str = "") -> list[TransactionDTO]:
        """Parse the export and return normalized transactions."""
