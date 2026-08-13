"""Production schema (v1) DDL and baseline seed (Stage 02 §3, §6, §40).

All money/quantity/rate columns are TEXT holding canonical Decimal strings
(§24); all timestamps are TEXT ISO-8601 UTC (§35). Foreign keys use deliberate
ON DELETE behavior — RESTRICT protects business/financial history (§38); CASCADE
is used only for pure mapping/child rows that never carry standalone history.

`create_schema` builds every table + index. `seed_baseline` inserts only safe,
production-appropriate system data (permissions, roles, role→permission grants,
currencies, units, a minimal chart of accounts, document sequences). It inserts
NO fake customers/items/sales (§39). Demo data lives in a separate dev-only
seeder.
"""

from __future__ import annotations

import sqlite3

from zenith_business.core.clock import now_iso

# ---------------------------------------------------------------- schema ----

_TABLES: list[str] = [
    # currencies first (referenced by companies/items/sales/...)
    """
    CREATE TABLE currencies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        symbol TEXT,
        decimal_places INTEGER NOT NULL DEFAULT 2,
        is_base INTEGER NOT NULL DEFAULT 0 CHECK (is_base IN (0,1)),
        is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        username_norm TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        full_name TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        preferred_language TEXT NOT NULL DEFAULT 'fa_AF',
        is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
        is_locked INTEGER NOT NULL DEFAULT 0 CHECK (is_locked IN (0,1)),
        failed_login_attempts INTEGER NOT NULL DEFAULT 0,
        last_failed_login_at TEXT,
        locked_until TEXT,
        last_login_at TEXT,
        password_changed_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL
    )""",
    """
    CREATE TABLE roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        description TEXT,
        is_system INTEGER NOT NULL DEFAULT 0 CHECK (is_system IN (0,1)),
        is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE permissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        category TEXT,
        description TEXT
    )""",
    """
    CREATE TABLE user_roles (
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
        PRIMARY KEY (user_id, role_id)
    )""",
    """
    CREATE TABLE role_permissions (
        role_id INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
        permission_id INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
        PRIMARY KEY (role_id, permission_id)
    )""",
    """
    CREATE TABLE exchange_rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        currency_id INTEGER NOT NULL REFERENCES currencies(id) ON DELETE RESTRICT,
        rate_to_base TEXT NOT NULL,
        effective_at TEXT NOT NULL,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE units (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        name_en TEXT NOT NULL,
        name_fa TEXT NOT NULL,
        symbol TEXT,
        is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER REFERENCES categories(id) ON DELETE RESTRICT,
        code TEXT NOT NULL UNIQUE,
        name_en TEXT NOT NULL,
        name_fa TEXT NOT NULL,
        description TEXT,
        is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        CHECK (parent_id IS NULL OR parent_id <> id)
    )""",
    """
    CREATE TABLE warehouses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        address TEXT,
        phone TEXT,
        manager_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0,1)),
        is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        legal_name TEXT NOT NULL,
        trade_name TEXT,
        logo_path TEXT,
        address TEXT,
        city TEXT,
        country TEXT,
        phone TEXT,
        secondary_phone TEXT,
        email TEXT,
        website TEXT,
        tax_id TEXT,
        default_currency_id INTEGER REFERENCES currencies(id) ON DELETE SET NULL,
        default_language TEXT NOT NULL DEFAULT 'fa_AF',
        invoice_footer TEXT,
        invoice_terms TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_code TEXT NOT NULL UNIQUE,
        barcode TEXT,
        name TEXT NOT NULL,
        name_en TEXT,
        name_fa TEXT,
        category_id INTEGER REFERENCES categories(id) ON DELETE RESTRICT,
        base_unit_id INTEGER NOT NULL REFERENCES units(id) ON DELETE RESTRICT,
        purchase_price TEXT NOT NULL DEFAULT '0.00',
        default_sale_price TEXT NOT NULL DEFAULT '0.00',
        min_sale_price TEXT,
        reorder_level TEXT NOT NULL DEFAULT '0.000',
        track_inventory INTEGER NOT NULL DEFAULT 1 CHECK (track_inventory IN (0,1)),
        is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        company_name TEXT,
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
        updated_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        company_name TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        city TEXT,
        tax_id TEXT,
        opening_balance TEXT NOT NULL DEFAULT '0.00',
        notes TEXT,
        is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        type TEXT NOT NULL CHECK (type IN ('ASSET','LIABILITY','EQUITY','INCOME','EXPENSE')),
        is_system INTEGER NOT NULL DEFAULT 0 CHECK (is_system IN (0,1)),
        is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE financial_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_no TEXT NOT NULL UNIQUE,
        entry_date TEXT NOT NULL,
        source_type TEXT NOT NULL,
        source_id INTEGER,
        description TEXT,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE financial_entry_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entry_id INTEGER NOT NULL REFERENCES financial_entries(id) ON DELETE CASCADE,
        account_id INTEGER REFERENCES accounts(id) ON DELETE RESTRICT,
        party_type TEXT CHECK (party_type IN ('CUSTOMER','SUPPLIER') OR party_type IS NULL),
        party_id INTEGER,
        debit TEXT NOT NULL DEFAULT '0.00',
        credit TEXT NOT NULL DEFAULT '0.00',
        currency_id INTEGER REFERENCES currencies(id) ON DELETE RESTRICT,
        memo TEXT
    )""",
    """
    CREATE TABLE sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_no TEXT NOT NULL UNIQUE,
        sale_date TEXT NOT NULL,
        customer_id INTEGER REFERENCES customers(id) ON DELETE RESTRICT,
        warehouse_id INTEGER REFERENCES warehouses(id) ON DELETE RESTRICT,
        salesperson_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        currency_id INTEGER NOT NULL REFERENCES currencies(id) ON DELETE RESTRICT,
        exchange_rate TEXT NOT NULL DEFAULT '1.0000',
        subtotal TEXT NOT NULL DEFAULT '0.00',
        discount_total TEXT NOT NULL DEFAULT '0.00',
        grand_total TEXT NOT NULL DEFAULT '0.00',
        amount_paid TEXT NOT NULL DEFAULT '0.00',
        remaining_amount TEXT NOT NULL DEFAULT '0.00',
        status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','POSTED','VOID')),
        notes TEXT,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        posted_at TEXT,
        posted_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        voided_at TEXT,
        voided_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        void_reason TEXT
    )""",
    """
    CREATE TABLE sales_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
        line_no INTEGER NOT NULL,
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
    CREATE TABLE purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_no TEXT NOT NULL UNIQUE,
        purchase_date TEXT NOT NULL,
        supplier_id INTEGER REFERENCES suppliers(id) ON DELETE RESTRICT,
        warehouse_id INTEGER REFERENCES warehouses(id) ON DELETE RESTRICT,
        currency_id INTEGER NOT NULL REFERENCES currencies(id) ON DELETE RESTRICT,
        exchange_rate TEXT NOT NULL DEFAULT '1.0000',
        subtotal TEXT NOT NULL DEFAULT '0.00',
        discount_total TEXT NOT NULL DEFAULT '0.00',
        grand_total TEXT NOT NULL DEFAULT '0.00',
        amount_paid TEXT NOT NULL DEFAULT '0.00',
        remaining_amount TEXT NOT NULL DEFAULT '0.00',
        status TEXT NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','POSTED','VOID')),
        notes TEXT,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        posted_at TEXT,
        posted_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        voided_at TEXT,
        voided_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        void_reason TEXT
    )""",
    """
    CREATE TABLE purchase_lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        purchase_id INTEGER NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
        line_no INTEGER NOT NULL,
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
    CREATE TABLE inventory_movements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id INTEGER NOT NULL REFERENCES items(id) ON DELETE RESTRICT,
        warehouse_id INTEGER NOT NULL REFERENCES warehouses(id) ON DELETE RESTRICT,
        movement_type TEXT NOT NULL CHECK (movement_type IN
            ('OPENING','PURCHASE','SALE','SALE_RETURN','PURCHASE_RETURN',
             'ADJUSTMENT_IN','ADJUSTMENT_OUT','TRANSFER_IN','TRANSFER_OUT')),
        quantity TEXT NOT NULL,
        unit_id INTEGER REFERENCES units(id) ON DELETE RESTRICT,
        reference_type TEXT,
        reference_id INTEGER,
        reference_line_id INTEGER,
        movement_date TEXT NOT NULL,
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_no TEXT NOT NULL UNIQUE,
        receipt_date TEXT NOT NULL,
        customer_id INTEGER REFERENCES customers(id) ON DELETE RESTRICT,
        account_id INTEGER REFERENCES accounts(id) ON DELETE RESTRICT,
        currency_id INTEGER NOT NULL REFERENCES currencies(id) ON DELETE RESTRICT,
        exchange_rate TEXT NOT NULL DEFAULT '1.0000',
        amount TEXT NOT NULL,
        reference TEXT,
        notes TEXT,
        status TEXT NOT NULL DEFAULT 'POSTED' CHECK (status IN ('DRAFT','POSTED','VOID')),
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_no TEXT NOT NULL UNIQUE,
        payment_date TEXT NOT NULL,
        supplier_id INTEGER REFERENCES suppliers(id) ON DELETE RESTRICT,
        account_id INTEGER REFERENCES accounts(id) ON DELETE RESTRICT,
        currency_id INTEGER NOT NULL REFERENCES currencies(id) ON DELETE RESTRICT,
        exchange_rate TEXT NOT NULL DEFAULT '1.0000',
        amount TEXT NOT NULL,
        reference TEXT,
        notes TEXT,
        status TEXT NOT NULL DEFAULT 'POSTED' CHECK (status IN ('DRAFT','POSTED','VOID')),
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE expense_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_no TEXT NOT NULL UNIQUE,
        expense_date TEXT NOT NULL,
        expense_category_id INTEGER REFERENCES expense_categories(id) ON DELETE RESTRICT,
        account_id INTEGER REFERENCES accounts(id) ON DELETE RESTRICT,
        amount TEXT NOT NULL,
        currency_id INTEGER NOT NULL REFERENCES currencies(id) ON DELETE RESTRICT,
        exchange_rate TEXT NOT NULL DEFAULT '1.0000',
        payee TEXT,
        description TEXT,
        reference TEXT,
        status TEXT NOT NULL DEFAULT 'POSTED' CHECK (status IN ('DRAFT','POSTED','VOID')),
        created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
        created_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE document_sequences (
        doc_type TEXT PRIMARY KEY,
        prefix TEXT NOT NULL,
        next_number INTEGER NOT NULL DEFAULT 1,
        padding INTEGER NOT NULL DEFAULT 6,
        updated_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        username TEXT,
        action TEXT NOT NULL,
        entity_type TEXT,
        entity_id INTEGER,
        document_no TEXT,
        details TEXT,
        created_at TEXT NOT NULL
    )""",
    """
    CREATE TABLE app_settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT NOT NULL
    )""",
]

_INDEXES: list[str] = [
    "CREATE INDEX idx_items_barcode ON items(barcode)",
    "CREATE INDEX idx_items_name ON items(name)",
    "CREATE INDEX idx_customers_name ON customers(name)",
    "CREATE INDEX idx_customers_phone ON customers(phone)",
    "CREATE INDEX idx_suppliers_name ON suppliers(name)",
    "CREATE INDEX idx_sales_date ON sales(sale_date)",
    "CREATE INDEX idx_sales_customer ON sales(customer_id)",
    "CREATE INDEX idx_purchases_date ON purchases(purchase_date)",
    "CREATE INDEX idx_purchases_supplier ON purchases(supplier_id)",
    "CREATE INDEX idx_inv_item ON inventory_movements(item_id)",
    "CREATE INDEX idx_inv_wh ON inventory_movements(warehouse_id)",
    "CREATE INDEX idx_inv_date ON inventory_movements(movement_date)",
    "CREATE INDEX idx_audit_user ON audit_log(user_id)",
    "CREATE INDEX idx_audit_created ON audit_log(created_at)",
    "CREATE INDEX idx_exrate_currency ON exchange_rates(currency_id, effective_at)",
    "CREATE INDEX idx_fel_entry ON financial_entry_lines(entry_id)",
    "CREATE INDEX idx_fel_party ON financial_entry_lines(party_type, party_id)",
]


def create_schema(conn: sqlite3.Connection) -> None:
    """Create every production table + index (migration 0001)."""
    for statement in _TABLES:
        conn.execute(statement)
    for statement in _INDEXES:
        conn.execute(statement)


# ---------------------------------------------------------------- seed ------

# Language-neutral permission codes (Stage 02 §13). Stable — never rename.
PERMISSIONS: list[tuple[str, str]] = [
    ("sales.view", "sales"), ("sales.create", "sales"), ("sales.edit", "sales"),
    ("sales.post", "sales"), ("sales.void", "sales"),
    ("purchases.view", "purchases"), ("purchases.create", "purchases"),
    ("purchases.edit", "purchases"), ("purchases.post", "purchases"), ("purchases.void", "purchases"),
    ("inventory.view", "inventory"), ("inventory.adjust", "inventory"), ("inventory.transfer", "inventory"),
    ("accounts.view", "accounts"), ("accounts.receive", "accounts"), ("accounts.pay", "accounts"),
    ("customers.view", "customers"), ("customers.manage", "customers"),
    ("suppliers.view", "suppliers"), ("suppliers.manage", "suppliers"),
    ("items.view", "items"), ("items.manage", "items"),
    ("items.view_cost", "items"), ("items.view_profit", "items"),
    ("reports.sales", "reports"), ("reports.inventory", "reports"),
    ("reports.accounts", "reports"), ("reports.profit", "reports"),
    ("users.view", "users"), ("users.manage", "users"),
    ("roles.manage", "roles"), ("settings.manage", "settings"),
    ("backup.create", "backup"), ("backup.restore", "backup"),
]

# Starter roles (§12). Behavior is driven by permissions, never role names.
ROLES: list[tuple[str, str, int]] = [  # (code, name, is_system)
    ("ADMINISTRATOR", "Administrator", 1),
    ("MANAGER", "Manager", 0),
    ("CASHIER", "Cashier", 0),
    ("SALESPERSON", "Salesperson", 0),
    ("ACCOUNTANT", "Accountant", 0),
    ("WAREHOUSE", "Warehouse Staff", 0),
    ("VIEWER", "Viewer", 0),
]

# Role → permission grants. Administrator gets ALL (handled specially).
_ROLE_GRANTS: dict[str, list[str]] = {
    "MANAGER": [
        "sales.view", "sales.create", "sales.edit", "sales.post", "sales.void",
        "purchases.view", "purchases.create", "purchases.edit", "purchases.post",
        "inventory.view", "inventory.adjust", "inventory.transfer",
        "accounts.view", "accounts.receive", "accounts.pay",
        "customers.view", "customers.manage", "suppliers.view", "suppliers.manage",
        "items.view", "items.manage", "items.view_cost", "items.view_profit",
        "reports.sales", "reports.inventory", "reports.accounts", "reports.profit",
        "users.view", "backup.create",
    ],
    "CASHIER": [
        "sales.view", "sales.create", "sales.post",
        "accounts.receive", "customers.view", "items.view", "reports.sales",
    ],
    "SALESPERSON": [
        "sales.view", "sales.create", "customers.view", "customers.manage",
        "items.view", "reports.sales",
    ],
    "ACCOUNTANT": [
        "accounts.view", "accounts.receive", "accounts.pay",
        "purchases.view", "reports.sales", "reports.accounts", "reports.profit",
        "customers.view", "suppliers.view", "items.view", "items.view_cost",
    ],
    "WAREHOUSE": [
        "inventory.view", "inventory.adjust", "inventory.transfer",
        "items.view", "reports.inventory",
    ],
    "VIEWER": [
        "sales.view", "purchases.view", "inventory.view", "accounts.view",
        "customers.view", "suppliers.view", "items.view",
        "reports.sales", "reports.inventory", "reports.accounts",
    ],
}

CURRENCIES: list[tuple[str, str, str, int, int]] = [  # code,name,symbol,decimals,is_base
    ("AFN", "Afghani", "؋", 2, 1),
    ("USD", "US Dollar", "$", 2, 0),
    ("EUR", "Euro", "€", 2, 0),
    ("PKR", "Pakistani Rupee", "₨", 2, 0),
]

UNITS: list[tuple[str, str, str, str]] = [  # code,en,fa,symbol
    ("PCS", "Piece", "عدد", "pcs"), ("KG", "Kilogram", "کیلوگرام", "kg"),
    ("GR", "Gram", "گرام", "g"), ("LTR", "Liter", "لیتر", "L"),
    ("CTN", "Carton", "کارتن", "ctn"), ("BOX", "Box", "بکس", "box"),
    ("BAG", "Bag", "بوجی", "bag"), ("MTR", "Meter", "متر", "m"),
]

ACCOUNTS: list[tuple[str, str, str]] = [  # code,name,type
    ("1000", "Cash", "ASSET"), ("1010", "Bank", "ASSET"),
    ("1100", "Accounts Receivable", "ASSET"), ("1200", "Inventory", "ASSET"),
    ("2000", "Accounts Payable", "LIABILITY"), ("3000", "Owner Equity", "EQUITY"),
    ("4000", "Sales Revenue", "INCOME"), ("5000", "Cost of Goods Sold", "EXPENSE"),
    ("5100", "Purchases", "EXPENSE"), ("6000", "Operating Expenses", "EXPENSE"),
]

SEQUENCES: list[tuple[str, str]] = [
    ("SALE", "SALE-"), ("PUR", "PUR-"), ("REC", "REC-"),
    ("PAY", "PAY-"), ("EXP", "EXP-"), ("JV", "JV-"),
]


def seed_baseline(conn: sqlite3.Connection) -> None:
    """Insert safe, production-appropriate system data (migration 0002)."""
    ts = now_iso()

    conn.executemany(
        "INSERT OR IGNORE INTO permissions (code, category) VALUES (?, ?)",
        PERMISSIONS,
    )
    for code, name, is_system in ROLES:
        conn.execute(
            "INSERT OR IGNORE INTO roles (code, name, is_system, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (code, name, is_system, ts, ts),
        )
    # Administrator → every permission; others → their grant list.
    perm_ids = {c: pid for pid, c in conn.execute("SELECT id, code FROM permissions").fetchall()}
    role_ids = {c: rid for rid, c in conn.execute("SELECT id, code FROM roles").fetchall()}
    for perm_code, pid in perm_ids.items():
        conn.execute(
            "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
            (role_ids["ADMINISTRATOR"], pid),
        )
    for role_code, perms in _ROLE_GRANTS.items():
        for perm_code in perms:
            conn.execute(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (role_ids[role_code], perm_ids[perm_code]),
            )

    for code, name, symbol, dp, is_base in CURRENCIES:
        conn.execute(
            "INSERT OR IGNORE INTO currencies (code, name, symbol, decimal_places, is_base,"
            " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (code, name, symbol, dp, is_base, ts, ts),
        )
    for code, en, fa, symbol in UNITS:
        conn.execute(
            "INSERT OR IGNORE INTO units (code, name_en, name_fa, symbol, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (code, en, fa, symbol, ts, ts),
        )
    for code, name, atype in ACCOUNTS:
        conn.execute(
            "INSERT OR IGNORE INTO accounts (code, name, type, is_system, created_at, updated_at)"
            " VALUES (?, ?, ?, 1, ?, ?)",
            (code, name, atype, ts, ts),
        )
    for doc_type, prefix in SEQUENCES:
        conn.execute(
            "INSERT OR IGNORE INTO document_sequences (doc_type, prefix, next_number, padding,"
            " updated_at) VALUES (?, ?, 1, 6, ?)",
            (doc_type, prefix, ts),
        )
