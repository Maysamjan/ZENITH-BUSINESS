"""Authentication service (Stage 02 §10, §11).

Verifies credentials against stored PBKDF2 hashes (never plaintext), enforces
active/locked account state, applies a failed-attempt lockout, and loads the
user's roles + permissions into a :class:`CurrentUser`. Successful and failed
attempts are audited — but a password is NEVER logged or audited.
"""

from __future__ import annotations

from datetime import timedelta

from zenith_business.core.clock import now_utc, parse_iso
from zenith_business.core.logging_setup import get_logger
from zenith_business.database.connection import Database
from zenith_business.repositories.system import AuditRepository
from zenith_business.repositories.users import UserRepository, normalize_username
from zenith_business.security.passwords import hash_password, needs_rehash, verify_password
from zenith_business.services.exceptions import (
    AccountInactiveError,
    AccountLockedError,
    AuthenticationError,
)
from zenith_business.services.session import CurrentUser, SessionContext

_logger = get_logger("services.auth")

#: Failed logins allowed before the account is temporarily locked.
MAX_FAILED_ATTEMPTS = 5
#: How long an account stays locked after crossing the threshold.
LOCKOUT_MINUTES = 15


class AuthenticationService:
    def __init__(
        self,
        db: Database,
        users: UserRepository,
        audit: AuditRepository,
        session: SessionContext,
    ) -> None:
        self._db = db
        self._users = users
        self._audit = audit
        self._session = session

    def authenticate(self, username: str, password: str) -> CurrentUser:
        """Validate credentials and return a :class:`CurrentUser`.

        Does NOT itself mutate the global session — callers (or :meth:`login`)
        decide when to start the session. Raises an :class:`AuthenticationError`
        subclass on any failure, with a generic user-facing message so we never
        reveal whether the username or the password was the wrong part.
        """
        uname = normalize_username(username)
        if not uname or not password:
            raise AuthenticationError("Empty username or password.")

        row = self._users.get_by_username(uname)
        if row is None:
            # Do not disclose which field was wrong; still audit the attempt.
            self._audit_failure(None, uname, "unknown user")
            raise AuthenticationError(f"Unknown username {uname!r}.")

        self._guard_locked(row)
        self._guard_active(row)

        if not verify_password(password, row["password_hash"]):
            self._register_failure(row)
            raise AuthenticationError("Bad password.")

        self._register_success(row, password)
        return self._load_current_user(row["id"])

    def login(self, username: str, password: str) -> CurrentUser:
        """Authenticate and start the global session on success."""
        user = self.authenticate(username, password)
        self._session.start(user)
        _logger.info("User %r signed in (id=%d).", user.username, user.id)
        return user

    def logout(self) -> None:
        user = self._session.user
        if user is not None:
            with self._db.transaction():
                self._audit.record(
                    action="auth.logout", user_id=user.id, username=user.username)
            _logger.info("User %r signed out.", user.username)
        self._session.clear()

    # ---- internals -------------------------------------------------------

    def _guard_locked(self, row: dict) -> None:
        if not row["is_locked"]:
            return
        until = parse_iso(row.get("locked_until"))
        if until is not None and now_utc() >= until:
            # Lock window elapsed — clear it and let the attempt proceed.
            with self._db.transaction():
                self._users.set_locked(row["id"], False, None)
            row["is_locked"] = 0
            return
        self._audit_failure(row["id"], row["username"], "locked")
        raise AccountLockedError(f"Account {row['username']!r} is locked.")

    def _guard_active(self, row: dict) -> None:
        if not row["is_active"]:
            self._audit_failure(row["id"], row["username"], "inactive")
            raise AccountInactiveError(f"Account {row['username']!r} is inactive.")

    def _register_failure(self, row: dict) -> None:
        with self._db.transaction():
            attempts = self._users.record_login_failure(row["id"])
            if attempts >= MAX_FAILED_ATTEMPTS:
                locked_until = (now_utc() + timedelta(minutes=LOCKOUT_MINUTES)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
                self._users.set_locked(row["id"], True, locked_until)
                self._audit.record(
                    action="auth.lockout", user_id=row["id"], username=row["username"],
                    details=f"Locked after {attempts} failed attempts.")
            self._audit.record(
                action="auth.login_failed", user_id=row["id"], username=row["username"],
                details="Invalid password.")

    def _register_success(self, row: dict, password: str) -> None:
        with self._db.transaction():
            self._users.record_login_success(row["id"])
            # Transparent hash upgrade if parameters have since strengthened.
            if needs_rehash(row["password_hash"]):
                self._users.update_password(row["id"], hash_password(password))
            self._audit.record(
                action="auth.login_success", user_id=row["id"], username=row["username"])

    def _audit_failure(self, user_id: int | None, username: str, reason: str) -> None:
        with self._db.transaction():
            self._audit.record(
                action="auth.login_denied", user_id=user_id, username=username,
                details=reason)

    def _load_current_user(self, user_id: int) -> CurrentUser:
        row = self._users.get_by_id(user_id)
        assert row is not None  # just authenticated
        roles = self._users.roles_for_user(user_id)
        perms = self._users.permissions_for_user(user_id)
        return CurrentUser(
            id=row["id"],
            username=row["username"],
            full_name=row["full_name"],
            preferred_language=row["preferred_language"],
            role_codes=tuple(r["code"] for r in roles),
            permissions=frozenset(perms),
        )
