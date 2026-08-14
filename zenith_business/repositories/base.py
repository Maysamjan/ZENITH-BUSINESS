"""Base repository helpers (Stage 02 §47).

Repositories use the shared :class:`Database` connection; transactions are opened
by the *service* layer, so repository writes automatically participate in the
enclosing transaction. All queries are parameterized (never string-built).
"""

from __future__ import annotations

from typing import Any, Sequence

from zenith_business.database.connection import Database


class BaseRepository:
    def __init__(self, db: Database) -> None:
        self._db = db

    @property
    def _conn(self):
        return self._db.connection()

    def _one(self, sql: str, params: Sequence[Any] = ()) -> dict | None:
        row = self._conn.execute(sql, params).fetchone()
        return dict(row) if row is not None else None

    def _all(self, sql: str, params: Sequence[Any] = ()) -> list[dict]:
        return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def _scalar(self, sql: str, params: Sequence[Any] = ()) -> Any:
        row = self._conn.execute(sql, params).fetchone()
        return row[0] if row is not None else None

    def _insert(self, sql: str, params: Sequence[Any] = ()) -> int:
        return int(self._conn.execute(sql, params).lastrowid)

    def _exec(self, sql: str, params: Sequence[Any] = ()) -> int:
        return self._conn.execute(sql, params).rowcount
