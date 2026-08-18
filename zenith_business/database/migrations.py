"""Lightweight, real migration system (Stage 02 §6).

Migrations are ordered by integer version and applied exactly once inside an
atomic transaction — a failed migration rolls back completely and stops the run.
The applied version is tracked in ``schema_migrations`` so future Stage 03+
schema changes never require deleting customer data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import sqlite3

from zenith_business.core.clock import now_iso
from zenith_business.core.logging_setup import get_logger
from zenith_business.database.connection import Database
from zenith_business.database.schema import create_schema, seed_baseline
from zenith_business.database.schema_stage03 import migrate_stage03
from zenith_business.database.schema_stage04 import migrate_stage04
from zenith_business.database.schema_stage05 import migrate_stage05
from zenith_business.database.schema_owner_fixes import migrate_owner_fixes

_logger = get_logger("database.migrations")


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    up: Callable[[sqlite3.Connection], None]


# Ordered migration list. Append new migrations with the next version number;
# never edit or reorder an already-released migration.
MIGRATIONS: list[Migration] = [
    Migration(1, "initial_schema", create_schema),
    Migration(2, "baseline_seed", seed_baseline),
    Migration(3, "stage03_master_data", migrate_stage03),
    Migration(4, "stage04_sales_purchases_returns", migrate_stage04),
    Migration(5, "stage05_receipts_payments_expenses", migrate_stage05),
    Migration(6, "owner_fixes_walkin_ledger_void", migrate_owner_fixes),
]


class MigrationRunner:
    """Applies pending migrations and tracks the schema version."""

    def __init__(self, db: Database) -> None:
        self._db = db

    def _ensure_table(self) -> None:
        self._db.connection().execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )

    def current_version(self) -> int:
        self._ensure_table()
        row = self._db.connection().execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def latest_version(self) -> int:
        return MIGRATIONS[-1].version if MIGRATIONS else 0

    def pending(self) -> list[Migration]:
        current = self.current_version()
        return [m for m in MIGRATIONS if m.version > current]

    def migrate(self) -> list[int]:
        """Apply all pending migrations atomically. Returns applied versions."""
        applied: list[int] = []
        for migration in self.pending():
            _logger.info("Applying migration %d — %s", migration.version, migration.name)
            with self._db.transaction() as conn:  # rolls back on failure
                migration.up(conn)
                conn.execute(
                    "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (migration.version, migration.name, now_iso()),
                )
            applied.append(migration.version)
        if applied:
            _logger.info("Migrations applied: %s (schema v%d)", applied, self.current_version())
        return applied
