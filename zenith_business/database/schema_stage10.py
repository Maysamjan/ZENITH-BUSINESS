"""Forward migration 0013 — audit hash chain columns (Stage 10 hardening §5).

Two nullable columns on ``audit_log``. Nullable is the whole design: locked
business services call ``AuditRepository.record`` inside their own transactions
and know nothing about hashing, so a freshly written row simply has no hash yet
and the chain service seals it afterwards. Nothing in locked behaviour changes,
and an un-sealed row is never treated as a tampered one.

Existing entries are sealed on first run, which establishes the chain from the
history that is already there. That is an honest starting point rather than a
claim about the past: it proves nothing has changed *since* the chain was
established, which is exactly what it says.
"""

from __future__ import annotations

import sqlite3


def migrate_stage10(conn: sqlite3.Connection) -> None:
    """Migration 0013 — add ``entry_hash`` / ``prev_hash`` to ``audit_log``."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(audit_log)")}
    if "entry_hash" not in existing:
        conn.execute("ALTER TABLE audit_log ADD COLUMN entry_hash TEXT")
    if "prev_hash" not in existing:
        conn.execute("ALTER TABLE audit_log ADD COLUMN prev_hash TEXT")
    # The chain is walked in id order and sealed incrementally; this index keeps
    # "what is still unsealed?" cheap as the log grows.
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_audit_unsealed"
        " ON audit_log(id) WHERE entry_hash IS NULL")
