"""Stage 10 final pass: the gate, the demo clock, recovery, and backup passwords.

Every case here came from the owner testing the real Windows build, so each one
is written as the thing they saw or the thing they must now see instead. The
headline is that **licensing moved in front of login**: it used to be a screen
in Tools that an unlicensed installation could reach by way of the whole
workspace, which is not a gate.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from zenith_business.core.config import AppConfig, LANG_DARI, LANG_ENGLISH
from zenith_business.core.i18n import Translator
from zenith_business.database.connection import Database
from zenith_business.services.context import open_application_context
from zenith_business.services.licensing_service import (
    LicenseError,
    LicenseReason,
    LicenseStatus,
)

pytest.importorskip("cryptography", reason="test signing tooling only")
from tests.tooling.license_signing import (            # noqa: E402
    generate_keypair,
    make_license,
    tamper,
)

PASSWORD = "Str0ngPass!"
OTHER_PC = {"machine_guid": "guid-other", "volume_serial": "VOL-9999",
            "mac": "112233445566", "cpu": "x86_64|Intel|8", "hostname": "other-pc"}


@pytest.fixture(autouse=True)
def no_modal_dialogs(monkeypatch):
    """Answer every message box instead of blocking the test run on one.

    These screens report outcomes with QMessageBox, which is modal and waits for
    a human even under the offscreen platform. Silencing them here keeps the
    assertions about STATE rather than about which popup appeared.
    """
    from PyQt6.QtWidgets import QMessageBox

    for name in ("information", "warning", "critical", "question"):
        monkeypatch.setattr(QMessageBox, name,
                            staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))


@pytest.fixture
def shop(tmp_path):
    """A real on-disk installation with a vendor key, but NO licence yet."""
    database_file = tmp_path / "data" / "zenith.db"
    database_file.parent.mkdir(parents=True)
    db = Database(str(database_file))
    ctx = open_application_context(db, backups_dir=str(tmp_path / "backups"),
                                   license_dir=str(tmp_path / "license"))
    private, public = generate_keypair()
    ctx.licensing._explicit_key = public
    ctx.signing_key = private
    ctx.license_dir = tmp_path / "license"
    ctx.backups_dir = tmp_path / "backups"
    ctx.database_file = database_file
    ctx.setup.create_administrator(username="owner", password=PASSWORD,
                                   full_name="Owner", company_name="Kabul Traders Ltd")
    yield ctx
    db.close()


def _write_licence(ctx, *, license_type="FULL", expires_at=None, machine=None,
                   license_id=None, issued_at=None, install=True) -> str:
    me = machine or ctx.licensing.machine
    text = make_license(ctx.signing_key, machine_fingerprint=me.fingerprint,
                        machine_traits=me.traits, license_type=license_type,
                        license_id=license_id or f"ZB-{license_type}-000001",
                        issued_at=issued_at, expires_at=expires_at)
    if install:
        ctx.licensing.license_path.parent.mkdir(parents=True, exist_ok=True)
        ctx.licensing.license_path.write_text(text, encoding="utf-8")
    return text


def _window(ctx, language=LANG_ENGLISH):
    from zenith_business.ui.auth.auth_window import AuthWindow

    cfg = AppConfig()
    cfg.ui.language = language
    return AuthWindow(ctx, cfg)


def _rows(ctx) -> dict[str, int]:
    """A fingerprint of the customer's data, to prove licensing never touches it."""
    conn = ctx.db.connection()
    return {table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ("users", "audit_log", "parties", "items")}


# ==========================================================================
# 1. licensing is a PRE-LOGIN gate
# ==========================================================================

def test_an_unactivated_installation_stops_at_the_activation_screen(shop, qapp):
    window = _window(shop)
    try:
        assert window._stack.currentWidget() is window._activation_page
        assert window._stack.currentWidget() is not window._login_page
        assert window._stack.currentWidget() is not window._setup_page
        assert window.authenticated_user is None
    finally:
        window.deleteLater()


def test_an_unactivated_installation_cannot_sign_in_even_with_the_right_password(
        shop, qapp):
    """The gate is not just which page is drawn — the login path itself refuses."""
    window = _window(shop)
    try:
        window._handle_login("owner", PASSWORD)
        assert window.authenticated_user is None
        assert window._stack.currentWidget() is window._activation_page
    finally:
        window.deleteLater()


def test_a_valid_licence_lets_the_gate_reach_the_login_page(shop, qapp):
    _write_licence(shop)
    window = _window(shop)
    try:
        assert window._stack.currentWidget() is window._login_page
        window._handle_login("owner", PASSWORD)
        assert window.authenticated_user is not None
    finally:
        window.deleteLater()


def test_importing_a_licence_at_the_gate_moves_straight_on_to_login(
        shop, qapp, tmp_path, monkeypatch):
    incoming = tmp_path / "issued.zlic"
    incoming.write_text(_write_licence(shop, install=False))
    window = _window(shop)
    try:
        assert window._stack.currentWidget() is window._activation_page
        _accept_file(monkeypatch, incoming)
        window._handle_import_license()
        assert window._stack.currentWidget() is window._login_page
        assert shop.licensing.evaluate().status == LicenseStatus.FULL
    finally:
        window.deleteLater()


def _accept_file(monkeypatch, path: Path, *, save: bool = False):
    """Make the file dialog answer with ``path`` instead of opening."""
    from PyQt6.QtWidgets import QFileDialog

    name = "getSaveFileName" if save else "getOpenFileName"
    monkeypatch.setattr(QFileDialog, name,
                        staticmethod(lambda *a, **k: (str(path), "")))


@pytest.mark.parametrize("make, expect_reason", [
    ("wrong_machine", LicenseReason.WRONG_MACHINE),
    ("altered", LicenseReason.BAD_SIGNATURE),
    ("expired", LicenseReason.EXPIRED),
])
def test_a_licence_that_cannot_be_trusted_lands_on_activation(
        shop, qapp, make, expect_reason):
    from zenith_business.security import machine_id as machine
    from zenith_business.security.license_format import PRODUCT_ID

    if make == "wrong_machine":
        _write_licence(shop, machine=machine.collect(PRODUCT_ID, overrides=OTHER_PC))
    elif make == "altered":
        text = _write_licence(shop, install=False)
        shop.licensing.license_path.parent.mkdir(parents=True, exist_ok=True)
        shop.licensing.license_path.write_text(
            tamper(text, "license_id", "ZB-FULL-999999"))
    else:
        _write_licence(shop, expires_at=(date.today() - timedelta(days=1)).isoformat())

    state = shop.licensing.evaluate()
    assert state.reason == expect_reason
    assert state.allows_login is False
    window = _window(shop)
    try:
        assert window._stack.currentWidget() is window._activation_page
        # The screen explains THIS failure, not a generic "invalid".
        assert window._activation_page._error.text()
    finally:
        window.deleteLater()


def test_a_failed_licence_never_touches_customer_data(shop, qapp):
    before = _rows(shop)
    for text in ("", "{}", '{"format":"zenith-license-1"}'):
        shop.licensing.license_path.parent.mkdir(parents=True, exist_ok=True)
        shop.licensing.license_path.write_text(text)
        assert shop.licensing.evaluate().allows_login is False
        window = _window(shop)
        window.deleteLater()
    assert _rows(shop) == before
    assert shop.database_file.is_file()


def test_the_licence_is_re_checked_on_every_startup(shop, qapp):
    _write_licence(shop)
    first = _window(shop)
    assert first._stack.currentWidget() is first._login_page
    first.deleteLater()

    shop.licensing.license_path.unlink()          # e.g. the folder was cleaned out
    second = _window(shop)
    try:
        assert second._stack.currentWidget() is second._activation_page
    finally:
        second.deleteLater()


def test_the_activation_screen_shows_what_the_vendor_needs(shop, qapp):
    window = _window(shop)
    try:
        page = window._activation_page
        assert page._machine_id.text() == shop.licensing.machine.short
        # A paste box for the key, and the button that uses it.
        assert page.key_input.placeholderText()
        assert page.activate_btn.text() == "Activate"
        assert page._copy_btn.text() == "Copy Request Code"
        # The file route still exists, but folded away.
        assert page._advanced.isVisible() is False
    finally:
        window.deleteLater()


def test_the_activation_screen_speaks_dari(shop, qapp):
    window = _window(shop, LANG_DARI)
    try:
        page = window._activation_page
        assert "فعال" in page._title.text()
        assert "کلید محصول" in page._key_caption.text()
        assert "کاپی" in page._copy_btn.text()
        assert "Copy Request Code" not in page._copy_btn.text()
    finally:
        window.deleteLater()


def test_the_workspace_returns_to_activation_when_the_licence_lapses(shop, qapp):
    """Expiry must bite while the program is OPEN, not only at the next start."""
    from zenith_business.ui.main_window import MainWindow

    _write_licence(shop, license_type="DEMO",
                   expires_at=(date.today() + timedelta(days=5)).isoformat())
    user = shop.auth.login("owner", PASSWORD)
    lapsed = {"called": False}
    window = MainWindow(AppConfig(), database=shop.db, current_user=user,
                        on_license_lapsed=lambda: lapsed.update(called=True),
                        context=shop)
    try:
        assert window._license_watch is not None
        window._check_license_still_valid()
        assert lapsed["called"] is False          # still inside the demo

        shop.licensing.license_path.unlink()      # the licence goes away
        window._check_license_still_valid()
        assert lapsed["called"] is True
        assert _rows(shop)["users"] >= 1          # and the data is still there
    finally:
        window.deleteLater()


# ==========================================================================
# 2. the demo clock
# ==========================================================================

def _clock(shop):
    return shop.licensing.clock


#: The mark is stored to whole seconds, so a comparison against a value with
#: microseconds has to allow for that truncation — it is the format, not drift.
_TRUNCATION = timedelta(seconds=1)


def test_moving_the_clock_back_does_not_buy_more_demo_time(shop):
    _write_licence(shop, license_type="DEMO",
                   expires_at=(date.today() + timedelta(days=3)).isoformat())
    assert shop.licensing.evaluate().status == LicenseStatus.DEMO

    # The installation has now seen "today". Pretend Windows is set back a month.
    seen = datetime.now(timezone.utc) + timedelta(days=10)
    _clock(shop).observe(seen)
    reading = _clock(shop).read()
    assert reading.rolled_back is True
    assert reading.now >= seen - _TRUNCATION
    # 10 days on, a 3-day demo is over — and moving the clock back did not help.
    assert shop.licensing.evaluate().status == LicenseStatus.DEMO_EXPIRED


def test_the_high_water_mark_only_ever_moves_forward(shop):
    clock = _clock(shop)
    ahead = datetime.now(timezone.utc) + timedelta(days=5)
    clock.observe(ahead)
    clock.observe(datetime.now(timezone.utc) - timedelta(days=30))
    assert clock.high_water() >= ahead - _TRUNCATION


def test_deleting_the_clock_file_does_not_reset_it(shop):
    clock = _clock(shop)
    ahead = datetime.now(timezone.utc) + timedelta(days=7)
    clock.observe(ahead)
    assert clock.state_path.is_file()
    clock.state_path.unlink()
    # The mirror inside the database still remembers.
    assert clock.high_water() >= ahead - _TRUNCATION


def test_an_edited_clock_file_is_not_believed(shop):
    clock = _clock(shop)
    clock.observe(datetime.now(timezone.utc) + timedelta(days=7))
    clock.state_path.write_bytes(b"DPAPI1\x00nonsense")
    # Ignored rather than trusted; the settings mirror carries the truth.
    assert clock.high_water() is not None


def test_a_signed_issue_date_is_a_floor_no_clock_can_get_under(shop):
    """Even with every stored mark gone, a licence cannot be used before issue."""
    issued = (date.today() + timedelta(days=30)).isoformat()
    _write_licence(shop, license_type="DEMO", issued_at=issued,
                   expires_at=(date.today() + timedelta(days=31)).isoformat())
    state = shop.licensing.evaluate()
    clock = _clock(shop)
    clock.state_path.unlink(missing_ok=True)
    clock.set_floor(issued)
    assert clock.high_water() is not None
    assert clock.read().now >= datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert state.status in (LicenseStatus.DEMO, LicenseStatus.DEMO_EXPIRED)


def test_a_demo_cannot_be_restarted_by_deleting_application_files(shop):
    """A demo is a signed file now, so removing it un-licenses rather than renews."""
    _write_licence(shop, license_type="DEMO",
                   expires_at=(date.today() + timedelta(days=1)).isoformat())
    assert shop.licensing.evaluate().status == LicenseStatus.DEMO
    shop.licensing.license_path.unlink()
    assert shop.licensing.evaluate().status == LicenseStatus.UNLICENSED


# ==========================================================================
# 4. recovery the owner can actually reach
# ==========================================================================

def test_the_login_screen_offers_a_way_back_in(shop, qapp):
    _write_licence(shop)
    window = _window(shop)
    try:
        assert window._login_page.forgot.isVisibleTo(window._login_page)
        assert window._login_page.forgot.text() == "Forgot your password?"
    finally:
        window.deleteLater()


def test_the_forgot_link_is_translated(shop, qapp):
    _write_licence(shop)
    window = _window(shop, LANG_DARI)
    try:
        assert "فراموش" in window._login_page.forgot.text()
    finally:
        window.deleteLater()


def test_a_recovery_code_resets_the_password_and_clears_the_lockout(shop, qapp):
    from zenith_business.services.authentication import MAX_FAILED_ATTEMPTS
    from zenith_business.services.exceptions import AuthenticationError
    from zenith_business.ui.auth.recovery_dialog import RecoveryDialog

    shop.auth.login("owner", PASSWORD)
    code = shop.security.issue_recovery_code(current_password=PASSWORD)
    shop.auth.logout()
    for _ in range(MAX_FAILED_ATTEMPTS):
        with pytest.raises(AuthenticationError):
            shop.auth.authenticate("owner", "wrong")
    assert shop.security.guard_state("owner").is_locked is True

    dialog = RecoveryDialog(shop, Translator(LANG_ENGLISH), username="owner")
    dialog._code.setText(code)
    dialog._password.edit.setText("Rec0veredPass!")
    dialog._confirm.edit.setText("Rec0veredPass!")
    dialog._submit()
    assert dialog.recovered_username == "owner"
    assert shop.security.guard_state("owner").is_locked is False
    assert shop.auth.authenticate("owner", "Rec0veredPass!") is not None


def test_a_recovery_code_cannot_be_used_twice(shop, qapp):
    from zenith_business.ui.auth.recovery_dialog import RecoveryDialog

    shop.auth.login("owner", PASSWORD)
    code = shop.security.issue_recovery_code(current_password=PASSWORD)
    shop.security.recover_with_code(username="owner", recovery_code=code,
                                    new_password="Rec0veredPass!")
    dialog = RecoveryDialog(shop, Translator(LANG_ENGLISH), username="owner")
    dialog._code.setText(code)
    dialog._password.edit.setText("An0therTry!")
    dialog._confirm.edit.setText("An0therTry!")
    dialog._submit()
    assert dialog.recovered_username is None
    assert dialog._error.isVisible() or dialog._error.text()


def test_a_wrong_recovery_code_says_nothing_useful(shop, qapp):
    from zenith_business.ui.auth.recovery_dialog import RecoveryDialog

    shop.auth.login("owner", PASSWORD)
    shop.security.issue_recovery_code(current_password=PASSWORD)
    dialog = RecoveryDialog(shop, Translator(LANG_ENGLISH), username="owner")
    dialog._code.setText("AAAAA-BBBBB-CCCCC-DDDDD")
    dialog._password.edit.setText("An0therTry!")
    dialog._confirm.edit.setText("An0therTry!")
    dialog._submit()
    assert dialog.recovered_username is None
    assert "not correct" in dialog._error.text()


def test_my_account_issues_a_code_once_and_never_shows_it_again(shop, qapp):
    from zenith_business.ui.documents.account_settings_page import AccountSettingsPage

    shop.auth.login("owner", PASSWORD)
    page = AccountSettingsPage(shop, Translator(LANG_ENGLISH))
    try:
        page._rc_current.setText(PASSWORD)
        page._issue_recovery_code()
        shown = page._rc_value.text()
        assert shown and page._rc_value.isVisibleTo(page)
        # Only the hash is stored, so nothing can print it back.
        stored = shop.settings_repo.get("security.recovery_code_hash")
        assert stored and shown not in stored
        assert shop.security.has_recovery_code() is True
    finally:
        page.deleteLater()


def test_issuing_a_code_needs_the_current_password(shop, qapp):
    from zenith_business.ui.documents.account_settings_page import AccountSettingsPage

    shop.auth.login("owner", PASSWORD)
    page = AccountSettingsPage(shop, Translator(LANG_ENGLISH))
    try:
        page._rc_current.setText("not-the-password")
        page._issue_recovery_code()
        assert page._rc_value.isVisibleTo(page) is False
        assert shop.security.has_recovery_code() is False
    finally:
        page.deleteLater()


# ==========================================================================
# 5. the backup password, and the Persian-keyboard inconsistency
# ==========================================================================

#: What the physical keys of "Str0ngPass!" produce under a Persian layout.
PERSIAN_LAYOUT = "ش/۰هلبحشسس!"


def _backup_page(shop, language=LANG_ENGLISH):
    from zenith_business.ui.documents.security_pages import BackupPage

    return BackupPage(shop, Translator(language),
                      database_path=str(shop.database_file))


def test_a_backup_cannot_be_locked_with_a_password_that_is_not_the_owners(
        shop, qapp, monkeypatch):
    """The defect behind the Windows inconsistency, stated as a rule.

    A backup used to be encrypted with whatever was typed. Typing the English
    password's keys under a Persian layout produced a Persian string, so the
    file was locked with something the owner never chose — which then passed
    Check Backup (it WAS the passphrase) and failed Restore (which also checks
    the real account password).
    """
    shop.auth.login("owner", PASSWORD)
    page = _backup_page(shop)
    try:
        monkeypatch.setattr(page, "_ask_passphrase",
                            lambda *a, **k: PERSIAN_LAYOUT)
        page._create_backup()
        made = list(shop.backups_dir.glob("zenith-backup-*")) if shop.backups_dir.is_dir() else []
        assert made == [], "a backup was written with a passphrase nobody chose"
        assert "not your current password" in page._status.text()
    finally:
        page.deleteLater()


def test_a_backup_made_with_the_owner_password_opens_with_it(shop, qapp, monkeypatch):
    shop.auth.login("owner", PASSWORD)
    page = _backup_page(shop)
    try:
        monkeypatch.setattr(page, "_ask_passphrase", lambda *a, **k: PASSWORD)
        page._create_backup()
        made = sorted(shop.backups_dir.glob("zenith-backup-*.zbak"))
        assert len(made) == 1
        assert shop.safe_restore.inspect(made[0], passphrase=PASSWORD).ok is True
    finally:
        page.deleteLater()


@pytest.mark.parametrize("attempt, expect", [
    (PASSWORD, True),
    (PASSWORD + "x", False),            # one character different
    (PASSWORD.lower(), False),          # one case different
    (PERSIAN_LAYOUT, False),            # the same physical keys, other layout
    ("", False),
])
def test_only_the_exact_characters_open_a_backup(shop, attempt, expect):
    shop.auth.login("owner", PASSWORD)
    path = shop.backup.create_backup(passphrase=PASSWORD)
    assert shop.safe_restore.inspect(path, passphrase=attempt).ok is expect


def test_a_passphrase_is_taken_exactly_as_typed_in_any_script(shop):
    """No layout translation, no normalisation — including for Persian text."""
    shop.auth.login("owner", PASSWORD)
    persian = "رمزعبور۱۲۳"
    path = shop.backup.create_backup(passphrase=persian)
    assert shop.safe_restore.inspect(path, passphrase=persian).ok is True
    assert shop.safe_restore.inspect(path, passphrase="رمزعبور۱۲۴").ok is False


# ==========================================================================
# 6. the safety copy taken before a restore
# ==========================================================================

def test_the_pre_restore_safety_copy_is_not_a_readable_database(shop, qapp):
    from zenith_business.security import backup_crypto

    shop.auth.login("owner", PASSWORD)
    backup = shop.backup.create_backup(passphrase=PASSWORD)
    result = shop.safe_restore.restore(backup, shop.database_file, confirmed=True,
                                       passphrase=PASSWORD, safety_passphrase=PASSWORD)
    safety = result.safety_backup
    assert safety is not None and safety.suffix == ".zbak"
    assert backup_crypto.looks_encrypted(safety) is True
    # The customer's rows are not sitting there in the clear.
    assert b"Kabul Traders" not in safety.read_bytes()
    # And it still opens with the owner password, so it is a real safety net.
    assert shop.safe_restore.inspect(safety, passphrase=PASSWORD).ok is True


def test_a_failed_restore_puts_back_an_encrypted_safety_copy(shop, qapp, tmp_path):
    """Rollback has to survive the safety copy being a container, not a .db."""
    shop.auth.login("owner", PASSWORD)
    before = _rows(shop)
    good = shop.backup.create_backup(passphrase=PASSWORD)

    original = shop.safe_restore._sweep_stale_journals
    from zenith_business.services import safe_restore as module

    real_inspect = module.inspect_backup
    calls = {"n": 0}

    def failing_inspect(path, *, passphrase=None):
        # Fail the AFTER-restore verification only, which is the path that rolls back.
        calls["n"] += 1
        result = real_inspect(path, passphrase=passphrase)
        if calls["n"] >= 2 and Path(path) == Path(shop.database_file):
            return module.BackupCheck(False, "corrupt", "simulated failure")
        return result

    module.inspect_backup = failing_inspect
    try:
        from zenith_business.services.exceptions import ValidationError

        with pytest.raises(ValidationError):
            shop.safe_restore.restore(good, shop.database_file, confirmed=True,
                                      passphrase=PASSWORD, safety_passphrase=PASSWORD)
    finally:
        module.inspect_backup = real_inspect
        shop.safe_restore._sweep_stale_journals = original

    reopened = Database(str(shop.database_file))
    try:
        ctx = open_application_context(reopened, backups_dir=str(shop.backups_dir))
        restored = _rows(ctx)
        # The BUSINESS data is exactly what it was. The audit log legitimately
        # holds more, because the attempt itself is recorded — the safety copy
        # was taken after "restore started" was written, and putting it back
        # brings that entry with it. A restore that erased its own trail would
        # be the wrong outcome.
        for table in ("users", "parties", "items"):
            assert restored[table] == before[table], f"{table} was not put back"
        assert restored["audit_log"] >= before["audit_log"]
        from zenith_business.services.safe_restore import check_database_integrity

        assert check_database_integrity(reopened).ok is True
    finally:
        reopened.close()


# ==========================================================================
# 7. what a refused backup says to a customer
# ==========================================================================

def test_an_authentication_failure_names_all_three_causes(shop, qapp):
    page = _backup_page(shop)
    try:
        from zenith_business.services.safe_restore import BackupCheck

        text = page._refusal(BackupCheck(False, "bad_passphrase", "x"))
        assert "bad_passphrase" not in text
        assert "password may be incorrect" in text
        assert "damaged or modified" in text
    finally:
        page.deleteLater()


def test_the_same_message_exists_in_dari(shop, qapp):
    page = _backup_page(shop, LANG_DARI)
    try:
        from zenith_business.services.safe_restore import BackupCheck

        text = page._refusal(BackupCheck(False, "bad_passphrase", "x"))
        assert "رمز" in text and "تغییر" in text
        assert "bad_passphrase" not in text
    finally:
        page.deleteLater()


def test_an_unknown_reason_still_says_something(shop, qapp):
    page = _backup_page(shop)
    try:
        from zenith_business.services.safe_restore import BackupCheck

        assert page._refusal(BackupCheck(False, "something_new", "detail here"))
    finally:
        page.deleteLater()


# ==========================================================================
# 9. one source of truth for licence state
# ==========================================================================

def test_every_screen_agrees_about_a_full_licence(shop, qapp):
    from zenith_business.ui.documents.security_pages import LicensePage

    _write_licence(shop, license_id="ZB-FULL-000007")
    shop.auth.login("owner", PASSWORD)
    window = _window(shop)
    page = LicensePage(shop, Translator(LANG_ENGLISH))
    try:
        summary = shop.licensing.summary()
        assert "DEMO" not in summary.upper()
        assert "ZB-FULL-000007" in summary
        assert "ZB-FULL-000007" in window._version_text()
        assert page._keys["status"].text() == "Activated"
        assert page._keys["license_id"].text() == "ZB-FULL-000007"
        assert "DEMO" not in page._keys["license_type"].text().upper()
    finally:
        page.deleteLater()
        window.deleteLater()


def test_the_licence_page_does_not_promise_never_when_there_is_no_licence(shop, qapp):
    from zenith_business.ui.documents.security_pages import LicensePage

    page = LicensePage(shop, Translator(LANG_ENGLISH))
    try:
        assert page._keys["expires"].text() == "—"
        assert page._keys["status"].text() == "Not activated"
    finally:
        page.deleteLater()


def test_a_demo_shows_its_real_expiry_everywhere(shop, qapp):
    from zenith_business.ui.documents.security_pages import LicensePage

    expires = (date.today() + timedelta(days=9)).isoformat()
    _write_licence(shop, license_type="DEMO", expires_at=expires)
    page = LicensePage(shop, Translator(LANG_ENGLISH))
    try:
        assert page._keys["expires"].text() == expires
        assert "9 day" in shop.licensing.summary()
    finally:
        page.deleteLater()


# ==========================================================================
# 10. what goes into an activation request
# ==========================================================================

def test_the_request_carries_the_customers_own_business_name(shop, tmp_path):
    path = shop.licensing.create_activation_request(tmp_path / "out")
    import json

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["business_name"] == "Kabul Traders Ltd"
    assert document["product_id"] == "ZENITH-BUSINESS"
    assert document["machine"]["fingerprint"] == shop.licensing.machine.fingerprint


def test_an_unconfigured_business_name_is_left_blank_not_invented(tmp_path):
    """Never a sample name, and never the product's own name."""
    import json

    db = Database(str(tmp_path / "fresh.db"))
    ctx = open_application_context(db, backups_dir=str(tmp_path / "b"),
                                   license_dir=str(tmp_path / "l"))
    try:
        assert ctx.licensing.business_name() == ""
        path = ctx.licensing.create_activation_request(tmp_path / "out")
        document = json.loads(path.read_text(encoding="utf-8"))
        assert document["business_name"] == ""
        assert "Zenith Business" not in path.read_text(encoding="utf-8")
    finally:
        db.close()


def test_the_request_still_exposes_no_raw_hardware_identifier(shop, tmp_path):
    import platform
    import uuid

    path = shop.licensing.create_activation_request(tmp_path / "out")
    text = path.read_text(encoding="utf-8")
    for raw in (platform.node(), platform.machine(), f"{uuid.getnode():012x}"):
        if raw:
            assert raw not in text


def test_the_request_contains_no_password_or_key_material(shop, tmp_path):
    path = shop.licensing.create_activation_request(tmp_path / "out")
    text = path.read_text(encoding="utf-8").lower()
    for forbidden in ("password", "private", "secret", "pbkdf2", "signature"):
        assert forbidden not in text


# ==========================================================================
# 11. nothing that already worked was given away
# ==========================================================================

def test_a_wrong_machine_licence_is_still_refused_on_import(shop, tmp_path):
    from zenith_business.security import machine_id as machine
    from zenith_business.security.license_format import PRODUCT_ID

    other = machine.collect(PRODUCT_ID, overrides=OTHER_PC)
    path = tmp_path / "other.zlic"
    path.write_text(_write_licence(shop, machine=other, install=False))
    with pytest.raises(LicenseError):
        shop.licensing.import_license(path)
    assert not shop.licensing.license_path.exists()


def test_the_application_still_cannot_sign_anything(shop):
    """The rule that must survive every change to this area."""
    import zenith_business

    root = Path(zenith_business.__file__).parent
    for module in root.rglob("*.py"):
        text = module.read_text(encoding="utf-8")
        assert "Ed25519PrivateKey" not in text, f"{module} can sign"
        assert "private_bytes" not in text, f"{module} handles a private key"


def test_a_tampered_backup_is_still_refused(shop):
    shop.auth.login("owner", PASSWORD)
    path = shop.backup.create_backup(passphrase=PASSWORD)
    raw = bytearray(path.read_bytes())
    raw[-1] ^= 0xFF
    path.write_bytes(bytes(raw))
    check = shop.safe_restore.inspect(path, passphrase=PASSWORD)
    assert check.ok is False
    assert check.reason == "bad_passphrase"


def test_the_audit_chain_still_detects_an_edited_row(shop):
    shop.auth.login("owner", PASSWORD)
    shop.audit_chain.seal()
    assert shop.audit_chain.verify().ok is True
    with shop.db.transaction() as tx:
        tx.execute("UPDATE audit_log SET details = 'edited' WHERE id ="
                   " (SELECT MIN(id) FROM audit_log WHERE entry_hash IS NOT NULL)")
    report = shop.audit_chain.verify()
    assert report.ok is False
    assert report.first_bad_id is not None


def test_the_licence_line_is_translated_not_left_in_english(shop, qapp):
    """One source of truth is the STATUS; the wording still has to be Dari."""
    from zenith_business.ui.components import license_summary

    _write_licence(shop, license_type="DEMO",
                   expires_at=(date.today() + timedelta(days=4)).isoformat())
    state = shop.licensing.evaluate()
    english = license_summary(Translator(LANG_ENGLISH), state)
    dari = license_summary(Translator(LANG_DARI), state)
    assert "day(s) left" in english and "4" in english
    assert "روز" in dari and "4" in dari
    assert english != dari

    window = _window(shop, LANG_DARI)
    try:
        assert "روز" in window._version_text()
        assert "day(s) left" not in window._version_text()
    finally:
        window.deleteLater()


def test_every_licence_state_has_a_dari_sentence(shop, qapp):
    from zenith_business.ui.components import license_summary

    class _State:
        def __init__(self, status):
            self.status = status
            self.license_id = ""
            self.demo_days_left = None

    for status in ("FULL", "DEMO", "DEMO_EXPIRED", "UNLICENSED",
                   "NO_VENDOR_KEY", "INVALID"):
        text = license_summary(Translator(LANG_DARI), _State(status))
        assert text and not text.startswith("lic."), f"{status} has no Dari wording"
        assert text.isascii() is False, f"{status} fell back to English"


# ==========================================================================
# 12. what the package may contain, checked before the build finds out
# ==========================================================================

#: Files the packaging step copies into dist/package verbatim, alongside the
#: frozen application and the seeded database.
_SHIPPED_EXTRAS = ("packaging/Run-ZenithBusiness.bat",
                   "packaging/Reset-Test-Data.bat",
                   "packaging/READ-ME-FIRST.md")


def _repo_root() -> Path:
    import zenith_business

    return Path(zenith_business.__file__).parent.parent


def test_nothing_that_ships_names_the_vendor_tool():
    """A customer package must not document the vendor tool, let alone carry it.

    The release auditor already fails the build on this, and it did — on a note
    added to READ-ME-FIRST telling the owner how to generate a signing key. The
    rule was right: that file ships to customers. This catches it in seconds
    instead of four minutes into a Windows build.
    """
    root = _repo_root()
    targets = [root / name for name in _SHIPPED_EXTRAS]
    targets += list((root / "zenith_business").rglob("*.py"))
    for path in targets:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        assert "zenith_license_tool" not in text, f"{path} names the vendor tool"
        assert "license_signing" not in text, f"{path} names the test signing tooling"


def test_the_verbatim_shipped_files_pass_the_release_auditors_own_rules():
    """Apply the auditor's hard rules to the files it will actually read as text.

    Scope matters here, and getting it wrong is what this docstring is for. The
    three files below are copied into the package byte for byte, so the rules
    apply to them exactly as the auditor will apply them. Our ``.py`` modules
    are NOT in that category: PyInstaller zlib-compresses them into the archive,
    so their strings are invisible to a byte scan — which is why
    ``license_format.py`` may show the licence-file shape in its own docstring
    without that ever reaching the package as readable text.
    """
    import importlib.util

    root = _repo_root()
    spec = importlib.util.spec_from_file_location(
        "audit_release_package", root / "packaging" / "audit_release_package.py")
    auditor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(auditor)

    for name in _SHIPPED_EXTRAS:
        path = root / name
        assert path.is_file(), f"{name} is listed as shipped but does not exist"
        data = path.read_bytes()
        for label, pattern, why in auditor.FORBIDDEN:
            assert not pattern.search(data), f"{path}: {label} — {why}"


# ==========================================================================
# 13. typography must not drift
# ==========================================================================

def test_the_stylesheet_declares_exactly_one_font_family():
    """Dari typography is pinned to the bundled Vazirmatn. It stays pinned.

    A Stage 10 recovery-code label briefly set a monospace family of its own.
    Two things were wrong with it: it was the only font-family override in the
    application, and Consolas and Courier New carry no Persian glyphs — so a
    Dari screen would have fallen back to whatever Windows picked, which is the
    silent substitution Stage 08 went to trouble to stop.
    """
    import re

    from zenith_business.ui.design.theme import build_stylesheet
    from zenith_business.ui.design.tokens import Typography

    families = re.findall(r"font-family:\s*([^;]+);", build_stylesheet())
    assert families, "the base rule must still set a font family"
    for declared in families:
        assert declared.strip() == Typography.FAMILY.strip(), (
            f"{declared.strip()!r} is not the bundled family stack")


def test_the_bundled_family_still_leads_the_stack():
    from zenith_business.core.fonts import FONT_FAMILY
    from zenith_business.ui.design.tokens import Typography

    assert Typography.FAMILY.strip().startswith(f'"{FONT_FAMILY}"')


def test_no_screen_hard_codes_a_font_family():
    """Print sheets may pass a family through, but never a literal name."""
    root = _repo_root() / "zenith_business"
    allowed = ("{t.FAMILY}", "{Typography.FAMILY}", "{family}", "{FONT_FAMILY}")
    for path in root.rglob("*.py"):
        for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1):
            # A real declaration, not prose that happens to use the word: the
            # property starts the line and the value is terminated.
            stripped = line.strip()
            if not stripped.startswith("font-family:") or ";" not in stripped:
                continue
            assert any(token in stripped for token in allowed), (
                f"{path}:{number} hard-codes a font family: {stripped}")


# ==========================================================================
# 14. copy / send / paste / activate — the Product Key workflow
# ==========================================================================

def _issue_key(shop, *, license_type="FULL", days=None, serial=42,
               issued_to="Kabul Traders Ltd", request=None):
    """Do what the vendor tool does: sign the packed payload. Tests only."""
    from datetime import date as _date

    from tests.tooling.license_signing import sign
    from zenith_business.security import product_key

    code = request or shop.licensing.request_code()
    decoded = product_key.decode_request(code)
    expires = None
    if days is not None:
        expires = (_date.today() + timedelta(days=days)).isoformat()
    payload = product_key.build_license_payload(
        license_type=license_type, fingerprint=decoded.fingerprint,
        traits=decoded.traits, issued_at=_date.today().isoformat(),
        expires_at=expires, serial=serial, issued_to=issued_to)
    return product_key.encode_license(payload, sign(shop.signing_key, payload))


def test_the_request_code_round_trips_through_text(shop):
    from zenith_business.security import product_key

    code = shop.licensing.request_code()
    assert code.startswith("ZBR1-")
    decoded = product_key.decode_request(code)
    assert decoded.fingerprint == shop.licensing.machine.fingerprint
    assert decoded.traits == {k: v[:8] for k, v in
                              shop.licensing.machine.traits.items()}
    assert decoded.machine_short == shop.licensing.machine.short


def test_a_request_code_survives_being_messed_about_in_a_message(shop):
    """Line breaks, spaces and lower case are what a pasted code looks like."""
    from zenith_business.security import product_key

    code = shop.licensing.request_code()
    for mangled in (code.lower(),
                    # what a message client does: wraps, indents, adds spaces
                    code[:40] + "\n" + code[40:],
                    f"  {code}  ",
                    code.replace("-", " - "),
                    # and a reflow that swallowed the separator after the prefix
                    code.replace("ZBR1-", "ZBR1")):
        assert product_key.decode_request(mangled).fingerprint == \
            shop.licensing.machine.fingerprint


def test_a_request_code_with_a_wrong_character_is_caught_not_guessed(shop):
    """The vendor must not issue a licence against a mangled machine id."""
    from zenith_business.security import product_key

    code = shop.licensing.request_code()
    broken = code[:-4] + ("Q" if code[-4] != "Q" else "R") + code[-3:]
    with pytest.raises(product_key.ProductKeyError):
        product_key.decode_request(broken)


def test_pasting_a_product_key_activates_and_opens_the_login_page(shop, qapp):
    window = _window(shop)
    try:
        assert window._stack.currentWidget() is window._activation_page
        window._activation_page.key_input.setPlainText(_issue_key(shop))
        window._activation_page.activate_btn.click()
        assert shop.licensing.evaluate().status == LicenseStatus.FULL
        assert window._stack.currentWidget() is window._login_page
        window._handle_login("owner", PASSWORD)
        assert window.authenticated_user is not None
    finally:
        window.deleteLater()


def test_a_pasted_key_survives_a_restart(shop):
    shop.licensing.import_product_key(_issue_key(shop, serial=7))
    fresh_dir = shop.licensing.license_path.parent
    from zenith_business.services.licensing_service import LicenseService

    fresh = LicenseService(license_dir=fresh_dir,
                           public_key=shop.licensing._explicit_key)
    state = fresh.evaluate()
    assert state.status == LicenseStatus.FULL
    assert state.license_id == "ZB-FULL-000007"


def test_a_demo_product_key_carries_the_vendors_chosen_length(shop):
    """DEMO days are the vendor's decision; the customer app only reads them."""
    state = shop.licensing.import_product_key(
        _issue_key(shop, license_type="DEMO", days=14, serial=3))
    assert state.status == LicenseStatus.DEMO
    assert state.license_type == "DEMO"
    assert state.demo_days_left == 14
    assert state.license_id == "ZB-DEMO-000003"
    assert state.issued_to == "Kabul Traders Ltd"


@pytest.mark.parametrize("days, expect", [(7, 7), (14, 14), (15, 15), (30, 30)])
def test_every_demo_length_the_vendor_can_pick_is_carried_exactly(shop, days, expect):
    state = shop.licensing.import_product_key(
        _issue_key(shop, license_type="DEMO", days=days))
    assert state.demo_days_left == expect


def test_an_expired_demo_key_is_refused_on_paste(shop):
    with pytest.raises(LicenseError):
        shop.licensing.import_product_key(
            _issue_key(shop, license_type="DEMO", days=-2))
    assert shop.licensing.evaluate().status == LicenseStatus.UNLICENSED


def test_a_product_key_for_another_computer_is_refused(shop):
    from zenith_business.security import machine_id as machine
    from zenith_business.security import product_key
    from zenith_business.security.license_format import PRODUCT_ID

    other = machine.collect(PRODUCT_ID, overrides=OTHER_PC)
    foreign_request = product_key.encode_request(
        fingerprint=other.fingerprint, traits=other.traits)
    key = _issue_key(shop, request=foreign_request)
    with pytest.raises(LicenseError):
        shop.licensing.import_product_key(key)
    assert shop.licensing.evaluate().status == LicenseStatus.UNLICENSED


@pytest.mark.parametrize("position", [0, 40, 120, -80, -20, -2])
def test_changing_any_character_of_a_product_key_invalidates_it(shop, position):
    key = _issue_key(shop)
    index = position if position >= 0 else len(key) + position
    while key[index] == "-":
        index += 1
    replacement = "A" if key[index] != "A" else "B"
    broken = key[:index] + replacement + key[index + 1:]
    with pytest.raises(LicenseError):
        shop.licensing.import_product_key(broken)
    assert shop.licensing.evaluate().status == LicenseStatus.UNLICENSED


def test_the_very_last_character_can_carry_unused_bits(shop):
    """A true property of base32, worth stating rather than discovering later.

    The payload length is not a multiple of five bytes, so the final base32
    character holds a few bits that decode to nothing. Changing only those bits
    yields the SAME payload, so the key still activates — which is correct, not
    a hole: the signature covers the decoded bytes, and an attacker gains
    nothing from a key that decodes to the licence they already had. It is
    recorded here so nobody later reads it as tampering that slipped through.
    """
    from zenith_business.security import product_key

    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
    key = _issue_key(shop)
    original = product_key.decode_license(key)

    # The payload is 129 bytes, so the final character carries 2 real bits in
    # its HIGH positions and 3 dead ones below. Which characters are equivalent
    # therefore depends on the signature, and must be computed, not guessed —
    # a fixed list of letters made this test pass or fail with the random key.
    value = alphabet.index(key[-1])
    same_bits = [c for c in alphabet
                 if alphabet.index(c) >> 3 == value >> 3 and c != key[-1]]
    other_bits = [c for c in alphabet if alphabet.index(c) >> 3 != value >> 3]
    assert same_bits and other_bits

    for replacement in same_bits:
        decoded = product_key.decode_license(key[:-1] + replacement)
        assert decoded.signed_bytes == original.signed_bytes
        assert decoded.signature == original.signature

    for replacement in other_bits[:4]:
        # Real bits moved, so this is a different licence and must be refused.
        with pytest.raises(LicenseError):
            shop.licensing.import_product_key(key[:-1] + replacement)
    assert shop.licensing.evaluate().status == LicenseStatus.UNLICENSED


def test_a_truncated_paste_is_refused_with_a_clear_reason(shop):
    key = _issue_key(shop)
    with pytest.raises(LicenseError) as caught:
        shop.licensing.import_product_key(key[:len(key) // 2])
    assert "damaged" in caught.value.user_message or \
           "incomplete" in caught.value.user_message


def test_pasting_the_request_code_back_says_so_plainly(shop):
    """The single most likely customer mistake gets its own sentence."""
    with pytest.raises(LicenseError) as caught:
        shop.licensing.import_product_key(shop.licensing.request_code())
    message = caught.value.user_message
    assert "request code" in message
    assert "ZB1-" in message
    assert "JSON" not in message


def test_pasting_nonsense_does_not_talk_about_json(shop):
    with pytest.raises(LicenseError) as caught:
        shop.licensing.import_product_key("hello there")
    assert "JSON" not in caught.value.user_message
    assert "ZB1-" in caught.value.user_message


def test_a_failed_paste_leaves_an_existing_licence_alone(shop):
    good = _issue_key(shop, license_type="DEMO", days=20, serial=11)
    shop.licensing.import_product_key(good)
    assert shop.licensing.evaluate().license_id == "ZB-DEMO-000011"
    for bad in ("", "nonsense", _issue_key(shop, license_type="DEMO", days=-1)):
        with pytest.raises(LicenseError):
            shop.licensing.import_product_key(bad)
    # Still the licence it had before anyone pasted anything.
    assert shop.licensing.evaluate().license_id == "ZB-DEMO-000011"
    assert shop.licensing.evaluate().status == LicenseStatus.DEMO


def test_copying_the_request_code_puts_it_on_the_clipboard(shop, qapp):
    from PyQt6.QtWidgets import QApplication

    window = _window(shop)
    try:
        window._activation_page._copy_btn.click()
        assert QApplication.clipboard().text() == shop.licensing.request_code()
        assert window._activation_page._status_line.text()
    finally:
        window.deleteLater()


def test_the_advanced_file_route_is_folded_away_but_still_there(shop, qapp):
    window = _window(shop)
    try:
        page = window._activation_page
        assert page._advanced.isVisible() is False
        page._advanced_btn.click()
        assert page._advanced.isVisibleTo(page) is True
        assert page._import_btn.text() and page._request_btn.text()
        page._advanced_btn.click()
        assert page._advanced.isVisible() is False
    finally:
        window.deleteLater()


def test_a_product_key_never_carries_a_private_key(shop):
    """It is a signature, not a secret: nothing in it can issue anything."""
    from zenith_business.security import product_key

    key = _issue_key(shop)
    decoded = product_key.decode_license(key)
    assert len(decoded.signature) == 64
    # The payload is exactly the fields a licence needs, and no key material.
    assert decoded.machine_fingerprint == shop.licensing.machine.fingerprint
    assert decoded.product_id == "ZENITH-BUSINESS"
    assert not hasattr(decoded, "private_key")


def test_the_customer_side_codec_cannot_sign(shop):
    from zenith_business.security import product_key

    source = Path(product_key.__file__).read_text(encoding="utf-8")
    for forbidden in ("Ed25519PrivateKey", "private_bytes", "def sign("):
        assert forbidden not in source, f"the codec can {forbidden}"


def test_both_sides_pack_the_same_bytes(shop):
    """The vendor tool and the application must agree byte for byte."""
    from zenith_business.security import product_key

    decoded = product_key.decode_request(shop.licensing.request_code())
    payload = product_key.build_license_payload(
        license_type="FULL", fingerprint=decoded.fingerprint,
        traits=decoded.traits, issued_at="2026-09-21", expires_at=None,
        serial=42, issued_to="Kabul Traders Ltd")
    again = product_key.build_license_payload(
        license_type="FULL", fingerprint=decoded.fingerprint,
        traits=decoded.traits, issued_at="2026-09-21", expires_at=None,
        serial=42, issued_to="Kabul Traders Ltd")
    assert payload == again
    assert product_key.decode_license(
        product_key.encode_license(payload, b"\0" * 64)).issued_at == "2026-09-21"


def test_a_product_key_is_short_enough_to_paste(shop):
    key = _issue_key(shop)
    assert len(key) < 300, f"a {len(key)}-character key is not pasteable"
    assert "\n" not in key


def test_every_activation_refusal_speaks_dari(shop, qapp):
    """The service raises English; the screen must not repeat it in a Dari UI."""
    window = _window(shop, LANG_DARI)
    try:
        page = window._activation_page
        for pasted in ("", "hello there", shop.licensing.request_code(),
                       _issue_key(shop)[:80]):
            page.key_input.setPlainText(pasted)
            page.activate_btn.click()
            message = page._error.text()
            assert message, f"no message for {pasted[:20]!r}"
            assert message.isascii() is False, f"English leaked: {message}"
    finally:
        window.deleteLater()


def test_a_wrong_machine_key_is_explained_in_dari(shop, qapp):
    from zenith_business.security import machine_id as machine
    from zenith_business.security import product_key
    from zenith_business.security.license_format import PRODUCT_ID

    other = machine.collect(PRODUCT_ID, overrides=OTHER_PC)
    foreign = product_key.encode_request(fingerprint=other.fingerprint,
                                         traits=other.traits)
    window = _window(shop, LANG_DARI)
    try:
        window._activation_page.key_input.setPlainText(
            _issue_key(shop, request=foreign))
        window._activation_page.activate_btn.click()
        message = window._activation_page._error.text()
        assert "کمپیوتر دیگری" in message
        assert message.isascii() is False
    finally:
        window.deleteLater()


def test_latin_tokens_inside_dari_text_are_isolated(shop):
    """Bidi reorders a trailing hyphen, so "ZB1-" reads as "-ZB1" without help.

    Found by reading the rendered Dari screen: the message told the customer
    their key starts with "-ZB1". Unicode isolates pin the run's direction.
    """
    from zenith_business.core.i18n import _CATALOG

    for key in ("act.product_key_ph", "act.err_request_pasted", "act.err_not_a_key"):
        dari = _CATALOG[key][LANG_DARI]
        assert "ZB1-" in dari
        position = dari.index("ZB1-")
        assert dari[position - 1] == "⁦", f"{key}: no isolate before ZB1-"
        assert dari[position + 4] == "⁩", f"{key}: no isolate after ZB1-"
