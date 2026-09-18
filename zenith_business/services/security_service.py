"""Owner-account security for a single-PC install (Stage 10 §1, §2, §3).

Stage 02 already hashes passwords with PBKDF2, counts failed attempts, locks the
account temporarily, records the last successful login and audits all of it. This
module adds the four things a single-owner installation still needed:

**Re-authentication.** A dangerous action should ask *who is doing it*, not just
whether someone is signed in. :meth:`verify_current_password` is the one check
behind every sensitive action, and it is rate-limited exactly like the login
screen so it cannot become a softer way to guess the password.

**Recovery for the only account there is.** On one PC with one owner there is no
administrator to reset the password — the usual answer, "ask your admin", does
not exist. A recovery code is issued on demand, shown once, and stored only as a
hash, so the owner can write it down and get back in without anyone being able
to read it out of the database later. Using it is a password change: it is
consumed, audited, and the old password stops working.

**A lockout that can be waited out or cleared knowingly.** The existing lockout
is temporary by design. This adds the reads the UI needs to explain it —
how many attempts remain, and when the lock lifts — because "wrong password"
with no further information is what makes people think their data is gone.

**Audited settings.** ``AppSettingsRepository.set`` writes configuration with no
record of who changed what. Critical keys now go through :meth:`update_setting`,
which audits the change including the previous value.

Nothing here weakens what Stage 02 established, and no locked service is
modified: this composes with them.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import timedelta

from zenith_business.core.clock import now_iso, now_utc, parse_iso
from zenith_business.core.logging_setup import get_logger
from zenith_business.security.passwords import hash_password, verify_password
from zenith_business.services.authentication import (
    LOCKOUT_MINUTES,
    MAX_FAILED_ATTEMPTS,
)
from zenith_business.services.exceptions import ValidationError
from zenith_business.services.password_policy import validate_password

_logger = get_logger("services.security")

#: Settings key holding the hash of the current recovery code.
RECOVERY_HASH_KEY = "security.recovery_code_hash"
#: Settings key holding when that code was issued (for display only).
RECOVERY_ISSUED_KEY = "security.recovery_code_issued_at"

#: Settings whose change is security-relevant and therefore always audited.
CRITICAL_SETTINGS = frozenset({
    "company.name", "license.demo_started_at",
    RECOVERY_HASH_KEY, RECOVERY_ISSUED_KEY,
})

#: Recovery codes are shown to a human, so they avoid easily-confused characters.
_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_CODE_GROUPS = 4
_CODE_GROUP_LENGTH = 5


@dataclass(frozen=True)
class LoginGuardState:
    """What the login screen can honestly tell the owner."""

    is_locked: bool
    failed_attempts: int
    attempts_remaining: int
    locked_until: str | None
    minutes_remaining: int
    last_login_at: str | None


def _format_code(raw: str) -> str:
    return "-".join(raw[i:i + _CODE_GROUP_LENGTH]
                    for i in range(0, len(raw), _CODE_GROUP_LENGTH))


def normalize_recovery_code(text: str) -> str:
    """Accept what a human typed: any case, any spacing, any dashes."""
    return "".join(ch for ch in (text or "").upper() if ch in _CODE_ALPHABET)


class SecurityService:
    """Re-authentication, recovery and audited settings for the owner account."""

    def __init__(self, db, users_repo, settings_repo, audit_repo, session,
                 audit=None) -> None:
        self._db = db
        self._users = users_repo
        self._settings = settings_repo
        self._audit = audit_repo
        self._session = session

    # ---- re-authentication ----------------------------------------------

    def verify_current_password(self, password: str, *, action: str = "sensitive") -> bool:
        """Confirm the signed-in owner's password before something dangerous.

        Counts against the same failed-attempt lockout as the login screen, so
        this cannot be used as an unlimited password oracle. Returns True/False
        rather than raising, because the caller shows a dialog either way.
        """
        uid = self._session.user_id
        row = self._users.get_by_id(uid) if uid is not None else None
        if row is None:
            return False

        if self._lock_is_active(row):
            self._write_audit("auth.reauth_blocked", f"action={action} reason=locked")
            raise ValidationError(
                "Account is temporarily locked.",
                user_message="Too many incorrect passwords. Please wait and try again.")

        if verify_password(password or "", row["password_hash"]):
            with self._db.transaction():
                self._users.record_login_success(row["id"])
                self._audit.record(action="auth.reauth_ok", user_id=row["id"],
                                   username=row["username"], details=f"action={action}")
            return True

        with self._db.transaction():
            attempts = self._users.record_login_failure(row["id"])
            if attempts >= MAX_FAILED_ATTEMPTS:
                until = (now_utc() + timedelta(minutes=LOCKOUT_MINUTES)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
                self._users.set_locked(row["id"], True, until)
                self._audit.record(action="auth.lockout", user_id=row["id"],
                                   username=row["username"],
                                   details=f"Locked after {attempts} failed re-auth.")
            self._audit.record(action="auth.reauth_failed", user_id=row["id"],
                               username=row["username"], details=f"action={action}")
        return False

    def require_current_password(self, password: str, *, action: str) -> None:
        """:meth:`verify_current_password`, but raising — for service callers."""
        if not self.verify_current_password(password, action=action):
            raise ValidationError(
                f"Re-authentication failed for {action}.",
                user_message="That password is not correct.")

    # ---- what the login screen may say ----------------------------------

    def guard_state(self, username: str | None = None) -> LoginGuardState:
        row = (self._users.get_by_username(username) if username
               else (self._users.get_by_id(self._session.user_id)
                     if self._session.user_id is not None else None))
        if row is None:
            return LoginGuardState(False, 0, MAX_FAILED_ATTEMPTS, None, 0, None)
        attempts = int(row["failed_login_attempts"] or 0)
        locked = self._lock_is_active(row)
        minutes = 0
        if locked:
            until = parse_iso(row.get("locked_until"))
            if until is not None:
                minutes = max(0, int((until - now_utc()).total_seconds() // 60) + 1)
        return LoginGuardState(
            is_locked=locked,
            failed_attempts=attempts,
            attempts_remaining=max(0, MAX_FAILED_ATTEMPTS - attempts),
            locked_until=row.get("locked_until"),
            minutes_remaining=minutes,
            last_login_at=row.get("last_login_at"))

    def _lock_is_active(self, row: dict) -> bool:
        if not row.get("is_locked"):
            return False
        until = parse_iso(row.get("locked_until"))
        if until is not None and now_utc() >= until:
            with self._db.transaction():
                self._users.set_locked(row["id"], False, None)
            return False
        return True

    # ---- recovery --------------------------------------------------------

    def has_recovery_code(self) -> bool:
        return bool(self._settings.get(RECOVERY_HASH_KEY))

    def recovery_issued_at(self) -> str | None:
        return self._settings.get(RECOVERY_ISSUED_KEY)

    def issue_recovery_code(self, *, current_password: str) -> str:
        """Generate a recovery code, store only its hash, and return it ONCE.

        Requires the current password: a recovery code is a second way into the
        account, so handing one out must itself be an authenticated act.
        """
        self.require_current_password(current_password, action="issue_recovery_code")
        raw = "".join(secrets.choice(_CODE_ALPHABET)
                      for _ in range(_CODE_GROUPS * _CODE_GROUP_LENGTH))
        with self._db.transaction():
            self._settings.set(RECOVERY_HASH_KEY, hash_password(raw))
            self._settings.set(RECOVERY_ISSUED_KEY, now_iso())
            self._audit.record(action="security.recovery_code_issued",
                               user_id=self._session.user_id,
                               username=self._session.username,
                               details="A new recovery code was generated.")
        _logger.info("Recovery code issued for the owner account.")
        # Returned once. Only the hash is kept, so it cannot be read back later.
        return _format_code(raw)

    def recover_with_code(self, *, username: str, recovery_code: str,
                          new_password: str) -> None:
        """Set a new password using the recovery code, without the old password.

        The code is single-use: it is cleared on success, so a written-down code
        that has been used cannot be used again by someone who finds the note.
        """
        stored = self._settings.get(RECOVERY_HASH_KEY)
        row = self._users.get_by_username(username)
        code = normalize_recovery_code(recovery_code)
        if not stored or row is None or not code:
            self._write_audit("security.recovery_failed", "No usable recovery code.")
            raise ValidationError(
                "Recovery is not available.",
                user_message="That recovery code is not correct.")

        if not verify_password(code, stored):
            self._write_audit("security.recovery_failed",
                              f"Bad recovery code for {username!r}.")
            raise ValidationError(
                "Recovery code did not match.",
                user_message="That recovery code is not correct.")

        validate_password(new_password, username=row["username"])
        with self._db.transaction():
            self._users.update_password(row["id"], hash_password(new_password))
            # Recovery also clears the lockout: the owner has proved themselves.
            self._users.set_locked(row["id"], False, None)
            self._settings.set(RECOVERY_HASH_KEY, None)
            self._settings.set(RECOVERY_ISSUED_KEY, None)
            self._audit.record(action="security.recovery_used", user_id=row["id"],
                               username=row["username"],
                               details="Password reset with a recovery code.")
        _logger.info("Owner password reset via recovery code.")

    # ---- audited settings -------------------------------------------------

    def update_setting(self, key: str, value: str | None, *, reason: str = "") -> None:
        """Change a setting and record who changed it, and from what."""
        previous = self._settings.get(key)
        with self._db.transaction():
            self._settings.set(key, value)
            self._audit.record(
                action="settings.update", user_id=self._session.user_id,
                username=self._session.username, entity_type="setting",
                document_no=key,
                details=self._describe(key, previous, value, reason))

    @staticmethod
    def _describe(key: str, previous, value, reason: str) -> str:
        # A secret's VALUE never reaches the audit log — only that it changed.
        if key in (RECOVERY_HASH_KEY,):
            body = f"{key}: (hidden) changed"
        else:
            body = f"{key}: {previous!r} -> {value!r}"
        return f"{body}{'; ' + reason if reason else ''}"

    # ---- internals -------------------------------------------------------

    def _write_audit(self, action: str, details: str) -> None:
        try:
            with self._db.transaction():
                self._audit.record(action=action, user_id=self._session.user_id,
                                   username=self._session.username, details=details)
        except Exception:
            _logger.warning("Could not write the %s audit entry.", action)
