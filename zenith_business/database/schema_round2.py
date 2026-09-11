"""Forward migration 0007 — owner review round 2 (additive only).

Supports the safe posted-Sales-Invoice **correction** workflow without editing any
LOCKED table:

* ``sales.corrected_from_id`` (nullable, self-referencing) links a replacement
  invoice to the original it superseded, so a correction keeps full document
  history (the original stays VOID/superseded, the new invoice references it).
* ``sales.correct`` permission gates the authorized correction action (granted to
  Administrator + Manager + Accountant).

Self-service Account Settings (own password / username change) needs no new
permission — any authenticated user may manage their own account, verified by the
current password.
"""

from __future__ import annotations

import sqlite3

ROUND2_PERMISSIONS: list[tuple[str, str]] = [
    ("sales.correct", "sales"),
]

_ROLE_GRANTS: dict[str, list[str]] = {
    "MANAGER": ["sales.correct"],
    "ACCOUNTANT": ["sales.correct"],
}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def migrate_round2(conn: sqlite3.Connection) -> None:
    """Migration 0007 — sales correction link column + sales.correct permission."""
    if "corrected_from_id" not in _columns(conn, "sales"):
        conn.execute(
            "ALTER TABLE sales ADD COLUMN corrected_from_id INTEGER"
            " REFERENCES sales(id) ON DELETE SET NULL")

    conn.executemany(
        "INSERT OR IGNORE INTO permissions (code, category) VALUES (?, ?)",
        ROUND2_PERMISSIONS)
    perm_ids = {c: pid for pid, c in conn.execute("SELECT id, code FROM permissions").fetchall()}
    role_ids = {c: rid for rid, c in conn.execute("SELECT id, code FROM roles").fetchall()}

    admin_id = role_ids.get("ADMINISTRATOR")
    if admin_id is not None:
        for code, _cat in ROUND2_PERMISSIONS:
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
