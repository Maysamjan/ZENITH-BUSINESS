"""Forward migration 0006 — owner manual-test hardening pass (additive only).

This migration supports the owner-reported Stage 05 fixes WITHOUT editing any
LOCKED Stage 01-05 table. It is additive, atomic and idempotent:

* Walk-in / general customer support (defect #2): three nullable snapshot columns
  on the LOCKED ``sales`` header so an unregistered buyer's entered name/phone/
  address are preserved on the sale itself (and therefore on re-open and on the
  printed invoice) without forcing a permanent ``parties`` record. A registered
  sale keeps ``party_id`` set; a walk-in sale has ``party_id IS NULL`` and a
  ``walkin_name`` — the two remain clearly distinguishable.
* New permissions (defects #3/#4): ``sales.void`` / ``purchases.void`` for the
  safe posted-document reversal, and ``parties.ledger`` for the customer/supplier
  account-history screens. Balances/ledger are still DERIVED from the authoritative
  locked ledger — no balance is stored or duplicated.

No inventory/accounting/numbering table is altered; Void reverses stock with the
already-allowed ``ADJUSTMENT_IN`` movement type and a reversing JV entry.
"""

from __future__ import annotations

import sqlite3

from zenith_business.core.clock import now_iso

# Additive nullable snapshot columns on the locked sales header.
_ALTERS: list[tuple[str, str]] = [
    ("sales", "ALTER TABLE sales ADD COLUMN walkin_name TEXT"),
    ("sales", "ALTER TABLE sales ADD COLUMN walkin_phone TEXT"),
    ("sales", "ALTER TABLE sales ADD COLUMN walkin_address TEXT"),
]

# Only ``parties.ledger`` is genuinely new — ``sales.void`` / ``purchases.void``
# already exist in the LOCKED baseline schema (granted to Administrator). This
# migration additionally extends those existing void grants to Manager/Accountant.
OWNER_FIX_PERMISSIONS: list[tuple[str, str]] = [
    ("parties.ledger", "parties"),
]

# Role -> permission grants (may reference pre-existing permission codes; the
# grant is idempotent via INSERT OR IGNORE so re-runs are safe).
_ROLE_GRANTS: dict[str, list[str]] = {
    "MANAGER": ["sales.void", "purchases.void", "parties.ledger"],
    "ACCOUNTANT": ["sales.void", "purchases.void", "parties.ledger"],
    "CASHIER": ["parties.ledger"],
    "SALESPERSON": ["parties.ledger"],
}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def migrate_owner_fixes(conn: sqlite3.Connection) -> None:
    """Migration 0006 — walk-in snapshot columns + void/ledger permissions."""
    # Idempotent ALTERs: only add a column that is not already present, so a
    # partially-migrated or re-run database upgrades safely.
    for table, statement in _ALTERS:
        column = statement.rsplit(" ADD COLUMN ", 1)[1].split()[0]
        if column not in _columns(conn, table):
            conn.execute(statement)

    conn.executemany(
        "INSERT OR IGNORE INTO permissions (code, category) VALUES (?, ?)",
        OWNER_FIX_PERMISSIONS)
    perm_ids = {c: pid for pid, c in conn.execute("SELECT id, code FROM permissions").fetchall()}
    role_ids = {c: rid for rid, c in conn.execute("SELECT id, code FROM roles").fetchall()}

    admin_id = role_ids.get("ADMINISTRATOR")
    if admin_id is not None:
        for code, _cat in OWNER_FIX_PERMISSIONS:
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
    _ = now_iso  # (kept for parity with sibling migrations; no timestamped rows here)
