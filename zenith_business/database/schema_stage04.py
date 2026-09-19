"""Stage 04 forward schema (migration 0004) — sales, purchases & returns.

Additive, non-breaking: the LOCKED Stage 01/02/03 schema is NOT edited. Stage 04
ADDS return tables, additive ``party_id`` links on the locked ``sales``/
``purchases`` headers (so the unified Stage 03 ``parties`` model is the preferred
business party without touching the locked ``customer_id``/``supplier_id`` FKs),
a supplier-reference column on purchases, new document sequences and permissions,
and indexes.

Status vocabulary: the locked ``sales``/``purchases`` CHECK allows
DRAFT/POSTED/VOID — Stage 04 treats **VOID as "Cancelled"** to stay compatible.
The new return tables use their own DRAFT/POSTED/CANCELLED CHECK.
"""

from __future__ import annotations

import sqlite3

from zenith_business.core.clock import now_iso

_STAGE04_TABLES: list[str] = [
    """
    CREATE TABLE sales_returns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_no TEXT NOT NULL UNIQUE,
        return_date TEXT NOT NULL,
        sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE RESTRICT,
        party_id INTEGER REFERENCES parties(id) ON DELETE RESTRICT,
        warehouse_id INTEGER REFERENCES warehouses(id) ON DELETE RESTRICT,
        currency_id INTEGER NOT NULL REFERENCES currencies(id) ON DELETE RESTRICT,
        exchange_rate TEXT NOT NULL DEFAULT '1.0000',
        subtotal TEXT NOT NULL DEFAULT '0.00',
        discount_total TEXT NOT NULL DEFAULT '0.00',
        grand_total TEXT NOT NULL DEFAULT '0.00',
        status TEXT NOT NULL DEFAULT 'POSTED' CHECK (status IN ('DRAFT','POSTED','CANCELLED')),
        reason TEXT,
        notes TEXT,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        posted_at TEXT,
        posted_by INTEGER REFERENCES users(id) ON DELETE SET NULL
    )""",
    """
    CREATE TABLE sales_return_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        return_id INTEGER NOT NULL REFERENCES sales_returns(id) ON DELETE CASCADE,
        line_no INTEGER NOT NULL,
        sale_line_id INTEGER NOT NULL REFERENCES sales_lines(id) ON DELETE RESTRICT,
        item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
        unit_id INTEGER NOT NULL REFERENCES units(id) ON DELETE RESTRICT,
        warehouse_id INTEGER REFERENCES warehouses(id) ON DELETE RESTRICT,
        quantity TEXT NOT NULL,
        unit_price TEXT NOT NULL,
        discount TEXT NOT NULL DEFAULT '0.00',
        line_total TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE purchase_returns (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_no TEXT NOT NULL UNIQUE,
        return_date TEXT NOT NULL,
        purchase_id INTEGER NOT NULL REFERENCES purchases(id) ON DELETE RESTRICT,
        party_id INTEGER REFERENCES parties(id) ON DELETE RESTRICT,
        warehouse_id INTEGER REFERENCES warehouses(id) ON DELETE RESTRICT,
        currency_id INTEGER NOT NULL REFERENCES currencies(id) ON DELETE RESTRICT,
        exchange_rate TEXT NOT NULL DEFAULT '1.0000',
        subtotal TEXT NOT NULL DEFAULT '0.00',
        discount_total TEXT NOT NULL DEFAULT '0.00',
        grand_total TEXT NOT NULL DEFAULT '0.00',
        status TEXT NOT NULL DEFAULT 'POSTED' CHECK (status IN ('DRAFT','POSTED','CANCELLED')),
        reason TEXT,
        notes TEXT,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        posted_at TEXT,
        posted_by INTEGER REFERENCES users(id) ON DELETE SET NULL
    )""",
    """
    CREATE TABLE purchase_return_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        return_id INTEGER NOT NULL REFERENCES purchase_returns(id) ON DELETE CASCADE,
        line_no INTEGER NOT NULL,
        purchase_line_id INTEGER NOT NULL REFERENCES purchase_lines(id) ON DELETE RESTRICT,
        item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
        unit_id INTEGER NOT NULL REFERENCES units(id) ON DELETE RESTRICT,
        warehouse_id INTEGER REFERENCES warehouses(id) ON DELETE RESTRICT,
        quantity TEXT NOT NULL,
        unit_price TEXT NOT NULL,
        discount TEXT NOT NULL DEFAULT '0.00',
        line_total TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
]

_STAGE04_ALTERS: list[str] = [
    "ALTER TABLE sales ADD COLUMN party_id INTEGER REFERENCES parties(id) ON DELETE RESTRICT",
    "ALTER TABLE purchases ADD COLUMN party_id INTEGER REFERENCES parties(id) ON DELETE RESTRICT",
    "ALTER TABLE purchases ADD COLUMN supplier_reference TEXT",
]

_STAGE04_INDEXES: list[str] = [
    "CREATE INDEX idx_sales_party ON sales(party_id)",
    "CREATE INDEX idx_purchases_party ON purchases(party_id)",
    "CREATE INDEX idx_sret_sale ON sales_returns(sale_id)",
    "CREATE INDEX idx_sret_party ON sales_returns(party_id)",
    "CREATE INDEX idx_sret_date ON sales_returns(return_date)",
    "CREATE INDEX idx_sretl_saleline ON sales_return_lines(sale_line_id)",
    "CREATE INDEX idx_pret_purchase ON purchase_returns(purchase_id)",
    "CREATE INDEX idx_pret_party ON purchase_returns(party_id)",
    "CREATE INDEX idx_pret_date ON purchase_returns(return_date)",
    "CREATE INDEX idx_pretl_purchaseline ON purchase_return_lines(purchase_line_id)",
]

_STAGE04_SEQUENCES: list[tuple[str, str]] = [
    ("SRET", "SRET-"), ("PRET", "PRET-"),
]

STAGE04_PERMISSIONS: list[tuple[str, str]] = [
    ("sales.return", "sales"), ("sales.print", "sales"),
    ("purchases.return", "purchases"), ("purchases.print", "purchases"),
]

_STAGE04_ROLE_GRANTS: dict[str, list[str]] = {
    "MANAGER": ["sales.return", "sales.print", "purchases.return", "purchases.print"],
    "CASHIER": ["sales.print"],
    "SALESPERSON": ["sales.print"],
    "ACCOUNTANT": ["sales.print", "purchases.print"],
}


def migrate_stage04(conn: sqlite3.Connection) -> None:
    """Migration 0004 — sales/purchase returns, party links, sequences, permissions."""
    ts = now_iso()
    for statement in _STAGE04_TABLES:
        conn.execute(statement)
    for statement in _STAGE04_ALTERS:
        conn.execute(statement)
    for statement in _STAGE04_INDEXES:
        conn.execute(statement)
    for doc_type, prefix in _STAGE04_SEQUENCES:
        conn.execute(
            "INSERT OR IGNORE INTO document_sequences (doc_type, prefix, next_number, padding,"
            " updated_at) VALUES (?, ?, 1, 6, ?)", (doc_type, prefix, ts))
    # permissions + grants (Administrator gets all)
    conn.executemany(
        "INSERT OR IGNORE INTO permissions (code, category) VALUES (?, ?)",
        STAGE04_PERMISSIONS)
    perm_ids = {c: pid for pid, c in conn.execute("SELECT id, code FROM permissions").fetchall()}
    role_ids = {c: rid for rid, c in conn.execute("SELECT id, code FROM roles").fetchall()}
    admin_id = role_ids.get("ADMINISTRATOR")
    if admin_id is not None:
        for code, _cat in STAGE04_PERMISSIONS:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (admin_id, perm_ids[code]))
    for role_code, perms in _STAGE04_ROLE_GRANTS.items():
        rid = role_ids.get(role_code)
        if rid is None:
            continue
        for code in perms:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (rid, perm_ids[code]))
