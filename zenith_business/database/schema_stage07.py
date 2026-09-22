"""Forward migration 0009 — Stage 07 purchases parity (additive only).

Stage 07 brings purchases up to the contracts the sales side already carries.
Almost nothing new has to be stored: supplier payments, the supplier ledger and
purchase returns all already have their tables. Two things are genuinely missing:

* ``purchases.corrected_from_id`` (nullable, self-referencing) — the mirror of
  ``sales.corrected_from_id``. Correction amends the bill IN PLACE, so this column
  is not used to point at a replacement document; it exists so the purchase header
  carries the same shape as the sale header and a future superseding workflow has
  somewhere to record a link.
* ``purchases.correct`` permission, granted to Administrator, Manager and
  Accountant — exactly as ``sales.correct`` is.

Nothing is renamed, dropped or back-filled.
"""

from __future__ import annotations

import sqlite3

STAGE07_PERMISSIONS: list[tuple[str, str]] = [
    ("purchases.correct", "purchases"),
]

_ROLE_GRANTS: dict[str, list[str]] = {
    "MANAGER": ["purchases.correct"],
    "ACCOUNTANT": ["purchases.correct"],
}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def migrate_stage07(conn: sqlite3.Connection) -> None:
    """Migration 0009 — purchase correction link column + purchases.correct."""
    if "corrected_from_id" not in _columns(conn, "purchases"):
        conn.execute(
            "ALTER TABLE purchases ADD COLUMN corrected_from_id INTEGER"
            " REFERENCES purchases(id) ON DELETE SET NULL")

    conn.executemany(
        "INSERT OR IGNORE INTO permissions (code, category) VALUES (?, ?)",
        STAGE07_PERMISSIONS)
    perm_ids = {c: pid for pid, c in conn.execute("SELECT id, code FROM permissions").fetchall()}
    role_ids = {c: rid for rid, c in conn.execute("SELECT id, code FROM roles").fetchall()}

    admin_id = role_ids.get("ADMINISTRATOR")
    if admin_id is not None:
        for code, _cat in STAGE07_PERMISSIONS:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (admin_id, perm_ids[code]))
    for role_code, perms in _ROLE_GRANTS.items():
        rid = role_ids.get(role_code)
        if rid is None:
            continue
        for code in perms:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (rid, perm_ids[code]))

    # The purchase list and the net-position reads scan returns by their source
    # bill and by line; index both the way Stage 06 indexed the movement reads.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_pret_purchase"
        " ON purchase_returns(purchase_id, status)")
