"""Schema versioning & migrations (Stage 02 §6)."""

from __future__ import annotations

from zenith_business.database.connection import MEMORY, Database
from zenith_business.database.migrations import MigrationRunner
from zenith_business.database.schema import PERMISSIONS, ROLES


def _tables(db: Database) -> set[str]:
    return {
        r[0]
        for r in db.connection().execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }


def test_migrate_applies_all_pending() -> None:
    db = Database(MEMORY)
    runner = MigrationRunner(db)
    assert runner.current_version() == 0
    applied = runner.migrate()
    assert applied == [1, 2]
    assert runner.current_version() == runner.latest_version()
    tables = _tables(db)
    for expected in ("users", "roles", "permissions", "sales", "purchases",
                     "inventory_movements", "audit_log", "schema_migrations"):
        assert expected in tables
    db.close()


def test_migrations_are_idempotent() -> None:
    db = Database(MEMORY)
    runner = MigrationRunner(db)
    runner.migrate()
    # A second run applies nothing and does not raise.
    assert runner.migrate() == []
    assert runner.pending() == []
    db.close()


def test_baseline_seed_counts() -> None:
    db = Database(MEMORY)
    MigrationRunner(db).migrate()
    conn = db.connection()
    assert conn.execute("SELECT COUNT(*) FROM permissions").fetchone()[0] == len(PERMISSIONS)
    assert conn.execute("SELECT COUNT(*) FROM roles").fetchone()[0] == len(ROLES)
    # Administrator holds every permission.
    admin_perms = conn.execute(
        "SELECT COUNT(*) FROM role_permissions rp JOIN roles r ON r.id = rp.role_id"
        " WHERE r.code = 'ADMINISTRATOR'").fetchone()[0]
    assert admin_perms == len(PERMISSIONS)
    # Currencies include a single base currency.
    base = conn.execute("SELECT code FROM currencies WHERE is_base = 1").fetchall()
    assert [r[0] for r in base] == ["AFN"]
    db.close()


def test_foreign_keys_enforced() -> None:
    db = Database(MEMORY)
    MigrationRunner(db).migrate()
    assert db.foreign_keys_enabled() is True
    db.close()
