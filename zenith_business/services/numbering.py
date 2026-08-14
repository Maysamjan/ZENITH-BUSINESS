"""Document numbering service (Stage 02 §32).

Allocates gap-safe, unique, prefixed document numbers (SALE-000001, ...). The
read-then-increment is wrapped in a transaction so it is atomic; because
:class:`Database.transaction` nests via SAVEPOINTs, calling this from inside a
larger service transaction (e.g. posting a sale) is safe — the number is reclaimed
if that outer transaction rolls back.
"""

from __future__ import annotations

from zenith_business.database.connection import Database
from zenith_business.repositories.system import DocumentSequenceRepository


class DocumentNumberService:
    def __init__(self, db: Database, sequences: DocumentSequenceRepository) -> None:
        self._db = db
        self._sequences = sequences

    def allocate(self, doc_type: str) -> str:
        """Atomically consume and return the next number for ``doc_type``."""
        with self._db.transaction():
            return self._sequences.allocate(doc_type)

    def peek(self, doc_type: str) -> str | None:
        """Preview the next number WITHOUT consuming it (for draft display)."""
        return self._sequences.peek(doc_type)
