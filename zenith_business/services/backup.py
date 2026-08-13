"""Backup / restore foundation (Stage 02 §41).

Uses SQLite's online backup API to produce a consistent, timestamped copy of the
live database even while it is open — no file copy races. Restore validates the
candidate file (integrity check + expected schema table) before it is put in
place, so a corrupt or unrelated file can never silently replace live data.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

from zenith_business.core.clock import now_utc
from zenith_business.core.logging_setup import get_logger
from zenith_business.database.connection import Database
from zenith_business.repositories.system import AuditRepository
from zenith_business.services.authorization import AuthorizationService
from zenith_business.services.exceptions import ValidationError
from zenith_business.services.session import SessionContext

_logger = get_logger("services.backup")


class BackupService:
    def __init__(
        self,
        db: Database,
        backups_dir: Path,
        audit: AuditRepository,
        session: SessionContext,
        authz: AuthorizationService,
    ) -> None:
        self._db = db
        self._backups_dir = Path(backups_dir)
        self._audit = audit
        self._session = session
        self._authz = authz

    def create_backup(self) -> Path:
        """Write a consistent ``.db`` snapshot to the backups directory."""
        self._authz.require("backup.create")
        self._backups_dir.mkdir(parents=True, exist_ok=True)
        stamp = now_utc().strftime("%Y%m%d-%H%M%S")
        target = self._backups_dir / f"zenith-backup-{stamp}.db"

        source = self._db.connection()
        dest = sqlite3.connect(target)
        try:
            source.backup(dest)
        finally:
            dest.close()

        with self._db.transaction():
            self._audit.record(
                action="backup.create", user_id=self._session.user_id,
                username=self._session.username, details=f"file={target.name}")
        _logger.info("Database backup written: %s", target)
        return target

    def validate_backup(self, path: str | Path) -> bool:
        """Return True if ``path`` is a healthy Zenith database backup."""
        p = Path(path)
        if not p.exists():
            return False
        try:
            conn = sqlite3.connect(p)
            try:
                integrity = conn.execute("PRAGMA integrity_check").fetchone()
                if not integrity or integrity[0] != "ok":
                    return False
                has_migrations = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table'"
                    " AND name='schema_migrations'").fetchone()
                return has_migrations is not None
            finally:
                conn.close()
        except sqlite3.Error:
            return False

    def restore_backup(self, path: str | Path, target_db_path: str | Path) -> Path:
        """Validate and put a backup in place (app must restart afterwards)."""
        self._authz.require("backup.restore")
        source = Path(path)
        if not self.validate_backup(source):
            raise ValidationError(
                f"Backup file failed validation: {source}",
                user_message="This file is not a valid Zenith backup.")
        target = Path(target_db_path)
        self._db.close()  # release the live connection before overwriting
        shutil.copy2(source, target)
        _logger.info("Database restored from backup %s -> %s", source, target)
        return target
