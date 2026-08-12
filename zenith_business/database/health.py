"""Database infrastructure health check (Prompt 01 §9).

A lightweight, non-destructive probe that confirms the database layer is
functioning: the connection opens, foreign keys are enforced, and a trivial
round-trip query succeeds. It creates no business tables and writes no data.
"""

from __future__ import annotations

from dataclasses import dataclass

from zenith_business.core.exceptions import DatabaseError
from zenith_business.core.logging_setup import get_logger
from zenith_business.database.connection import Database

_logger = get_logger("database.health")


@dataclass(frozen=True)
class DatabaseHealth:
    """Outcome of a health check."""

    ok: bool
    foreign_keys: bool
    sqlite_version: str
    message: str


def check_health(db: Database) -> DatabaseHealth:
    """Probe the database layer without mutating any data."""
    try:
        conn = db.connection()
        version_row = conn.execute("SELECT sqlite_version()").fetchone()
        sqlite_version = str(version_row[0]) if version_row else "unknown"
        fk = db.foreign_keys_enabled()

        # Trivial round-trip to confirm query execution works end to end.
        probe = conn.execute("SELECT 1").fetchone()
        round_trip_ok = probe is not None and probe[0] == 1

        ok = round_trip_ok and fk
        message = "healthy" if ok else "degraded: foreign keys not enforced"
        _logger.debug(
            "DB health: ok=%s fk=%s sqlite=%s", ok, fk, sqlite_version
        )
        return DatabaseHealth(
            ok=ok,
            foreign_keys=fk,
            sqlite_version=sqlite_version,
            message=message,
        )
    except DatabaseError as exc:
        _logger.error("DB health check failed: %s", exc)
        return DatabaseHealth(
            ok=False, foreign_keys=False, sqlite_version="unknown", message=str(exc)
        )
