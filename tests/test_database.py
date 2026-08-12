"""Database infrastructure: connection, pragmas, transactions (Prompt 01 §9-§11, §32)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from zenith_business.core.exceptions import DatabaseError
from zenith_business.database import Database, check_health
from zenith_business.database.connection import MEMORY


@pytest.fixture
def mem_db() -> Database:
    db = Database(MEMORY)
    db.connect()
    # A scratch table (infrastructure test only — NOT a business table).
    db.connection().execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    return db


def test_connection_opens_and_reports_connected() -> None:
    db = Database(MEMORY)
    assert not db.is_connected
    db.connect()
    assert db.is_connected
    db.close()
    assert not db.is_connected


def test_foreign_keys_enabled() -> None:
    db = Database(MEMORY)
    db.connect()
    assert db.foreign_keys_enabled() is True


def test_file_db_uses_wal(data_home: Path, app_paths) -> None:
    db = Database(app_paths.database_file)
    db.connect()
    assert str(db.pragma("journal_mode")).lower() == "wal"
    assert db.foreign_keys_enabled() is True
    db.close()


def test_transaction_commits(mem_db: Database) -> None:
    with mem_db.transaction() as conn:
        conn.execute("INSERT INTO t (v) VALUES ('a')")
    rows = mem_db.connection().execute("SELECT COUNT(*) FROM t").fetchone()[0]
    assert rows == 1


def test_transaction_rolls_back_on_error(mem_db: Database) -> None:
    with pytest.raises(ValueError):
        with mem_db.transaction() as conn:
            conn.execute("INSERT INTO t (v) VALUES ('b')")
            raise ValueError("boom")
    rows = mem_db.connection().execute("SELECT COUNT(*) FROM t").fetchone()[0]
    assert rows == 0  # nothing persisted


def test_nested_transaction_savepoint_rolls_back_inner(mem_db: Database) -> None:
    with mem_db.transaction() as conn:
        conn.execute("INSERT INTO t (v) VALUES ('outer')")
        with pytest.raises(ValueError):
            with mem_db.transaction() as conn2:
                conn2.execute("INSERT INTO t (v) VALUES ('inner')")
                raise ValueError("inner fails")
        # inner rolled back, outer continues
    rows = [r[0] for r in mem_db.connection().execute("SELECT v FROM t").fetchall()]
    assert rows == ["outer"]


def test_fk_constraint_is_enforced() -> None:
    db = Database(MEMORY)
    db.connect()
    conn = db.connection()
    conn.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
    conn.execute(
        "CREATE TABLE child (id INTEGER PRIMARY KEY, "
        "pid INTEGER REFERENCES parent(id))"
    )
    with pytest.raises(sqlite3.IntegrityError):
        with db.transaction() as c:
            c.execute("INSERT INTO child (pid) VALUES (999)")  # no such parent


def test_health_check_healthy(mem_db: Database) -> None:
    health = check_health(mem_db)
    assert health.ok is True
    assert health.foreign_keys is True
    assert health.sqlite_version


def test_open_bad_path_raises() -> None:
    # A path whose parent cannot be created (a file used as a directory).
    bad = Database("/dev/null/nope.db")
    with pytest.raises(DatabaseError):
        bad.connect()
