"""Persistence helpers for transaction imports."""
from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from finance.domain.enums import BankSource
from finance.domain.models import Import, Transaction


class TransactionImportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_import(self, *, source: BankSource, filename: str, total_rows: int) -> Import:
        import_row = Import(source=source, filename=filename, total_rows=total_rows)
        self.session.add(import_row)
        self.session.flush()
        return import_row

    def insert_transaction_values(self, values: dict[str, object]) -> bool:
        stmt = (
            pg_insert(Transaction)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["dedup_hash"])
            .returning(Transaction.id)
        )
        return self.session.execute(stmt).first() is not None

    def finalize_import(self, import_row: Import, *, inserted: int, duplicates: int) -> None:
        import_row.inserted = inserted
        import_row.duplicates = duplicates
