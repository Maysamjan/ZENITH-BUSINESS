"""Backup verification and safe restore (Stage 10 §4, §5, §6).

Stage 02 gave the application a working backup and a validating restore. What it
did not give it was a restore that is safe when something goes *wrong*, and that
is the whole point of a restore: it is used on the worst day the customer has.

The Stage 02 path closed the live database and then copied the candidate
straight over it. Everything before the copy was careful; the copy itself was
not. A disk filling up, a USB stick pulled out, or a power cut half way through
would leave the customer with **no** working database — neither the old one nor
the new one — which is the one outcome a restore must never produce.

What this service adds, without changing how a backup is written:

* a **safety backup of the current data** before anything is replaced, so the
  state being restored over is always recoverable;
* an **atomic swap**: the candidate is copied to a temporary file beside the
  target and only then moved into place with :func:`os.replace`, which is atomic
  on both Windows and POSIX. The live database is replaced in one step or not
  at all;
* **verification after the swap** — the restored file is opened and integrity
  checked before the restore is called a success, and the safety backup is put
  back if it is not;
* **audit entries** for started, completed and failed restores, which Stage 02
  never wrote at all.

Nothing here is destructive on failure: every error path ends with the customer
holding a working database and a file they can retry.
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path

from zenith_business.core.clock import now_utc
from zenith_business.security import backup_crypto
from zenith_business.core.logging_setup import get_logger
from zenith_business.services.exceptions import ValidationError

_logger = get_logger("services.restore")

#: Tables a file must have to be a Zenith database rather than merely valid SQLite.
_REQUIRED_TABLES = ("schema_migrations", "users", "audit_log")


@dataclass(frozen=True)
class BackupCheck:
    """Why a file is or is not a usable Zenith backup — shown to the customer."""

    ok: bool
    reason: str
    detail: str = ""
    schema_version: int | None = None
    size_bytes: int = 0

    def __bool__(self) -> bool:
        return self.ok


@dataclass(frozen=True)
class IntegrityReport:
    """A health check of the LIVE database (Stage 10 §6).

    Stage 01's ``check_health`` is a locked contract covering foreign keys and a
    round trip; it deliberately does not run ``integrity_check``, which walks the
    whole file. This is the deeper check, offered on demand rather than at every
    startup, and it does not modify the locked one.
    """

    ok: bool
    integrity: str
    foreign_keys_ok: bool
    orphan_count: int
    journal_mode: str
    schema_version: int | None
    detail: str = ""


def check_database_integrity(db) -> IntegrityReport:
    """Run SQLite's own integrity and foreign-key checks against the live file."""
    conn = db.connection()
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        integrity = str(row[0]) if row else "unknown"
    except sqlite3.DatabaseError as exc:
        return IntegrityReport(False, "error", False, 0, "", None, str(exc))
    try:
        orphans = conn.execute("PRAGMA foreign_key_check").fetchall()
    except sqlite3.DatabaseError:
        orphans = []
    try:
        journal = str(conn.execute("PRAGMA journal_mode").fetchone()[0])
    except sqlite3.DatabaseError:
        journal = ""
    try:
        version_row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(version_row[0]) if version_row and version_row[0] is not None else None
    except sqlite3.DatabaseError:
        version = None

    fk_ok = not orphans
    ok = integrity == "ok" and fk_ok
    detail = ("Database is healthy." if ok
              else f"integrity={integrity}; orphaned rows={len(orphans)}")
    return IntegrityReport(ok=ok, integrity=integrity, foreign_keys_ok=fk_ok,
                           orphan_count=len(orphans), journal_mode=journal,
                           schema_version=version, detail=detail)


@dataclass(frozen=True)
class RestoreResult:
    """What a restore actually did, including the safety copy it left behind."""

    restored_from: Path
    safety_backup: Path | None
    schema_version: int | None
    integrity_ok: bool


def inspect_backup(path: str | Path, *, passphrase: str | None = None) -> BackupCheck:
    """Examine a candidate backup file without opening the live database.

    Every failure is reported as a reason rather than an exception, so the UI can
    tell the customer *why* a file was refused instead of "restore failed".

    An encrypted ``.zbak`` is described from its authenticated header without a
    passphrase — enough to list and identify it. With a passphrase it is fully
    decrypted and the database inside is checked, which is what a restore needs.
    """
    p = Path(path)
    if not p.exists():
        return BackupCheck(False, "missing", f"No such file: {p}")
    if not p.is_file():
        return BackupCheck(False, "not_a_file", f"Not a file: {p}")
    size = p.stat().st_size
    if size == 0:
        return BackupCheck(False, "empty", "The file is empty.", size_bytes=0)

    if backup_crypto.looks_encrypted(p):
        return _inspect_encrypted(p, size, passphrase)

    try:
        conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return BackupCheck(False, "unreadable", str(exc), size_bytes=size)
    try:
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
        except sqlite3.DatabaseError as exc:
            return BackupCheck(False, "not_a_database", str(exc), size_bytes=size)
        if not integrity or integrity[0] != "ok":
            detail = integrity[0] if integrity else "unknown"
            return BackupCheck(False, "corrupt", str(detail), size_bytes=size)

        names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        missing = [t for t in _REQUIRED_TABLES if t not in names]
        if missing:
            return BackupCheck(False, "not_zenith",
                               f"Missing table(s): {', '.join(missing)}",
                               size_bytes=size)
        try:
            row = conn.execute(
                "SELECT MAX(version) FROM schema_migrations").fetchone()
            version = int(row[0]) if row and row[0] is not None else None
        except sqlite3.Error:
            version = None
        return BackupCheck(True, "ok", "Valid Zenith backup.",
                           schema_version=version, size_bytes=size)
    finally:
        conn.close()


def _inspect_encrypted(path: Path, size: int, passphrase: str | None) -> BackupCheck:
    """Describe (and, given a passphrase, fully verify) a ``.zbak`` container."""
    header = backup_crypto.read_header(path)
    if header is None:
        return BackupCheck(False, "corrupt", "The backup header is damaged.",
                           size_bytes=size)
    if passphrase is None:
        # Identified, not yet proven. A restore always supplies the passphrase,
        # so nothing is ever restored on the strength of a header alone.
        return BackupCheck(True, "encrypted",
                           "Encrypted Zenith backup (passphrase required).",
                           schema_version=header.schema_version, size_bytes=size)
    with tempfile.TemporaryDirectory() as tmp:
        plain = Path(tmp) / "candidate.db"
        try:
            backup_crypto.decrypt_file(path, plain, passphrase)
        except backup_crypto.WrongPassphrase:
            return BackupCheck(False, "bad_passphrase",
                               "Wrong passphrase, or the backup has been altered.",
                               size_bytes=size)
        except backup_crypto.BackupCryptoError as exc:
            return BackupCheck(False, "corrupt", str(exc), size_bytes=size)
        inner = inspect_backup(plain)
        # Report the container's size, not the decrypted copy's.
        return BackupCheck(inner.ok, inner.reason, inner.detail,
                           schema_version=inner.schema_version, size_bytes=size)


class SafeRestoreService:
    """Restores a backup without ever leaving the customer without a database."""

    def __init__(self, db, backups_dir: Path | str, audit=None, session=None,
                 authz=None) -> None:
        self._db = db
        self._backups_dir = Path(backups_dir)
        self._audit = audit
        self._session = session
        self._authz = authz

    # ---- reads -----------------------------------------------------------

    @staticmethod
    def inspect(path: str | Path, *, passphrase: str | None = None) -> BackupCheck:
        return inspect_backup(path, passphrase=passphrase)

    def safety_backup_path(self, *, encrypted: bool = False) -> Path:
        stamp = now_utc().strftime("%Y%m%d-%H%M%S")
        suffix = ".zbak" if encrypted else ".db"
        return self._backups_dir / f"zenith-before-restore-{stamp}{suffix}"

    # ---- the restore -----------------------------------------------------

    def restore(self, source: str | Path, target_db_path: str | Path, *,
                confirmed: bool = False, passphrase: str | None = None,
                safety_passphrase: str | None = None) -> RestoreResult:
        """Replace the live database with ``source``.

        ``confirmed`` must be True. It is not decoration: a restore discards the
        current data, and an API that can do that on a default argument will
        eventually be called by accident.

        ``passphrase`` opens an encrypted *source*. ``safety_passphrase`` locks
        the copy taken of the database being replaced — which is the customer's
        live business data and was previously left in the backups folder as a
        plain, readable ``.db``. The screen supplies the owner password it has
        just verified. Without one the safety copy stays plain, which is what a
        programmatic caller with no password available gets, and is said out
        loud in the log rather than quietly assumed to be fine.
        """
        if self._authz is not None:
            self._authz.require("backup.restore")
        if not confirmed:
            raise ValidationError(
                "Restore attempted without explicit confirmation.",
                user_message="Please confirm before restoring a backup.")

        source = Path(source)
        target = Path(target_db_path)
        check = inspect_backup(source, passphrase=passphrase)
        self._record("backup.restore_started",
                     f"file={source.name} valid={check.ok} reason={check.reason}")
        if check.ok and check.reason == "encrypted":
            # Identified but not authenticated: a restore must never proceed on
            # a header alone.
            self._record("backup.restore_failed",
                         f"file={source.name} reason=passphrase_required")
            raise ValidationError(
                "Encrypted backup needs its passphrase.",
                user_message="This backup is encrypted. Enter its passphrase to "
                             "restore it.")
        if not check.ok:
            self._record("backup.restore_failed",
                         f"file={source.name} reason={check.reason}")
            raise ValidationError(
                f"Backup failed validation ({check.reason}): {source}",
                user_message=_REFUSAL.get(check.reason,
                                          "This file is not a valid Zenith backup."))

        # 1. Safety copy of what is about to be replaced.
        safety: Path | None = None
        if target.exists():
            self._backups_dir.mkdir(parents=True, exist_ok=True)
            protected = bool(safety_passphrase) and backup_crypto.available()
            if safety_passphrase and not protected:      # pragma: no cover - no backend
                _logger.warning("No encryption backend: the safety copy will be plain.")
            elif not safety_passphrase:
                _logger.warning("No safety passphrase supplied: the safety copy of "
                                "the live database will be a plain .db file.")
            safety = self.safety_backup_path(encrypted=protected)
            try:
                self._snapshot_live(safety, target, passphrase=safety_passphrase
                                    if protected else None)
            except Exception as exc:
                self._record("backup.restore_failed",
                             f"file={source.name} reason=safety_backup_failed")
                raise ValidationError(
                    f"Could not create a safety backup: {exc}",
                    user_message="Could not back up the current data, so the "
                                 "restore was cancelled. Nothing has changed.")

        self._db.close()      # release the live connection before the swap

        # 2. Put the plain database beside the target, then swap atomically.
        #    An encrypted container is decrypted into the staging file, so the
        #    swap itself is identical for both kinds of backup.
        staged = target.with_name(target.name + ".restoring")
        try:
            if backup_crypto.looks_encrypted(source):
                backup_crypto.decrypt_file(source, staged, passphrase or "")
            else:
                shutil.copy2(source, staged)
            import os
            os.replace(staged, target)
        except Exception as exc:
            staged.unlink(missing_ok=True)
            self._rollback(safety, target, passphrase=safety_passphrase)
            self._record("backup.restore_failed",
                         f"file={source.name} reason=copy_failed")
            raise ValidationError(
                f"Restore failed while copying: {exc}",
                user_message="The restore could not be completed. Your previous "
                             "data is still in place.")

        # 3. The restored file has to prove itself before this is a success.
        verified = inspect_backup(target)
        if not verified.ok:
            self._rollback(safety, target, passphrase=safety_passphrase)
            self._record("backup.restore_failed",
                         f"file={source.name} reason=verify_after_restore")
            raise ValidationError(
                f"Restored database failed verification: {verified.reason}",
                user_message="The restored file did not verify, so your previous "
                             "data has been put back.")

        self._sweep_stale_journals(target)
        self._record("backup.restore_completed",
                     f"file={source.name} schema_v={verified.schema_version}"
                     f" safety={safety.name if safety else 'none'}")
        _logger.info("Database restored from %s (safety copy: %s)", source, safety)
        return RestoreResult(restored_from=source, safety_backup=safety,
                             schema_version=verified.schema_version,
                             integrity_ok=True)

    # ---- internals -------------------------------------------------------

    def _snapshot_live(self, destination: Path, target: Path,
                       *, passphrase: str | None = None) -> None:
        """Consistent copy of the CURRENT database, via SQLite's backup API.

        With a passphrase the copy is wrapped in the same authenticated ``.zbak``
        container a normal backup uses, and the plain intermediate is removed —
        so the file left in the backups folder is not a readable copy of the
        customer's books.
        """
        plain = destination if passphrase is None else destination.with_suffix(".staging")
        try:
            source_conn = self._db.connection()
            dest = sqlite3.connect(plain)
            try:
                source_conn.backup(dest)
            finally:
                dest.close()
        except Exception:
            # The live connection may already be unusable — that is exactly when
            # a safety copy matters most, so fall back to copying the file.
            shutil.copy2(target, plain)

        if passphrase is None:
            return
        from zenith_business.core.identity import APP_VERSION, PRODUCT_NAME

        try:
            header = backup_crypto.BackupHeader(
                created_at=now_utc().strftime("%Y-%m-%dT%H:%M:%SZ"),
                schema_version=inspect_backup(plain).schema_version,
                app_version=APP_VERSION, product=PRODUCT_NAME,
                hint="Safety copy taken before a restore.")
            backup_crypto.encrypt_file(plain, destination, passphrase, header=header)
        finally:
            plain.unlink(missing_ok=True)

    def _rollback(self, safety: Path | None, target: Path,
                  *, passphrase: str | None = None) -> None:
        """Put the pre-restore database back. Best effort, and loudly logged.

        The safety copy may now be an encrypted container, so rolling back may
        mean decrypting it first — with the passphrase held in memory from the
        moment it was written, never one asked for again at the worst time.
        """
        if safety is None or not safety.exists():
            return
        try:
            import os
            staged = target.with_name(target.name + ".rollback")
            if backup_crypto.looks_encrypted(safety):
                backup_crypto.decrypt_file(safety, staged, passphrase or "")
            else:
                shutil.copy2(safety, staged)
            os.replace(staged, target)
            _logger.warning("Restore rolled back; previous database reinstated.")
        except Exception as exc:
            _logger.error("ROLLBACK FAILED — the safety backup is at %s (%s)",
                          safety, exc)

    @staticmethod
    def _sweep_stale_journals(target: Path) -> None:
        """Remove WAL/SHM belonging to the replaced database.

        They describe the file that was just swapped out. Left behind, SQLite
        would try to apply them to the restored database on the next open.
        """
        for suffix in ("-wal", "-shm"):
            Path(str(target) + suffix).unlink(missing_ok=True)

    def _record(self, action: str, details: str) -> None:
        if self._audit is None:
            return
        try:
            user_id = self._session.user_id if self._session is not None else None
            username = self._session.username if self._session is not None else None
            # Deliberately NOT inside self._db.transaction(): a restore closes the
            # database, and an audit write must not be what makes a restore fail.
            self._audit.record(action=action, user_id=user_id, username=username,
                               details=details)
        except Exception:
            _logger.warning("Could not write the %s audit entry.", action)


#: Customer-facing wording per refusal reason.
_REFUSAL = {
    "missing": "That file could not be found.",
    "not_a_file": "That is a folder, not a backup file.",
    "empty": "That file is empty.",
    "unreadable": "That file could not be opened.",
    "not_a_database": "That file is not a database.",
    "corrupt": "That backup is damaged and cannot be restored.",
    "not_zenith": "That is not a Zenith Business backup.",
    "bad_passphrase": "Wrong passphrase, or the backup has been altered.",
}
