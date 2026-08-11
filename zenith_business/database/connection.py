"""SQLite connection management and safe transactions (Prompt 01 §9-§11).

Design notes
------------
* Business logic stays decoupled from SQLite specifics as far as is reasonable
  (Master Spec §2). The rest of the app talks to :class:`Database`, not to the
  ``sqlite3`` module directly, so a future PostgreSQL backend can implement the
  same surface.
* SQLite is configured for **data integrity first** (Prompt 01 §10):

  =====================  ==========  =====================================
  Pragma                 Value       Why
  =====================  ==========  =====================================
  ``foreign_keys``       ``ON``      Enforce referential integrity (§22).
  ``busy_timeout``       5000 ms     Wait, don't fail immediately, on locks.
  ``journal_mode``       ``WAL``     Better read/write concurrency with a
                                     durable, crash-safe journal.
  ``synchronous``        ``NORMAL``  Safe with WAL; good durability/speed
                                     balance for a financial desktop app.
  =====================  ==========  =====================================

  WAL is enabled deliberately (not "blindly"): it improves concurrency while
  remaining crash-safe, and ``synchronous=NORMAL`` is the SQLite-recommended
  companion for WAL. Both are set explicitly and documented here so the choice
  is auditable. WAL is a no-op for in-memory databases used in tests.

Transactions
------------
``sqlite3`` in Python has surprising autocommit behavior. We take explicit
control: ``isolation_level=None`` disables the driver's implicit transaction
management, and :meth:`Database.transaction` issues ``BEGIN`` / ``COMMIT`` /
``ROLLBACK`` itself. This gives future services the exact ``with
db.transaction(): ...`` semantics required by Master Spec §6.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from zenith_business.core.exceptions import DatabaseError, TransactionError
from zenith_business.core.logging_setup import get_logger

_logger = get_logger("database")

#: Sentinel path for an in-memory database (tests / health checks).
MEMORY = ":memory:"


class Database:
    """Owns a single SQLite connection and its lifecycle.

    Not thread-safe by design: one :class:`Database` per thread. A future stage
    may add a connection pool/registry if background workers are introduced.
    """

    def __init__(self, path: str | Path, *, busy_timeout_ms: int = 5000) -> None:
        self._path = MEMORY if str(path) == MEMORY else Path(path)
        self._busy_timeout_ms = busy_timeout_ms
        self._conn: sqlite3.Connection | None = None
        self._depth = 0  # transaction nesting depth (savepoints)

    # ---- lifecycle --------------------------------------------------------

    @property
    def path(self) -> str:
        return str(self._path)

    @property
    def is_connected(self) -> bool:
        return self._conn is not None

    def connect(self) -> sqlite3.Connection:
        """Open the connection (idempotent) and apply safety pragmas."""
        if self._conn is not None:
            return self._conn

        try:
            if self._path != MEMORY:
                Path(self._path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                self._path,
                # We manage transactions explicitly (see module docstring).
                isolation_level=None,
                timeout=self._busy_timeout_ms / 1000.0,
            )
            conn.row_factory = sqlite3.Row
            self._configure(conn)
        except (sqlite3.Error, OSError) as exc:
            raise DatabaseError(f"Could not open database {self._path}: {exc}") from exc

        self._conn = conn
        _logger.info("Database connection opened: %s", self._path)
        return conn

    def _configure(self, conn: sqlite3.Connection) -> None:
        """Apply SQLite safety pragmas (see module docstring)."""
        conn.execute(f"PRAGMA busy_timeout = {int(self._busy_timeout_ms)}")
        conn.execute("PRAGMA foreign_keys = ON")
        # WAL is meaningless / unsupported for in-memory DBs.
        if self._path != MEMORY:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")

    def close(self) -> None:
        """Close the connection if open."""
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None
                self._depth = 0
                _logger.info("Database connection closed: %s", self._path)

    # ---- introspection helpers -------------------------------------------

    def connection(self) -> sqlite3.Connection:
        """Return the live connection, opening it if necessary."""
        return self._conn or self.connect()

    def foreign_keys_enabled(self) -> bool:
        """Return True if FK enforcement is active on the connection."""
        row = self.connection().execute("PRAGMA foreign_keys").fetchone()
        return bool(row[0]) if row is not None else False

    def pragma(self, name: str) -> object:
        """Return the scalar value of a PRAGMA (introspection/tests)."""
        row = self.connection().execute(f"PRAGMA {name}").fetchone()
        return row[0] if row is not None else None

    # ---- transactions -----------------------------------------------------

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Atomic transaction context (Master Spec §6).

        Usage::

            with db.transaction() as conn:
                conn.execute(...)
                conn.execute(...)

        All statements commit together, or roll back together on any exception.
        Nested ``with`` blocks use SAVEPOINTs so composed operations remain
        atomic without prematurely committing an outer transaction.
        """
        conn = self.connection()

        if self._depth == 0:
            self._begin(conn, "BEGIN")
            outermost = True
        else:
            savepoint = f"sp_{self._depth}"
            self._begin(conn, f"SAVEPOINT {savepoint}")
            outermost = False

        self._depth += 1
        try:
            yield conn
        except BaseException:
            self._depth -= 1
            self._rollback(conn, outermost)
            raise
        else:
            self._depth -= 1
            self._commit(conn, outermost)

    def _begin(self, conn: sqlite3.Connection, statement: str) -> None:
        try:
            conn.execute(statement)
        except sqlite3.Error as exc:
            raise TransactionError(f"Could not begin transaction: {exc}") from exc

    def _commit(self, conn: sqlite3.Connection, outermost: bool) -> None:
        try:
            if outermost:
                conn.execute("COMMIT")
            else:
                conn.execute(f"RELEASE SAVEPOINT sp_{self._depth}")
        except sqlite3.Error as exc:
            raise TransactionError(f"Could not commit transaction: {exc}") from exc

    def _rollback(self, conn: sqlite3.Connection, outermost: bool) -> None:
        try:
            if outermost:
                conn.execute("ROLLBACK")
            else:
                sp = f"sp_{self._depth}"
                conn.execute(f"ROLLBACK TO SAVEPOINT {sp}")
                conn.execute(f"RELEASE SAVEPOINT {sp}")
        except sqlite3.Error as exc:
            # Rollback failing is serious but we must not mask the original
            # exception with a new one where avoidable; log and continue.
            _logger.error("Rollback failed: %s", exc)

    # ---- context manager --------------------------------------------------

    def __enter__(self) -> "Database":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
