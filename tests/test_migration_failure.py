"""Migration robustness: failure isolation & repeated runs (Stage 02 §19)."""

from __future__ import annotations

import pytest

from zenith_business.database import migrations as mig
from zenith_business.database.connection import MEMORY, Database
from zenith_business.database.migrations import Migration, MigrationRunner


def test_failed_migration_is_not_marked_applied(monkeypatch) -> None:
    def boom(conn):
        conn.execute("CREATE TABLE will_rollback (id INTEGER)")
        raise RuntimeError("simulated migration failure")

    patched = list(mig.MIGRATIONS) + [Migration(999, "boom", boom)]
    monkeypatch.setattr(mig, "MIGRATIONS", patched)

    db = Database(MEMORY)
    runner = MigrationRunner(db)
    with pytest.raises(RuntimeError):
        runner.migrate()

    # Good migrations committed; the failed one did NOT record a version…
    assert runner.current_version() == 2
    applied = [r[0] for r in db.connection().execute(
        "SELECT version FROM schema_migrations").fetchall()]
    assert 999 not in applied
    # …and its partial table was rolled back.
    exists = db.connection().execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='will_rollback'").fetchone()
    assert exists is None
    db.close()


def test_repeated_migration_is_idempotent(context) -> None:
    runner = MigrationRunner(context.db)
    assert runner.migrate() == []  # already migrated by the fixture
    assert runner.current_version() == runner.latest_version()


def test_migrate_on_already_current_db_is_noop(context) -> None:
    before = context.db.connection().execute(
        "SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    MigrationRunner(context.db).migrate()
    after = context.db.connection().execute(
        "SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
    assert before == after
