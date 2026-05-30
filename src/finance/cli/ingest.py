"""CLI: ingest a local CSV file into the database.

Usage (from project root, with .venv active and DB running):

    python -m finance.cli.ingest pekao "data/pekao_sa/styczen_kwiecien_2026_PekaoSA.csv"
    python -m finance.cli.ingest revolut "data/revolut/PLNaccount-statement_*.csv"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from finance.db import SessionLocal
from finance.domain.enums import BankSource
from finance.ingestion.service import ingest_file


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Ingest a bank CSV into the database.")
    p.add_argument("source", choices=[s.value for s in BankSource])
    p.add_argument("path", type=Path)
    args = p.parse_args(argv)

    if not args.path.is_file():
        print(f"File not found: {args.path}", file=sys.stderr)
        return 2

    source = BankSource(args.source)
    with SessionLocal() as session, args.path.open("rb") as fh:
        summary = ingest_file(
            session, source=source, filename=args.path.name, stream=fh
        )

    print(
        f"[{summary.source}] file={args.path.name}  "
        f"total={summary.total_rows}  inserted={summary.inserted}  "
        f"duplicates={summary.duplicates}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
