"""Stage 03 forward schema (migration 0003) — master data & business setup.

Additive, non-breaking (owner-approved Option A): the LOCKED Stage 02 schema
(migration 0001) is NOT edited. Stage 03 ADDS a unified ``parties`` table, a
``financial_years`` table, a few production columns on existing tables, new
permission codes (granted to the Administrator so no admin loses access), and
indexes for the new search paths.

The unified ``parties`` table satisfies §15 (one Person may be both customer and
supplier, without duplicate records). The locked ``customers``/``suppliers``
tables and their FKs are left intact and unused by the new Person layer; a future
stage will additively reference ``parties`` from Sales/Purchases.
"""

from __future__ import annotations

import sqlite3


# ---------------------------------------------------------------- DDL -------

_STAGE03_TABLES: list[str] = [
    # Unified party (person/company) — customer and/or supplier (§15).
    """
    CREATE TABLE parties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        party_code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        company_name TEXT,
        is_customer INTEGER NOT NULL DEFAULT 0 CHECK (is_customer IN (0,1)),
        is_supplier INTEGER NOT NULL DEFAULT 0 CHECK (is_supplier IN (0,1)),
        phone TEXT,
        secondary_phone TEXT,
        email TEXT,
        address TEXT,
        city TEXT,
        tax_id TEXT,
        credit_limit TEXT NOT NULL DEFAULT '0.00',
        opening_balance TEXT NOT NULL DEFAULT '0.00',
        notes TEXT,
        is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        CHECK (is_customer = 1 OR is_supplier = 1)
    )""",
    # Financial years (§6). Dates are ISO YYYY-MM-DD; lexicographic order == chronological.
    """
    CREATE TABLE financial_years (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED')),
        is_active INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0,1)),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        closed_at TEXT,
        closed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        CHECK (start_date < end_date)
    )""",
]

# Additive columns on existing tables (SQLite ADD COLUMN; NULL/constant defaults).
_STAGE03_ALTERS: list[str] = [
    "ALTER TABLE companies ADD COLUMN display_name TEXT",
    "ALTER TABLE companies ADD COLUMN registration_number TEXT",
    "ALTER TABLE companies ADD COLUMN default_warehouse_id INTEGER"
    " REFERENCES warehouses(id) ON DELETE SET NULL",
    "ALTER TABLE companies ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1"
    " CHECK (is_active IN (0,1))",
    "ALTER TABLE items ADD COLUMN alternate_name TEXT",
    "ALTER TABLE units ADD COLUMN decimal_allowed INTEGER NOT NULL DEFAULT 1"
    " CHECK (decimal_allowed IN (0,1))",
    "ALTER TABLE warehouses ADD COLUMN notes TEXT",
]

_STAGE03_INDEXES: list[str] = [
    "CREATE INDEX idx_parties_name ON parties(name)",
    "CREATE INDEX idx_parties_company ON parties(company_name)",
    "CREATE INDEX idx_parties_phone ON parties(phone)",
    "CREATE INDEX idx_parties_roles ON parties(is_customer, is_supplier)",
    "CREATE INDEX idx_items_altname ON items(alternate_name)",
    # At most one active financial year (enforced at the DB level, §6).
    "CREATE UNIQUE INDEX uq_financial_year_active ON financial_years(is_active)"
    " WHERE is_active = 1",
]

# ---------------------------------------------------------------- seed ------

# New permission codes (grouped by module). Stable — never rename (§25).
STAGE03_PERMISSIONS: list[tuple[str, str]] = [
    ("company.manage", "settings"),
    ("financialyear.view", "settings"), ("financialyear.manage", "settings"),
    ("warehouses.view", "warehouses"), ("warehouses.manage", "warehouses"),
    ("units.view", "units"), ("units.manage", "units"),
    ("categories.view", "categories"), ("categories.manage", "categories"),
    ("persons.view", "persons"), ("persons.create", "persons"), ("persons.edit", "persons"),
    ("items.create", "items"), ("items.edit", "items"),
]

# Additional grants for non-admin starter roles (Administrator gets ALL).
_STAGE03_ROLE_GRANTS: dict[str, list[str]] = {
    "MANAGER": [
        "company.manage", "financialyear.view", "financialyear.manage",
        "warehouses.view", "warehouses.manage", "units.view", "units.manage",
        "categories.view", "categories.manage", "persons.view", "persons.create",
        "persons.edit", "items.create", "items.edit",
    ],
    "SALESPERSON": ["persons.view", "persons.create", "warehouses.view", "units.view",
                    "categories.view"],
    "CASHIER": ["persons.view", "warehouses.view"],
    "ACCOUNTANT": ["persons.view", "financialyear.view", "warehouses.view"],
    "WAREHOUSE": ["warehouses.view", "warehouses.manage", "units.view", "categories.view",
                  "items.create", "items.edit"],
    "VIEWER": ["persons.view", "warehouses.view", "units.view", "categories.view",
               "financialyear.view"],
}


def _seed_permissions(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT OR IGNORE INTO permissions (code, category) VALUES (?, ?)",
        STAGE03_PERMISSIONS,
    )
    perm_ids = {c: pid for pid, c in conn.execute("SELECT id, code FROM permissions").fetchall()}
    role_ids = {c: rid for rid, c in conn.execute("SELECT id, code FROM roles").fetchall()}
    # Administrator → every (new) permission.
    admin_id = role_ids.get("ADMINISTRATOR")
    if admin_id is not None:
        for code, _cat in STAGE03_PERMISSIONS:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (admin_id, perm_ids[code]))
    for role_code, perms in _STAGE03_ROLE_GRANTS.items():
        rid = role_ids.get(role_code)
        if rid is None:
            continue
        for code in perms:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (rid, perm_ids[code]))


def migrate_stage03(conn: sqlite3.Connection) -> None:
    """Migration 0003 — add Stage 03 master-data tables, columns, indexes, perms."""
    for statement in _STAGE03_TABLES:
        conn.execute(statement)
    for statement in _STAGE03_ALTERS:
        conn.execute(statement)
    for statement in _STAGE03_INDEXES:
        conn.execute(statement)
    _seed_permissions(conn)
