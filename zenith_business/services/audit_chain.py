"""Tamper-evident audit trail (Stage 10 hardening §5).

The audit log was append-only *by construction*: no service can edit or delete a
row and no screen offers it. That stops the application from rewriting history.
It does nothing about somebody opening the database file with a SQLite browser,
which is the threat that actually matters for a log whose job is to be evidence.

This adds a hash chain. Each entry gets::

    entry_hash = SHA-256( previous_hash || id || created_at || action ||
                          user_id || username || entity_type || entity_id ||
                          document_no || details )

so every row commits to the one before it. Changing any field of any row, or
deleting a row, or inserting one, breaks the chain from that point on and
:func:`verify_chain` reports exactly where.

What this does and does not buy
-------------------------------
**Detection, not prevention.** Someone with write access to the file can still
change a row — but they cannot do it *quietly*, because they would have to
recompute every hash after it, and the application will say which entry first
disagrees. That is the honest claim, and it is the one worth making: an audit
trail's value is that you can tell whether it has been edited.

An attacker who recomputes the whole chain defeats this. Defending against that
needs a secret the attacker does not have (an HMAC key held outside the
database) or an external anchor (publishing the head hash somewhere else).
Neither fits a single offline PC where the owner holds every key, so it is
recorded as a limitation rather than pretended away.

Why it does not touch locked behaviour
--------------------------------------
Hashing happens **after** an entry is written, driven by this service, not
inside `AuditRepository.record` — which Stage 02 froze and which every locked
business service calls inside its own transaction. Locked code is unchanged and
unaware; an un-hashed row is simply a row the chain has not caught up with yet,
and :meth:`AuditChainService.seal` extends the chain over anything pending.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from zenith_business.core.logging_setup import get_logger

_logger = get_logger("services.audit_chain")

#: The chain starts from a fixed, public value rather than an empty string, so
#: an empty log and a truncated one are not the same thing.
GENESIS = "zenith-audit-chain-v1"


@dataclass(frozen=True)
class ChainReport:
    """The result of walking the whole chain."""

    ok: bool
    checked: int
    sealed: int
    unsealed: int
    first_bad_id: int | None = None
    detail: str = ""


def compute_hash(previous: str, row) -> str:
    """The hash for one entry, given the hash of the entry before it.

    Every field a reader would rely on is committed to. ``None`` and the empty
    string are encoded differently so one cannot be swapped for the other, and
    the unit separator cannot appear in the values, so fields cannot be shifted
    across boundaries.
    """
    def field(value) -> str:
        return "\x00" if value is None else str(value)

    material = "\x1f".join((
        previous,
        field(row["id"]),
        field(row["created_at"]),
        field(row["action"]),
        field(row["user_id"]),
        field(row["username"]),
        field(row["entity_type"]),
        field(row["entity_id"]),
        field(row["document_no"]),
        field(row["details"]),
    ))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class AuditChainService:
    """Seals audit entries into a hash chain and verifies it."""

    def __init__(self, db) -> None:
        self._db = db

    # ---- sealing ---------------------------------------------------------

    def seal(self, *, limit: int | None = None) -> int:
        """Hash every entry that does not yet have one. Returns how many.

        Safe to call as often as you like: already-sealed rows are skipped, and
        the chain is extended strictly in id order so it cannot fork.
        """
        conn = self._db.connection()
        pending = conn.execute(
            "SELECT id, created_at, action, user_id, username, entity_type,"
            "       entity_id, document_no, details"
            "  FROM audit_log WHERE entry_hash IS NULL ORDER BY id"
            + (f" LIMIT {int(limit)}" if limit else "")).fetchall()
        if not pending:
            return 0

        previous = self.head_hash()
        sealed = 0
        with self._db.transaction() as tx:
            for row in pending:
                digest = compute_hash(previous, row)
                tx.execute(
                    "UPDATE audit_log SET entry_hash = ?, prev_hash = ? WHERE id = ?",
                    (digest, previous, row["id"]))
                previous = digest
                sealed += 1
        return sealed

    def head_hash(self) -> str:
        """The hash of the most recently sealed entry, or the genesis value."""
        row = self._db.connection().execute(
            "SELECT entry_hash FROM audit_log WHERE entry_hash IS NOT NULL"
            " ORDER BY id DESC LIMIT 1").fetchone()
        return row["entry_hash"] if row and row["entry_hash"] else GENESIS

    # ---- verifying -------------------------------------------------------

    def verify(self) -> ChainReport:
        """Walk the chain and report the first entry that does not agree."""
        conn = self._db.connection()
        rows = conn.execute(
            "SELECT id, created_at, action, user_id, username, entity_type,"
            "       entity_id, document_no, details, entry_hash, prev_hash"
            "  FROM audit_log ORDER BY id").fetchall()

        previous = GENESIS
        checked = sealed = unsealed = 0
        first_unsealed_id: int | None = None
        for row in rows:
            checked += 1
            if row["entry_hash"] is None:
                # Not yet sealed. Legitimate ONLY at the tail — those are entries
                # written since the last seal.
                unsealed += 1
                if first_unsealed_id is None:
                    first_unsealed_id = int(row["id"])
                continue

            if first_unsealed_id is not None:
                # A sealed entry AFTER an unsealed one means the unsealed row was
                # put in among history that was already sealed. Skipping unsealed
                # rows without this check left exactly that hole: a forged entry
                # inserted between two sealed ones chained correctly around it
                # and passed verification.
                return ChainReport(
                    False, checked, sealed, unsealed, first_unsealed_id,
                    f"Entry {first_unsealed_id} was inserted into history that "
                    f"had already been sealed.")
            sealed += 1
            if row["prev_hash"] != previous:
                return ChainReport(
                    False, checked, sealed, unsealed, int(row["id"]),
                    f"Entry {row['id']} does not follow the entry before it — a "
                    f"record may have been inserted or removed.")
            expected = compute_hash(previous, row)
            if expected != row["entry_hash"]:
                return ChainReport(
                    False, checked, sealed, unsealed, int(row["id"]),
                    f"Entry {row['id']} has been altered since it was recorded.")
            previous = row["entry_hash"]

        detail = (f"{sealed} entr{'y' if sealed == 1 else 'ies'} verified"
                  + (f", {unsealed} not yet sealed." if unsealed else "."))
        return ChainReport(True, checked, sealed, unsealed, None, detail)
