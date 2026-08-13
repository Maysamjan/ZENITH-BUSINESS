"""Backup / restore foundation (Stage 02 §41)."""

from __future__ import annotations

from pathlib import Path

import pytest

from zenith_business.core.exceptions import SecurityError
from zenith_business.database.connection import Database
from zenith_business.services.context import open_application_context
from zenith_business.services.exceptions import ValidationError


def test_create_and_validate_backup(admin_context, tmp_path: Path) -> None:
    path = admin_context.backup.create_backup()
    assert path.exists()
    assert admin_context.backup.validate_backup(path) is True


def test_backup_requires_permission(context) -> None:
    # No user signed in → not permitted (SecurityError covers auth/authz).
    with pytest.raises(SecurityError):
        context.backup.create_backup()


def test_validate_rejects_non_backup(admin_context, tmp_path: Path) -> None:
    junk = tmp_path / "junk.db"
    junk.write_text("not a database")
    assert admin_context.backup.validate_backup(junk) is False


def test_restore_roundtrip(admin_context, tmp_path: Path) -> None:
    backup_path = admin_context.backup.create_backup()
    target = tmp_path / "restored.db"
    admin_context.backup.restore_backup(backup_path, target)
    # The restored file opens as a healthy migrated database.
    db = Database(target)
    ctx = open_application_context(db)
    assert ctx.users_repo.count() >= 1
    db.close()


def test_restore_rejects_bad_file(admin_context, tmp_path: Path) -> None:
    junk = tmp_path / "junk.db"
    junk.write_text("nope")
    with pytest.raises(ValidationError):
        admin_context.backup.restore_backup(junk, tmp_path / "out.db")
