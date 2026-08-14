"""User management service (Stage 02 §9, §12, §16, §48).

Creates and maintains user accounts and their role assignments. All writes run
in a transaction and are audited. Passwords are hashed here (never stored or
logged in plaintext) and validated against the shared password policy.
"""

from __future__ import annotations

from zenith_business.core.logging_setup import get_logger
from zenith_business.database.connection import Database
from zenith_business.repositories.system import AuditRepository
from zenith_business.repositories.users import (
    RoleRepository,
    UserRepository,
    normalize_username,
)
from zenith_business.security.passwords import hash_password
from zenith_business.services.authorization import AuthorizationService
from zenith_business.services.exceptions import ValidationError
from zenith_business.services.password_policy import validate_password
from zenith_business.services.session import SessionContext

_logger = get_logger("services.users")


class UserService:
    def __init__(
        self,
        db: Database,
        users: UserRepository,
        roles: RoleRepository,
        audit: AuditRepository,
        session: SessionContext,
        authz: AuthorizationService,
    ) -> None:
        self._db = db
        self._users = users
        self._roles = roles
        self._audit = audit
        self._session = session
        self._authz = authz

    def create_user(
        self,
        *,
        username: str,
        password: str,
        full_name: str,
        role_codes: list[str],
        email: str | None = None,
        phone: str | None = None,
        preferred_language: str = "fa_AF",
    ) -> int:
        """Create a user (requires ``users.manage``). Returns the new user id."""
        self._authz.require("users.manage")
        return self._create(
            username=username, password=password, full_name=full_name,
            role_codes=role_codes, email=email, phone=phone,
            preferred_language=preferred_language, created_by=self._session.user_id,
            audit_action="users.create")

    def _create(
        self,
        *,
        username: str,
        password: str,
        full_name: str,
        role_codes: list[str],
        email: str | None,
        phone: str | None,
        preferred_language: str,
        created_by: int | None,
        audit_action: str,
    ) -> int:
        username = (username or "").strip()
        full_name = (full_name or "").strip()
        if not username:
            raise ValidationError("Username is required.",
                                  user_message="Please enter a username.")
        if not full_name:
            raise ValidationError("Full name is required.",
                                  user_message="Please enter a full name.")
        if self._users.username_exists(username):
            raise ValidationError(
                f"Username {username!r} already exists.",
                user_message="That username is already taken.")
        validate_password(password, username=username)
        if not role_codes:
            raise ValidationError("At least one role is required.",
                                  user_message="Please assign at least one role.")

        role_ids: list[int] = []
        for code in role_codes:
            rid = self._roles.id_by_code(code)
            if rid is None:
                raise ValidationError(f"Unknown role {code!r}.")
            role_ids.append(rid)

        with self._db.transaction():
            user_id = self._users.create(
                username=username, password_hash=hash_password(password),
                full_name=full_name, email=email, phone=phone,
                preferred_language=preferred_language, created_by=created_by)
            for rid in role_ids:
                self._users.assign_role(user_id, rid)
            self._audit.record(
                action=audit_action, user_id=created_by,
                username=self._session.username, entity_type="user", entity_id=user_id,
                details=f"username={normalize_username(username)}; roles={role_codes}")
        _logger.info("Created user %r (id=%d) with roles %s", username, user_id, role_codes)
        return user_id

    def set_active(self, user_id: int, active: bool) -> None:
        self._authz.require("users.manage")
        with self._db.transaction():
            self._users.set_active(user_id, active)
            self._audit.record(
                action="users.activate" if active else "users.deactivate",
                user_id=self._session.user_id, username=self._session.username,
                entity_type="user", entity_id=user_id)

    def change_password(self, user_id: int, new_password: str) -> None:
        self._authz.require("users.manage")
        target = self._users.get_by_id(user_id)
        if target is None:
            raise ValidationError("No such user.")
        validate_password(new_password, username=target["username"])
        with self._db.transaction():
            self._users.update_password(user_id, hash_password(new_password))
            self._audit.record(
                action="users.password_reset", user_id=self._session.user_id,
                username=self._session.username, entity_type="user", entity_id=user_id)

    def list_users(self, *, include_inactive: bool = True) -> list[dict]:
        self._authz.require("users.view")
        return self._users.list_all(include_inactive=include_inactive)
