"""Forward migration 0011 — Stage 09 accounting reports & COGS posting (additive).

Stage 09 reads the ledger that already exists; it stores almost nothing new. Two
things are genuinely needed:

* **Exactly-once COGS posting.** Stage 08 knows what every sale cost, but nothing
  charged that cost to the accounts, so Inventory only ever grew and Cost of
  Goods Sold stayed at zero. Stage 09 posts ``Dr COGS / Cr Inventory`` from the
  costed movement — and "exactly once" is enforced by the **database**, not by
  hopeful code: a COGS entry carries ``source_type='COGS'`` and
  ``source_id=<inventory_movements.id>``, and a partial unique index makes a
  second posting for the same movement impossible. That also keeps the §8
  traceability rule: ledger → movement → document, both ways.

* **An `accounting.reports` permission**, granted to Administrator, Manager and
  Accountant. Financial statements expose the whole business position, so they
  are gated in the service layer like every other capability (§17).

Reporting indexes are added for the account/date slices every statement makes.
Nothing is renamed, dropped or back-filled — existing COGS-less history is
posted by the Stage 09 service on demand, dated by the movement it came from, so
a database upgraded today still reports the right figures for last month.
"""

from __future__ import annotations

import sqlite3

STAGE09_PERMISSIONS: list[tuple[str, str]] = [
    ("accounting.reports", "accounting"),
]

_ROLE_GRANTS: dict[str, list[str]] = {
    "MANAGER": ["accounting.reports"],
    "ACCOUNTANT": ["accounting.reports"],
}


def migrate_stage09(conn: sqlite3.Connection) -> None:
    """Migration 0011 — COGS uniqueness, reporting indexes, report permission."""
    # One COGS entry per costed movement. A UNIQUE index is the guarantee; the
    # service's "already posted?" check is only an optimisation on top of it.
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_fin_cogs_source"
        " ON financial_entries(source_type, source_id)"
        " WHERE source_type = 'COGS'")
    # Every statement slices the ledger by account and by date.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_fin_lines_account"
        " ON financial_entry_lines(account_id)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_fin_entries_date"
        " ON financial_entries(entry_date)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_fin_lines_party"
        " ON financial_entry_lines(party_type, party_id)")

    conn.executemany(
        "INSERT OR IGNORE INTO permissions (code, category) VALUES (?, ?)",
        STAGE09_PERMISSIONS)
    perm_ids = {c: pid for pid, c in conn.execute(
        "SELECT id, code FROM permissions").fetchall()}
    role_ids = {c: rid for rid, c in conn.execute(
        "SELECT id, code FROM roles").fetchall()}

    admin_id = role_ids.get("ADMINISTRATOR")
    if admin_id is not None:
        for code, _cat in STAGE09_PERMISSIONS:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id)"
                " VALUES (?, ?)", (admin_id, perm_ids[code]))
    for role_code, perms in _ROLE_GRANTS.items():
        rid = role_ids.get(role_code)
        if rid is None:
            continue
        for code in perms:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id)"
                " VALUES (?, ?)", (rid, perm_ids[code]))
