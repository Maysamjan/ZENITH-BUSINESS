"""Financial-year repository (Stage 03 §6).

Dates are ISO ``YYYY-MM-DD`` (lexicographic order == chronological). A partial
unique index guarantees at most one active year at the DB level; the service owns
the higher-level rules (activation switch, close, posting checks).
"""

from __future__ import annotations

from zenith_business.core.clock import now_iso
from zenith_business.repositories.base import BaseRepository


class FinancialYearRepository(BaseRepository):
    def create(self, *, name: str, start_date: str, end_date: str,
               is_active: bool = False) -> int:
        ts = now_iso()
        return self._insert(
            "INSERT INTO financial_years (name, start_date, end_date, status, is_active,"
            " created_at, updated_at) VALUES (?, ?, ?, 'OPEN', ?, ?, ?)",
            (name, start_date, end_date, 1 if is_active else 0, ts, ts))

    def get(self, year_id: int) -> dict | None:
        return self._one("SELECT * FROM financial_years WHERE id = ?", (year_id,))

    def get_by_name(self, name: str) -> dict | None:
        return self._one("SELECT * FROM financial_years WHERE name = ?", (name,))

    def active(self) -> dict | None:
        return self._one("SELECT * FROM financial_years WHERE is_active = 1 LIMIT 1")

    def list_all(self) -> list[dict]:
        return self._all("SELECT * FROM financial_years ORDER BY start_date DESC")

    def clear_active(self) -> None:
        self._exec("UPDATE financial_years SET is_active = 0, updated_at = ? WHERE is_active = 1",
                   (now_iso(),))

    def set_active(self, year_id: int) -> None:
        self._exec("UPDATE financial_years SET is_active = 1, updated_at = ? WHERE id = ?",
                   (now_iso(), year_id))

    def close(self, year_id: int, user_id: int | None) -> None:
        ts = now_iso()
        self._exec(
            "UPDATE financial_years SET status = 'CLOSED', is_active = 0, closed_at = ?,"
            " closed_by = ?, updated_at = ? WHERE id = ?", (ts, user_id, ts, year_id))

    def reopen(self, year_id: int) -> None:
        self._exec(
            "UPDATE financial_years SET status = 'OPEN', closed_at = NULL, closed_by = NULL,"
            " updated_at = ? WHERE id = ?", (now_iso(), year_id))

    def overlapping(self, start_date: str, end_date: str, exclude_id: int | None = None) -> list[dict]:
        """Years whose range overlaps [start,end] (service uses this to warn/prevent)."""
        sql = ("SELECT * FROM financial_years WHERE NOT (end_date < ? OR start_date > ?)")
        params: list = [start_date, end_date]
        if exclude_id is not None:
            sql += " AND id <> ?"
            params.append(exclude_id)
        return self._all(sql, tuple(params))
