"""Initial administrator setup (Stage 02 §11).

On a brand-new database there are no users, so the app cannot require a login
yet. This service detects that "first run" condition and creates the FIRST
administrator from details the owner types on the Initial-Setup screen. There is
NO insecure built-in default (no ``admin``/``admin``): an administrator only
exists once the owner has chosen a real username and a policy-compliant password.
"""

from __future__ import annotations

from zenith_business.core.logging_setup import get_logger
from zenith_business.database.connection import Database
from zenith_business.repositories.system import AppSettingsRepository, AuditRepository
from zenith_business.repositories.users import RoleRepository, UserRepository
from zenith_business.security.passwords import hash_password
from zenith_business.services.exceptions import SetupError, ValidationError
from zenith_business.services.password_policy import validate_password

_logger = get_logger("services.setup")

ADMIN_ROLE_CODE = "ADMINISTRATOR"
SETTING_SETUP_COMPLETE = "setup.completed_at"


class InitialSetupService:
    def __init__(
        self,
        db: Database,
        users: UserRepository,
        roles: RoleRepository,
        audit: AuditRepository,
        settings: AppSettingsRepository,
    ) -> None:
        self._db = db
        self._users = users
        self._roles = roles
        self._audit = audit
        self._settings = settings

    def is_setup_required(self) -> bool:
        """True when no active administrator/user exists yet (first run)."""
        return self._users.count() == 0

    def create_administrator(
        self,
        *,
        username: str,
        password: str,
        full_name: str,
        confirm_password: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        preferred_language: str = "fa_AF",
        company_name: str | None = None,
    ) -> int:
        """Create the first administrator. Only valid on a fresh database."""
        if not self.is_setup_required():
            raise SetupError(
                "Initial setup has already been completed.",
                user_message="Setup has already been completed.")

        username = (username or "").strip()
        full_name = (full_name or "").strip()
        if not username:
            raise ValidationError("Username is required.",
                                  user_message="Please enter a username.")
        if not full_name:
            raise ValidationError("Full name is required.",
                                  user_message="Please enter your full name.")
        if confirm_password is not None and password != confirm_password:
            raise ValidationError("Passwords do not match.",
                                  user_message="The two passwords do not match.")
        validate_password(password, username=username)

        admin_role_id = self._roles.id_by_code(ADMIN_ROLE_CODE)
        if admin_role_id is None:
            # Baseline seed must have run first (migration 0002).
            raise SetupError("Administrator role missing; baseline not seeded.")

        with self._db.transaction():
            user_id = self._users.create(
                username=username, password_hash=hash_password(password),
                full_name=full_name, email=email, phone=phone,
                preferred_language=preferred_language, created_by=None)
            self._users.assign_role(user_id, admin_role_id)
            if company_name and company_name.strip():
                self._settings.set("company.name", company_name.strip())
            self._settings.set("app.default_language", preferred_language)
            self._audit.record(
                action="setup.create_administrator", user_id=user_id, username=username,
                entity_type="user", entity_id=user_id,
                details="First administrator created via initial setup.")
        _logger.info("Initial administrator %r created (id=%d).", username, user_id)
        return user_id
