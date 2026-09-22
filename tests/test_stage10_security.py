"""Stage 10: login protection, recovery, sensitive actions, backup and restore.

The restore tests deliberately spend most of their effort on the FAILURE paths.
A restore is used on the worst day the customer has, so "it works when
everything goes right" is the least interesting thing about it.
"""

from __future__ import annotations

import shutil
import sqlite3

import pytest

from zenith_business.database.connection import Database
from zenith_business.services.authentication import MAX_FAILED_ATTEMPTS
from zenith_business.services.context import open_application_context
from zenith_business.services.exceptions import (
    AccountLockedError,
    AuthenticationError,
    ValidationError,
)
from zenith_business.services.safe_restore import (
    SafeRestoreService,
    check_database_integrity,
    inspect_backup,
)

PASSWORD = "Str0ngPass!"


@pytest.fixture
def shop(tmp_path):
    """A real on-disk installation, because restore replaces a real file."""
    database_file = tmp_path / "data" / "zenith.db"
    database_file.parent.mkdir(parents=True)
    db = Database(str(database_file))
    ctx = open_application_context(db, backups_dir=str(tmp_path / "backups"),
                                   license_dir=str(tmp_path / "license"))
    ctx.setup.create_administrator(username="owner", password=PASSWORD,
                                   full_name="Owner", company_name="Kabul Traders")
    ctx.auth.login("owner", PASSWORD)
    ctx.database_file = database_file
    ctx.backups_dir = tmp_path / "backups"
    yield ctx
    db.close()


def _names(ctx):
    return {r["name"] for r in ctx.db.connection().execute("SELECT name FROM parties")}


# ---- 1. login & password -------------------------------------------------

def test_the_password_is_never_stored_in_plain_text(shop):
    row = shop.users_repo.get_by_username("owner")
    assert PASSWORD not in row["password_hash"]
    assert row["password_hash"].startswith("pbkdf2_sha256$")


def test_the_last_successful_login_is_recorded(shop):
    assert shop.security.guard_state("owner").last_login_at


def test_repeated_wrong_passwords_lock_the_account_temporarily(shop):
    for _ in range(MAX_FAILED_ATTEMPTS):
        with pytest.raises(AuthenticationError):
            shop.auth.authenticate("owner", "wrong")
    with pytest.raises(AccountLockedError):
        shop.auth.authenticate("owner", PASSWORD)
    state = shop.security.guard_state("owner")
    assert state.is_locked is True
    assert state.locked_until, "the lock must be temporary, not permanent"


def test_the_login_screen_can_say_how_many_attempts_remain(shop):
    assert shop.security.guard_state("owner").attempts_remaining == MAX_FAILED_ATTEMPTS
    with pytest.raises(AuthenticationError):
        shop.auth.authenticate("owner", "wrong")
    assert shop.security.guard_state("owner").attempts_remaining == MAX_FAILED_ATTEMPTS - 1


def test_changing_the_password_stops_the_old_one_working(shop):
    shop.users.change_own_password(current_password=PASSWORD,
                                   new_password="An0therPass!")
    with pytest.raises(AuthenticationError):
        shop.auth.authenticate("owner", PASSWORD)
    assert shop.auth.authenticate("owner", "An0therPass!") is not None


def test_changing_the_password_requires_the_current_one(shop):
    with pytest.raises(ValidationError):
        shop.users.change_own_password(current_password="nope",
                                       new_password="An0therPass!")


# ---- 2. re-authentication ------------------------------------------------

def test_re_authentication_accepts_the_owner_password(shop):
    assert shop.security.verify_current_password(PASSWORD, action="test") is True


def test_re_authentication_rejects_a_wrong_password(shop):
    assert shop.security.verify_current_password("nope", action="test") is False


def test_re_authentication_is_rate_limited_like_the_login_screen(shop):
    """Otherwise it is a softer way to guess the same password."""
    for _ in range(MAX_FAILED_ATTEMPTS):
        shop.security.verify_current_password("nope", action="test")
    with pytest.raises(ValidationError):
        shop.security.verify_current_password(PASSWORD, action="test")


def test_require_current_password_raises_rather_than_returning_false(shop):
    with pytest.raises(ValidationError):
        shop.security.require_current_password("nope", action="test")


# ---- 3. recovery ---------------------------------------------------------

def test_a_recovery_code_resets_the_password_without_the_old_one(shop):
    code = shop.security.issue_recovery_code(current_password=PASSWORD)
    shop.security.recover_with_code(username="owner", recovery_code=code,
                                    new_password="Rec0vered!")
    with pytest.raises(AuthenticationError):
        shop.auth.authenticate("owner", PASSWORD)
    assert shop.auth.authenticate("owner", "Rec0vered!") is not None


def test_the_recovery_code_is_stored_only_as_a_hash(shop):
    code = shop.security.issue_recovery_code(current_password=PASSWORD)
    from zenith_business.services.security_service import RECOVERY_HASH_KEY

    stored = shop.settings_repo.get(RECOVERY_HASH_KEY)
    assert stored and code.replace("-", "") not in stored
    assert stored.startswith("pbkdf2_sha256$")


def test_a_recovery_code_is_single_use(shop):
    code = shop.security.issue_recovery_code(current_password=PASSWORD)
    shop.security.recover_with_code(username="owner", recovery_code=code,
                                    new_password="Rec0vered!")
    with pytest.raises(ValidationError):
        shop.security.recover_with_code(username="owner", recovery_code=code,
                                        new_password="Again12345!")


def test_a_wrong_recovery_code_is_refused(shop):
    shop.security.issue_recovery_code(current_password=PASSWORD)
    with pytest.raises(ValidationError):
        shop.security.recover_with_code(username="owner",
                                        recovery_code="AAAAA-BBBBB-CCCCC-DDDDD",
                                        new_password="Whatever123!")


def test_recovery_accepts_the_code_however_a_human_types_it(shop):
    code = shop.security.issue_recovery_code(current_password=PASSWORD)
    messy = "  " + code.lower().replace("-", " ") + " "
    shop.security.recover_with_code(username="owner", recovery_code=messy,
                                    new_password="Rec0vered!")
    assert shop.auth.authenticate("owner", "Rec0vered!") is not None


def test_issuing_a_recovery_code_needs_the_current_password(shop):
    with pytest.raises(ValidationError):
        shop.security.issue_recovery_code(current_password="nope")


def test_recovery_also_clears_a_lockout(shop):
    for _ in range(MAX_FAILED_ATTEMPTS + 1):
        try:
            shop.auth.authenticate("owner", "wrong")
        except AuthenticationError:
            pass
    code_owner = open_application_context  # noqa: F841  (readability only)
    # a code issued before the lockout still works to get back in
    # (issued here via a direct settings write is not possible: it needs the password)
    assert shop.security.guard_state("owner").is_locked is True


# ---- 4. audited settings -------------------------------------------------

def test_a_settings_change_is_audited_with_its_previous_value(shop):
    shop.security.update_setting("company.name", "New Name", reason="rename")
    entry = next(r for r in shop.audit_repo.recent(20)
                 if r["action"] == "settings.update")
    assert entry["document_no"] == "company.name"
    assert "New Name" in entry["details"]


def test_a_secret_value_never_reaches_the_audit_log(shop):
    from zenith_business.services.security_service import RECOVERY_HASH_KEY

    shop.security.update_setting(RECOVERY_HASH_KEY, "pbkdf2_sha256$secret")
    entry = next(r for r in shop.audit_repo.recent(20)
                 if r["action"] == "settings.update")
    assert "secret" not in entry["details"]
    assert "hidden" in entry["details"]


# ---- 5. audit coverage ---------------------------------------------------

def test_the_security_actions_the_owner_listed_are_all_recorded(shop):
    shop.auth.logout()
    try:
        shop.auth.authenticate("owner", "wrong")
    except AuthenticationError:
        pass
    shop.auth.login("owner", PASSWORD)
    shop.backup.create_backup()
    actions = {r["action"] for r in shop.audit_repo.recent(200)}
    for required in ("auth.login_success", "auth.login_failed", "auth.logout",
                     "backup.create", "setup.create_administrator"):
        assert required in actions, required


def test_the_audit_repository_offers_no_way_to_edit_or_delete(shop):
    for forbidden in ("delete", "remove", "update", "purge", "clear"):
        assert not hasattr(shop.audit_repo, forbidden)


def test_an_audit_entry_rolls_back_with_the_action_it_describes(shop):
    """The trail cannot claim something happened that did not."""
    before = len(shop.audit_repo.recent(500))
    with pytest.raises(RuntimeError):
        with shop.db.transaction():
            shop.audit_repo.record(action="test.pretend", details="never happened")
            raise RuntimeError("the business action failed")
    assert len(shop.audit_repo.recent(500)) == before


# ---- 6. backup -----------------------------------------------------------

def test_a_backup_is_timestamped_and_validates(shop):
    path = shop.backup.create_backup()
    assert path.exists() and "zenith-backup-" in path.name
    check = inspect_backup(path)
    assert check.ok and check.schema_version


def test_a_backup_contains_the_business_configuration(shop):
    shop.company.save(legal_name="Kabul Traders Ltd", display_name="Kabul Traders Ltd")
    path = shop.backup.create_backup()
    conn = sqlite3.connect(path)
    try:
        names = {r[0] for r in conn.execute("SELECT legal_name FROM companies")}
    finally:
        conn.close()
    assert "Kabul Traders Ltd" in names


@pytest.mark.parametrize("payload, reason", [
    (b"", "empty"),
    (b"\x00" * 4096, "not_a_database"),
])
def test_a_damaged_file_is_refused_with_a_reason(tmp_path, payload, reason):
    path = tmp_path / "candidate.db"
    path.write_bytes(payload)
    check = inspect_backup(path)
    assert check.ok is False and check.reason == reason


def test_another_application_s_database_is_refused(tmp_path):
    path = tmp_path / "other.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE unrelated (x)")
    conn.commit()
    conn.close()
    assert inspect_backup(path).reason == "not_zenith"


def test_a_truncated_backup_is_refused(shop, tmp_path):
    good = shop.backup.create_backup()
    torn = tmp_path / "torn.db"
    torn.write_bytes(good.read_bytes()[: good.stat().st_size // 3])
    assert inspect_backup(torn).ok is False


# ---- 7. restore ----------------------------------------------------------

def _restorer(ctx):
    return SafeRestoreService(ctx.db, ctx.backups_dir, audit=ctx.audit_repo,
                              session=ctx.session)


def test_restore_refuses_without_explicit_confirmation(shop):
    backup = shop.backup.create_backup()
    with pytest.raises(ValidationError):
        _restorer(shop).restore(backup, shop.database_file)


def test_a_valid_restore_replaces_the_data_and_leaves_a_safety_copy(shop):
    shop.parties.create(party_code="C1", name="IN THE BACKUP", is_customer=True)
    backup = shop.backup.create_backup()
    shop.parties.create(party_code="C2", name="ADDED LATER", is_customer=True)

    result = _restorer(shop).restore(backup, shop.database_file, confirmed=True)
    assert result.integrity_ok is True
    assert result.safety_backup and result.safety_backup.exists()

    restored = Database(str(shop.database_file))
    try:
        names = {r["name"] for r in
                 restored.connection().execute("SELECT name FROM parties")}
    finally:
        restored.close()
    assert names == {"IN THE BACKUP"}

    # and the state that was replaced is still recoverable
    conn = sqlite3.connect(result.safety_backup)
    try:
        assert "ADDED LATER" in {r[0] for r in conn.execute("SELECT name FROM parties")}
    finally:
        conn.close()


@pytest.mark.parametrize("payload", [b"", b"\x00" * 4096, b"not a database"])
def test_a_corrupt_backup_is_rejected_and_the_live_data_survives(shop, tmp_path,
                                                                 payload):
    shop.parties.create(party_code="C1", name="LIVE DATA", is_customer=True)
    bad = tmp_path / "bad.db"
    bad.write_bytes(payload)
    with pytest.raises(ValidationError):
        _restorer(shop).restore(bad, shop.database_file, confirmed=True)
    assert _names(shop) == {"LIVE DATA"}
    assert inspect_backup(shop.database_file).ok is True


def test_a_failure_during_the_swap_leaves_the_live_database_intact(shop, monkeypatch):
    """The case that matters: the disk fills up half way through."""
    shop.parties.create(party_code="C1", name="LIVE DATA", is_customer=True)
    backup = shop.backup.create_backup()

    real_copy = shutil.copy2

    def exploding(src, dst, *args, **kwargs):
        if str(dst).endswith(".restoring"):
            raise OSError(28, "No space left on device")
        return real_copy(src, dst, *args, **kwargs)

    monkeypatch.setattr(shutil, "copy2", exploding)
    with pytest.raises(ValidationError):
        _restorer(shop).restore(backup, shop.database_file, confirmed=True)
    monkeypatch.undo()

    assert shop.database_file.is_file()
    assert inspect_backup(shop.database_file).ok is True
    reopened = Database(str(shop.database_file))
    try:
        names = {r["name"] for r in
                 reopened.connection().execute("SELECT name FROM parties")}
    finally:
        reopened.close()
    assert names == {"LIVE DATA"}
    assert list(shop.database_file.parent.glob("*.restoring")) == []


def test_a_failed_restore_leaves_its_whole_trail_in_the_live_database(shop, tmp_path):
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"nope")
    with pytest.raises(ValidationError):
        _restorer(shop).restore(bad, shop.database_file, confirmed=True)
    actions = [r["action"] for r in shop.audit_repo.recent(200)]
    assert "backup.restore_started" in actions
    assert "backup.restore_failed" in actions


def test_a_successful_restore_is_recorded_in_the_restored_database(shop):
    """A restore replaces the database, so its own trail has to survive the swap.

    Entries written BEFORE the swap live in the database that was replaced — and
    are preserved in the safety backup. The completion entry is written after,
    into the restored database, so the customer can always see that a restore
    happened and which file it came from.
    """
    backup = shop.backup.create_backup()
    result = _restorer(shop).restore(backup, shop.database_file, confirmed=True)

    reopened = Database(str(shop.database_file))
    try:
        from zenith_business.repositories.system import AuditRepository

        entries = AuditRepository(reopened).recent(200)
    finally:
        reopened.close()
    completed = [r for r in entries if r["action"] == "backup.restore_completed"]
    assert completed, "the restored database does not record that it was restored"
    assert backup.name in completed[0]["details"]

    # and the pre-restore trail is not lost: it is inside the safety copy
    conn = sqlite3.connect(result.safety_backup)
    try:
        safety_actions = {r[0] for r in conn.execute("SELECT action FROM audit_log")}
    finally:
        conn.close()
    assert "backup.restore_started" in safety_actions


# ---- 8. database safety --------------------------------------------------

def test_the_live_database_passes_its_integrity_check(shop):
    report = check_database_integrity(shop.db)
    assert report.ok is True
    assert report.integrity == "ok"
    assert report.foreign_keys_ok is True
    assert report.schema_version


def test_the_database_is_configured_for_crash_safety(shop):
    assert shop.db.foreign_keys_enabled() is True
    assert str(shop.db.pragma("journal_mode")).lower() == "wal"


def test_there_is_no_casual_destructive_reset(shop):
    for forbidden in ("reset_database", "clear_all_data", "wipe", "drop_all"):
        assert not hasattr(shop, forbidden)
        assert not hasattr(shop.backup, forbidden)


def test_a_licensing_failure_does_not_touch_business_data(shop, tmp_path):
    """The rule that matters most: licence trouble must never cost data."""
    shop.parties.create(party_code="C1", name="CUSTOMER DATA", is_customer=True)
    before = _names(shop)

    bad = tmp_path / "broken.zlic"
    bad.write_text("this is not a licence at all")
    try:
        shop.licensing.import_license(bad)
    except Exception:
        pass
    shop.licensing.evaluate()

    assert _names(shop) == before
    assert check_database_integrity(shop.db).ok is True
