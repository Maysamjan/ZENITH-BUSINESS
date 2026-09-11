"""Stage 05 forward schema (migration 0005) — receipts, payments, expenses, funds.

Additive, non-breaking: the LOCKED Stage 01–04 schema is NOT edited. Stage 05
builds the real money-movement layer on the money tables that Stage 02 already
created (``receipts``, ``payments``, ``expenses``, ``expense_categories``) by
adding, forward-compatibly:

* an ``is_fund`` flag on ``accounts`` — the minimum foundation for choosing where
  money comes from / goes to (Cash / Bank / Petty Cash / other funds), without a
  separate treasury module;
* the unified Stage 03 ``parties`` link + ``payment_method`` + posting stamps on
  ``receipts`` / ``payments`` (mirrors the Stage 04 additive-party approach, the
  locked ``customer_id`` / ``supplier_id`` FKs untouched);
* ``payment_method`` + posting stamps on ``expenses`` and an ``account_id``
  (expense account) on ``expense_categories`` so each expense posts to a real
  expense account — categories stay master data, never hard-coded in the UI;
* seeded funds + a standard set of expense accounts and categories;
* RCP / PAY / EXP document sequences, indexes, and RBAC permissions + grants.
"""

from __future__ import annotations

import sqlite3

from zenith_business.core.clock import now_iso

_STAGE05_ALTERS: list[str] = [
    "ALTER TABLE accounts ADD COLUMN is_fund INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE receipts ADD COLUMN party_id INTEGER REFERENCES parties(id) ON DELETE RESTRICT",
    "ALTER TABLE receipts ADD COLUMN payment_method TEXT",
    "ALTER TABLE receipts ADD COLUMN posted_at TEXT",
    "ALTER TABLE receipts ADD COLUMN posted_by INTEGER REFERENCES users(id) ON DELETE SET NULL",
    "ALTER TABLE payments ADD COLUMN party_id INTEGER REFERENCES parties(id) ON DELETE RESTRICT",
    "ALTER TABLE payments ADD COLUMN payment_method TEXT",
    "ALTER TABLE payments ADD COLUMN posted_at TEXT",
    "ALTER TABLE payments ADD COLUMN posted_by INTEGER REFERENCES users(id) ON DELETE SET NULL",
    "ALTER TABLE expenses ADD COLUMN payment_method TEXT",
    "ALTER TABLE expenses ADD COLUMN notes TEXT",
    "ALTER TABLE expenses ADD COLUMN posted_at TEXT",
    "ALTER TABLE expenses ADD COLUMN posted_by INTEGER REFERENCES users(id) ON DELETE SET NULL",
    "ALTER TABLE expense_categories ADD COLUMN account_id INTEGER"
    " REFERENCES accounts(id) ON DELETE RESTRICT",
]

_STAGE05_INDEXES: list[str] = [
    "CREATE INDEX idx_receipts_party ON receipts(party_id)",
    "CREATE INDEX idx_receipts_date ON receipts(receipt_date)",
    "CREATE INDEX idx_receipts_account ON receipts(account_id)",
    "CREATE INDEX idx_payments_party ON payments(party_id)",
    "CREATE INDEX idx_payments_date ON payments(payment_date)",
    "CREATE INDEX idx_payments_account ON payments(account_id)",
    "CREATE INDEX idx_expenses_date ON expenses(expense_date)",
    "CREATE INDEX idx_expenses_account ON expenses(account_id)",
    "CREATE INDEX idx_expenses_category ON expenses(expense_category_id)",
    "CREATE INDEX idx_accounts_fund ON accounts(is_fund)",
]

_STAGE05_SEQUENCES: list[tuple[str, str]] = [
    ("RCP", "RCP-"), ("PAY", "PAY-"), ("EXP", "EXP-"),
]

# New fund + expense accounts (code, name, type). Existing 1000 Cash / 1010 Bank
# are simply flagged as funds below.
_STAGE05_ACCOUNTS: list[tuple[str, str, str, int]] = [
    ("1020", "Petty Cash", "ASSET", 1),
    ("6100", "Rent", "EXPENSE", 0),
    ("6200", "Utilities", "EXPENSE", 0),
    ("6300", "Salaries & Wages", "EXPENSE", 0),
    ("6400", "Transport", "EXPENSE", 0),
    ("6500", "Office Supplies", "EXPENSE", 0),
    ("6600", "Maintenance", "EXPENSE", 0),
    ("6900", "Other Expenses", "EXPENSE", 0),
]

# Default expense categories (code, name, expense-account code). Master data —
# the owner can add/rename/deactivate; the UI never hard-codes them.
_STAGE05_EXPENSE_CATEGORIES: list[tuple[str, str, str]] = [
    ("RENT", "Rent", "6100"),
    ("ELEC", "Electricity", "6200"),
    ("NET", "Internet", "6200"),
    ("TRANS", "Transport", "6400"),
    ("SAL", "Salaries", "6300"),
    ("OFFICE", "Office Expenses", "6500"),
    ("MAINT", "Maintenance", "6600"),
    ("OTHER", "Other Operating Expenses", "6900"),
]

STAGE05_PERMISSIONS: list[tuple[str, str]] = [
    ("receipts.view", "receipts"), ("receipts.create", "receipts"), ("receipts.print", "receipts"),
    ("payments.view", "payments"), ("payments.create", "payments"), ("payments.print", "payments"),
    ("expenses.view", "expenses"), ("expenses.create", "expenses"), ("expenses.print", "expenses"),
    ("funds.view", "funds"),
]

_ALL_S5 = [c for c, _ in STAGE05_PERMISSIONS]
_STAGE05_ROLE_GRANTS: dict[str, list[str]] = {
    "MANAGER": _ALL_S5,
    "ACCOUNTANT": _ALL_S5,
    "CASHIER": ["receipts.view", "receipts.create", "receipts.print",
                "payments.view", "payments.create", "payments.print",
                "expenses.view", "expenses.create", "expenses.print", "funds.view"],
    "SALESPERSON": ["receipts.view", "funds.view"],
}


def migrate_stage05(conn: sqlite3.Connection) -> None:
    """Migration 0005 — money-movement layer (receipts, payments, expenses, funds)."""
    ts = now_iso()
    for statement in _STAGE05_ALTERS:
        conn.execute(statement)
    for statement in _STAGE05_INDEXES:
        conn.execute(statement)

    # Flag the existing seeded Cash + Bank accounts as selectable funds.
    conn.execute("UPDATE accounts SET is_fund = 1 WHERE code IN ('1000', '1010')")
    # New fund + expense accounts.
    for code, name, acct_type, is_fund in _STAGE05_ACCOUNTS:
        conn.execute(
            "INSERT OR IGNORE INTO accounts (code, name, type, is_system, is_active, is_fund,"
            " created_at, updated_at) VALUES (?, ?, ?, 1, 1, ?, ?, ?)",
            (code, name, acct_type, is_fund, ts, ts))
    # Default expense categories mapped to their expense accounts.
    acct_id = {c: i for i, c in conn.execute("SELECT id, code FROM accounts").fetchall()}
    for code, name, acct_code in _STAGE05_EXPENSE_CATEGORIES:
        conn.execute(
            "INSERT OR IGNORE INTO expense_categories (code, name, is_active, account_id,"
            " created_at, updated_at) VALUES (?, ?, 1, ?, ?, ?)",
            (code, name, acct_id.get(acct_code), ts, ts))

    for doc_type, prefix in _STAGE05_SEQUENCES:
        conn.execute(
            "INSERT OR IGNORE INTO document_sequences (doc_type, prefix, next_number, padding,"
            " updated_at) VALUES (?, ?, 1, 6, ?)", (doc_type, prefix, ts))

    # Permissions + grants (Administrator gets all).
    conn.executemany(
        "INSERT OR IGNORE INTO permissions (code, category) VALUES (?, ?)", STAGE05_PERMISSIONS)
    perm_ids = {c: pid for pid, c in conn.execute("SELECT id, code FROM permissions").fetchall()}
    role_ids = {c: rid for rid, c in conn.execute("SELECT id, code FROM roles").fetchall()}
    admin_id = role_ids.get("ADMINISTRATOR")
    if admin_id is not None:
        for code, _cat in STAGE05_PERMISSIONS:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (admin_id, perm_ids[code]))
    for role_code, perms in _STAGE05_ROLE_GRANTS.items():
        rid = role_ids.get(role_code)
        if rid is None:
            continue
        for code in perms:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (rid, perm_ids[code]))
