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
        # Administrator self-lockout protection (Stage 03 §21): never deactivate
        # the last active administrator.
        if not active and self._is_last_active_admin(user_id):
            raise ValidationError(
                "Cannot deactivate the last active administrator.",
                user_message="You cannot deactivate the only remaining administrator.")
        with self._db.transaction():
            self._users.set_active(user_id, active)
            self._audit.record(
                action="users.activate" if active else "users.deactivate",
                user_id=self._session.user_id, username=self._session.username,
                entity_type="user", entity_id=user_id)

    def change_password(self, user_id: int, new_password: str) -> None:
        """Administrative password reset — sets a NEW password (never reveals old)."""
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

    # Explicit alias mirroring the §18 vocabulary.
    reset_password = change_password

    # ---- self-service account settings (round 2) ------------------------

    def change_own_password(self, *, current_password: str, new_password: str) -> None:
        """The signed-in user changes their OWN password (round 2).

        Requires the current password (verified against the stored hash), enforces
        the shared password policy, stores only a secure hash, and is audited. No
        admin permission is needed — a user always owns their own account.
        """
        from zenith_business.security.passwords import verify_password
        uid = self._session.user_id
        me = self._users.get_by_id(uid) if uid is not None else None
        if me is None:
            raise ValidationError("Not signed in.", user_message="Please sign in again.")
        if not verify_password(current_password or "", me["password_hash"]):
            raise ValidationError("Current password is incorrect.",
                                  user_message="Your current password is incorrect.")
        if (new_password or "") == (current_password or ""):
            raise ValidationError("New password must differ.",
                                  user_message="The new password must be different from the"
                                               " current one.")
        validate_password(new_password, username=me["username"])
        with self._db.transaction():
            self._users.update_password(uid, hash_password(new_password))
            self._audit.record(action="account.change_password", user_id=uid,
                               username=self._session.username, entity_type="user",
                               entity_id=uid)
        _logger.info("User id=%s changed their own password", uid)

    def change_own_username(self, *, current_password: str, new_username: str) -> None:
        """The signed-in user changes their OWN username (round 2).

        Verifies the current password, validates + de-duplicates the new username,
        preserves the internal user id (so all transaction/audit relationships stay
        intact), refreshes the live session, and is audited.
        """
        from zenith_business.security.passwords import verify_password
        uid = self._session.user_id
        me = self._users.get_by_id(uid) if uid is not None else None
        if me is None:
            raise ValidationError("Not signed in.", user_message="Please sign in again.")
        if not verify_password(current_password or "", me["password_hash"]):
            raise ValidationError("Current password is incorrect.",
                                  user_message="Your current password is incorrect.")
        new_username = (new_username or "").strip()
        if not new_username:
            raise ValidationError("Username is required.",
                                  user_message="Please enter a username.")
        if normalize_username(new_username) == me["username_norm"]:
            return  # unchanged
        if self._users.username_exists(new_username):
            raise ValidationError("Username already exists.",
                                  user_message="That username is already taken.")
        with self._db.transaction():
            self._users.update_username(uid, new_username)
            self._audit.record(action="account.change_username", user_id=uid,
                               username=self._session.username, entity_type="user",
                               entity_id=uid,
                               details=f"{me['username']} → {new_username}")
        # Keep the live session label in sync with the new username.
        current = self._session.user
        if current is not None:
            try:
                current.username = new_username
            except Exception:
                pass
        _logger.info("User id=%s changed their own username", uid)

    def update_profile(self, user_id: int, *, full_name: str, email: str | None = None,
                       phone: str | None = None) -> None:
        self._authz.require("users.manage")
        full_name = (full_name or "").strip()
        if not full_name:
            raise ValidationError("Full name is required.",
                                  user_message="Full name is required.")
        with self._db.transaction():
            self._users.update_profile(user_id, full_name=full_name, email=email, phone=phone)
            self._audit.record(action="users.update_profile", user_id=self._session.user_id,
                               username=self._session.username, entity_type="user",
                               entity_id=user_id)

    def set_roles(self, user_id: int, role_codes: list[str]) -> None:
        """Replace a user's roles, protecting against removing the last admin."""
        self._authz.require("users.manage")
        if self._users.get_by_id(user_id) is None:
            raise ValidationError("No such user.")
        if not role_codes:
            raise ValidationError("At least one role is required.",
                                  user_message="Please assign at least one role.")
        # If this user is the last active admin, the new roles must keep admin.
        losing_admin = ("ADMINISTRATOR" not in role_codes
                        and self._users.has_role(user_id, "ADMINISTRATOR")
                        and self._is_last_active_admin(user_id))
        if losing_admin:
            raise ValidationError(
                "Cannot remove the administrator role from the last administrator.",
                user_message="You cannot remove admin rights from the only administrator.")
        role_ids = []
        for code in role_codes:
            rid = self._roles.id_by_code(code)
            if rid is None:
                raise ValidationError(f"Unknown role {code!r}.")
            role_ids.append((code, rid))
        with self._db.transaction():
            for existing in self._users.roles_for_user(user_id):
                self._users.remove_role(user_id, existing["id"])
            for _code, rid in role_ids:
                self._users.assign_role(user_id, rid)
            self._audit.record(action="users.set_roles", user_id=self._session.user_id,
                               username=self._session.username, entity_type="user",
                               entity_id=user_id, details=f"roles={role_codes}")

    def list_users(self, *, include_inactive: bool = True) -> list[dict]:
        self._authz.require("users.view")
        return self._users.list_all(include_inactive=include_inactive)

    def search_users(self, term: str, *, limit: int = 50) -> list[dict]:
        self._authz.require("users.view")
        return self._users.search(term, limit=limit)

    def roles_for(self, user_id: int) -> list[dict]:
        self._authz.require("users.view")
        return self._users.roles_for_user(user_id)

    def _is_last_active_admin(self, user_id: int) -> bool:
        return (self._users.has_role(user_id, "ADMINISTRATOR")
                and self._users.count_active_with_role("ADMINISTRATOR") <= 1)
