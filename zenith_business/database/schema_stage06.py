"""Forward migration 0008 — Stage 06 inventory & stock management (additive only).

Stock was already a signed movement ledger, so Stage 06 needs exactly one schema
change: a place to keep the human explanation of a movement.

* ``inventory_movements.notes`` (nullable) — the reason an adjustment was made,
  what a transfer was for, where an opening balance came from. Until now a
  reason was written only to the audit log, so the stock-movement history the
  operator reads could not show it. Documents keep referencing their source via
  ``reference_type``/``reference_id``; this column carries the words.

Nothing is renamed, dropped or back-filled with invented data — existing
movements simply have no note. No new permission is needed: ``inventory.view``,
``inventory.adjust`` and ``inventory.transfer`` already exist and are granted.
"""

from __future__ import annotations

import sqlite3


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def migrate_stage06(conn: sqlite3.Connection) -> None:
    """Migration 0008 — movement notes + reporting indexes."""
    if "notes" not in _columns(conn, "inventory_movements"):
        conn.execute("ALTER TABLE inventory_movements ADD COLUMN notes TEXT")

    # Stock screens read movements by item, by warehouse and by date; index the
    # combinations the Stage 06 reports actually scan.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_invmov_item_wh"
        " ON inventory_movements(item_id, warehouse_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_invmov_date"
        " ON inventory_movements(movement_date)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_invmov_type"
        " ON inventory_movements(movement_type)")
