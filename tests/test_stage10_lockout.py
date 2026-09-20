"""Stage 10 lockout polish: expiry gives a fresh allowance, and it is visible.

Two defects motivated this file, both found by probing a real on-disk database
rather than by reading the code:

**Waiting out the lock did not restore the five attempts.** Clearing the lock
moved ``is_locked`` and ``locked_until`` but left ``failed_login_attempts`` at
the threshold, so the very next wrong password re-locked the account for another
full fifteen minutes. The owner served the wait and got one try, not five.

**The screen said "locked" and nothing else.** With no end time on it, a
temporary lock is indistinguishable from a broken program, which is what makes
someone reinstall or call for help over a wait that would have passed.

The tests below are split accordingly: what the polish CHANGES, and what it must
NOT change. The second half matters as much as the first — a lockout that is
easy to escape is not a lockout.
"""

from __future__ import annotations

import re
from datetime import timedelta

import pytest

from zenith_business.core.clock import now_utc, parse_iso
from zenith_business.core.config import LANG_DARI, LANG_ENGLISH
from zenith_business.core.i18n import Translator
from zenith_business.database.connection import Database
from zenith_business.services.authentication import (
    LOCKOUT_MINUTES,
    MAX_FAILED_ATTEMPTS,
)
from zenith_business.services.context import open_application_context
from zenith_business.services.exceptions import (
    AccountLockedError,
    AuthenticationError,
    ValidationError,
)

PASSWORD = "Str0ngPass!"


@pytest.fixture
def shop(tmp_path):
    """A real on-disk installation — the lock has to survive a real reopen."""
    database_file = tmp_path / "data" / "zenith.db"
    database_file.parent.mkdir(parents=True)
    db = Database(str(database_file))
    ctx = open_application_context(db, backups_dir=str(tmp_path / "backups"),
                                   license_dir=str(tmp_path / "license"))
    ctx.setup.create_administrator(username="owner", password=PASSWORD,
                                   full_name="Owner", company_name="Kabul Traders")
    ctx.auth.login("owner", PASSWORD)
    ctx.database_file = database_file
    yield ctx
    db.close()


# ---- helpers -------------------------------------------------------------

def _wrong(ctx, times: int = 1) -> None:
    for _ in range(times):
        with pytest.raises(AuthenticationError):
            ctx.auth.authenticate("owner", "wrong")


def _lock(ctx) -> None:
    _wrong(ctx, MAX_FAILED_ATTEMPTS)


def _row(ctx) -> dict:
    return ctx.users_repo.get_by_username("owner")


def _expire_the_lock(ctx) -> None:
    """Move the stored expiry into the past — what waiting it out looks like.

    Rewinding the timestamp rather than patching the clock keeps the test on the
    same wall-clock comparison the application actually performs.
    """
    past = (now_utc() - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with ctx.db.transaction() as tx:
        tx.execute("UPDATE users SET locked_until = ? WHERE username_norm = 'owner'",
                   (past,))


def _audit_actions(ctx) -> list[str]:
    return [r["action"] for r in ctx.db.connection().execute(
        "SELECT action FROM audit_log ORDER BY id")]


# ---- 1. what expiry now does --------------------------------------------

def test_an_expired_lock_is_cleared_in_full(shop):
    _lock(shop)
    _expire_the_lock(shop)
    assert shop.auth.authenticate("owner", PASSWORD) is not None
    row = _row(shop)
    assert row["is_locked"] == 0
    assert row["locked_until"] is None
    assert int(row["failed_login_attempts"] or 0) == 0


def test_expiry_restores_the_full_allowance_before_anything_else_happens(shop):
    """Merely ASKING about the account must already report five tries again."""
    _lock(shop)
    _expire_the_lock(shop)
    state = shop.security.guard_state("owner")
    assert state.is_locked is False
    assert state.failed_attempts == 0
    assert state.attempts_remaining == MAX_FAILED_ATTEMPTS


def test_one_wrong_password_after_expiry_does_not_re_lock_the_account(shop):
    """The regression this stage exists to kill."""
    _lock(shop)
    _expire_the_lock(shop)
    _wrong(shop)
    row = _row(shop)
    assert row["is_locked"] == 0, "a single mistake must not cost another 15 minutes"
    assert int(row["failed_login_attempts"]) == 1
    assert shop.security.guard_state("owner").attempts_remaining == MAX_FAILED_ATTEMPTS - 1


def test_after_expiry_it_takes_five_more_wrong_passwords_to_lock_again(shop):
    _lock(shop)
    _expire_the_lock(shop)
    _wrong(shop, MAX_FAILED_ATTEMPTS - 1)
    assert _row(shop)["is_locked"] == 0, "the fourth attempt must still be allowed"
    _wrong(shop)
    assert _row(shop)["is_locked"] == 1


def test_the_correct_password_works_the_moment_the_lock_expires(shop):
    _lock(shop)
    _expire_the_lock(shop)
    user = shop.auth.authenticate("owner", PASSWORD)
    assert user.username == "owner"


def test_expiry_noticed_during_re_authentication_also_resets_the_count(shop):
    """The sensitive-action path shares the counter, so it must share the fix."""
    _lock(shop)
    _expire_the_lock(shop)
    assert shop.security.verify_current_password(PASSWORD, action="test") is True
    assert int(_row(shop)["failed_login_attempts"] or 0) == 0


def test_the_expiry_is_recorded_in_the_audit_log(shop):
    _lock(shop)
    _expire_the_lock(shop)
    shop.auth.authenticate("owner", PASSWORD)
    actions = _audit_actions(shop)
    assert "auth.lockout" in actions
    assert "auth.lockout_expired" in actions


# ---- 2. the countdown the screen shows -----------------------------------

def test_guard_state_reports_the_seconds_left_on_the_lock(shop):
    _lock(shop)
    state = shop.security.guard_state("owner")
    assert state.is_locked is True
    # Rounded up, so a lock with any time left never reads as zero.
    assert LOCKOUT_MINUTES * 60 - 5 <= state.seconds_remaining <= LOCKOUT_MINUTES * 60


def test_an_unlocked_account_has_no_countdown(shop):
    state = shop.security.guard_state("owner")
    assert state.is_locked is False
    assert state.seconds_remaining == 0
    assert state.minutes_remaining == 0


def test_the_seconds_shrink_as_the_lock_runs_down(shop):
    _lock(shop)
    with shop.db.transaction() as tx:
        soon = (now_utc() + timedelta(seconds=90)).strftime("%Y-%m-%dT%H:%M:%SZ")
        tx.execute("UPDATE users SET locked_until = ? WHERE username_norm = 'owner'",
                   (soon,))
    assert 85 <= shop.security.guard_state("owner").seconds_remaining <= 90


def _login_page(qapp, language: str):
    from zenith_business.ui.auth.login_page import LoginPage

    return LoginPage(Translator(language), lambda u, p: None)


def test_the_login_screen_counts_down_in_english(qapp):
    page = _login_page(qapp, LANG_ENGLISH)
    page.show_lockout(12 * 60 + 34)
    assert page._error.text() == "Account locked. Try again in 12m 34s."
    assert page._error.isVisibleTo(page)


def test_the_login_screen_counts_down_in_dari(qapp):
    page = _login_page(qapp, LANG_DARI)
    page.show_lockout(12 * 60 + 34)
    text = page._error.text()
    assert "12" in text and "34" in text
    assert "دقیقه" in text and "ثانیه" in text
    assert "Account locked" not in text


def test_seconds_are_zero_padded_so_the_line_does_not_jump(qapp):
    page = _login_page(qapp, LANG_ENGLISH)
    page.show_lockout(61)
    assert page._error.text() == "Account locked. Try again in 1m 01s."


def test_each_tick_takes_a_second_off_the_countdown(qapp):
    page = _login_page(qapp, LANG_ENGLISH)
    page.show_lockout(125)
    page._tick_lockout()
    assert page.lockout_seconds == 124
    assert page._error.text() == "Account locked. Try again in 2m 04s."


def test_the_countdown_ends_by_saying_the_lock_is_over(qapp):
    page = _login_page(qapp, LANG_ENGLISH)
    page.show_lockout(1)
    page._tick_lockout()
    assert page.lockout_seconds == 0
    assert page._lock_timer.isActive() is False
    assert page._error.text() == "The lock has ended. You can sign in again."
    # Good news must not be painted in the error colour.
    assert page._error.property("role") == "secondary"


def test_a_new_error_goes_back_to_the_error_colour(qapp):
    page = _login_page(qapp, LANG_ENGLISH)
    page.show_lockout(1)
    page._tick_lockout()
    page.set_error("Incorrect username or password.")
    assert page._error.property("role") == "error"


def test_pressing_sign_in_again_does_not_wipe_the_countdown(qapp):
    """``clear_error`` runs on every submit; the wait is still real."""
    page = _login_page(qapp, LANG_ENGLISH)
    page.show_lockout(300)
    page.clear_error()
    assert page._error.text() == "Account locked. Try again in 5m 00s."
    assert page._error.isVisibleTo(page)


def test_a_different_error_replaces_the_countdown(qapp):
    page = _login_page(qapp, LANG_ENGLISH)
    page.show_lockout(300)
    page.set_error("Incorrect username or password.")
    assert page.lockout_seconds == 0
    assert page._lock_timer.isActive() is False


def test_switching_language_mid_lock_retranslates_the_countdown(qapp):
    page = _login_page(qapp, LANG_ENGLISH)
    page.show_lockout(12 * 60 + 34)
    page.retranslate(Translator(LANG_DARI))
    assert "دقیقه" in page._error.text()
    assert "Account locked" not in page._error.text()


def test_a_lock_with_no_time_left_falls_back_to_a_plain_message(qapp):
    page = _login_page(qapp, LANG_ENGLISH)
    page.show_lockout(0)
    assert page._lock_timer.isActive() is False
    assert page._error.text() == "This account is locked. Please try again later."


def test_the_login_window_shows_the_real_remaining_time(qapp, shop):
    """End to end: five wrong passwords on the real screen produce a countdown."""
    from zenith_business.core.config import AppConfig
    from zenith_business.ui.auth.auth_window import AuthWindow

    cfg = AppConfig()
    cfg.ui.language = LANG_ENGLISH
    window = AuthWindow(shop, cfg)
    try:
        for _ in range(MAX_FAILED_ATTEMPTS + 1):
            window._handle_login("owner", "wrong")
        assert window._login_page.lockout_seconds > 0
        # A freshly-set 15-minute lock, give or take the second it took to run.
        assert re.fullmatch(r"Account locked\. Try again in 1[45]m \d\ds\.",
                            window._login_page._error.text())
    finally:
        window.deleteLater()


# ---- 3. what must NOT have changed ---------------------------------------

def test_the_lock_still_falls_on_the_fifth_wrong_password(shop):
    _wrong(shop, MAX_FAILED_ATTEMPTS - 1)
    assert _row(shop)["is_locked"] == 0, "four mistakes must not lock the account"
    _wrong(shop)
    assert _row(shop)["is_locked"] == 1


def test_the_lock_still_lasts_fifteen_minutes(shop):
    assert LOCKOUT_MINUTES == 15
    before = now_utc()
    _lock(shop)
    until = parse_iso(_row(shop)["locked_until"])
    assert until is not None
    delta = (until - before).total_seconds()
    assert 15 * 60 - 5 <= delta <= 15 * 60 + 5


def test_attempts_during_an_active_lock_still_do_not_extend_it(shop):
    _lock(shop)
    until = _row(shop)["locked_until"]
    attempts = int(_row(shop)["failed_login_attempts"])
    for _ in range(3):
        with pytest.raises(AccountLockedError):
            shop.auth.authenticate("owner", "wrong")
    assert _row(shop)["locked_until"] == until, "the wait must not restart"
    assert int(_row(shop)["failed_login_attempts"]) == attempts


def test_the_correct_password_is_still_rejected_while_locked(shop):
    _lock(shop)
    with pytest.raises(AccountLockedError):
        shop.auth.authenticate("owner", PASSWORD)


def test_re_authentication_is_still_refused_while_locked(shop):
    _lock(shop)
    with pytest.raises(ValidationError):
        shop.security.verify_current_password(PASSWORD, action="test")


def test_the_lock_still_survives_closing_and_reopening_the_application(shop):
    _lock(shop)
    path = str(shop.database_file)
    shop.db.close()
    reopened = Database(path)
    ctx = open_application_context(reopened)
    try:
        assert ctx.users_repo.get_by_username("owner")["is_locked"] == 1
        with pytest.raises(AccountLockedError):
            ctx.auth.authenticate("owner", PASSWORD)
    finally:
        reopened.close()


def test_a_successful_login_still_resets_the_failed_attempts(shop):
    _wrong(shop, 3)
    assert int(_row(shop)["failed_login_attempts"]) == 3
    shop.auth.authenticate("owner", PASSWORD)
    assert int(_row(shop)["failed_login_attempts"] or 0) == 0


def test_a_recovery_code_still_clears_the_lock(shop):
    code = shop.security.issue_recovery_code(current_password=PASSWORD)
    _lock(shop)
    shop.security.recover_with_code(username="owner", recovery_code=code,
                                    new_password="An0therPass!")
    row = _row(shop)
    assert row["is_locked"] == 0
    assert row["locked_until"] is None
    # And with a clean slate, so a first typo does not land straight back in.
    assert int(row["failed_login_attempts"] or 0) == 0
    assert shop.auth.authenticate("owner", "An0therPass!") is not None


def test_an_unknown_username_still_locks_nothing(shop):
    for _ in range(MAX_FAILED_ATTEMPTS + 2):
        with pytest.raises(AuthenticationError):
            shop.auth.authenticate("nobody", "wrong")
    assert _row(shop)["is_locked"] == 0
