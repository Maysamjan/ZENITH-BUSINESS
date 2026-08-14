"""Role & permission management service (Stage 03 §19, §20).

Wraps the LOCKED Stage 02 RBAC tables. Presents human-readable permission labels
grouped by module while preserving the stable internal permission codes. System
roles (e.g. Administrator) are protected from having their permissions stripped.
"""

from __future__ import annotations

from zenith_business.database.connection import Database
from zenith_business.repositories.system import AuditRepository
from zenith_business.repositories.users import PermissionRepository, RoleRepository
from zenith_business.services.authorization import AuthorizationService
from zenith_business.services.exceptions import ValidationError
from zenith_business.services.session import SessionContext

# Human-readable labels for permission codes (UI shows these; codes stay stable).
PERMISSION_LABELS: dict[str, str] = {
    "sales.view": "View sales", "sales.create": "Create sales", "sales.edit": "Edit sales",
    "sales.post": "Post sales", "sales.void": "Void sales",
    "purchases.view": "View purchases", "purchases.create": "Create purchases",
    "purchases.edit": "Edit purchases", "purchases.post": "Post purchases",
    "purchases.void": "Void purchases",
    "inventory.view": "View inventory", "inventory.adjust": "Adjust stock",
    "inventory.transfer": "Transfer stock",
    "accounts.view": "View accounts", "accounts.receive": "Receive payments",
    "accounts.pay": "Make payments",
    "customers.view": "View customers", "customers.manage": "Manage customers",
    "suppliers.view": "View suppliers", "suppliers.manage": "Manage suppliers",
    "items.view": "View items", "items.manage": "Manage items",
    "items.create": "Create items", "items.edit": "Edit items",
    "items.view_cost": "View item cost", "items.view_profit": "View item profit",
    "reports.sales": "Sales reports", "reports.inventory": "Inventory reports",
    "reports.accounts": "Account reports", "reports.profit": "Profit reports",
    "users.view": "View users", "users.manage": "Manage users",
    "roles.manage": "Manage roles", "settings.manage": "Manage settings",
    "backup.create": "Create backups", "backup.restore": "Restore backups",
    "company.manage": "Manage company profile",
    "financialyear.view": "View financial years", "financialyear.manage": "Manage financial years",
    "warehouses.view": "View warehouses", "warehouses.manage": "Manage warehouses",
    "units.view": "View units", "units.manage": "Manage units",
    "categories.view": "View categories", "categories.manage": "Manage categories",
    "persons.view": "View persons", "persons.create": "Create persons",
    "persons.edit": "Edit persons",
}

# Display order for permission groups.
_GROUP_ORDER = ["sales", "purchases", "inventory", "items", "persons", "customers",
                "suppliers", "warehouses", "units", "categories", "accounts", "reports",
                "financialyear", "users", "roles", "settings", "company", "backup"]


def label_for(code: str) -> str:
    return PERMISSION_LABELS.get(code, code)


class RoleService:
    def __init__(self, db: Database, roles: RoleRepository, permissions: PermissionRepository,
                 audit: AuditRepository, session: SessionContext,
                 authz: AuthorizationService) -> None:
        self._db = db
        self._roles = roles
        self._perms = permissions
        self._audit = audit
        self._session = session
        self._authz = authz

    def list_roles(self) -> list[dict]:
        self._authz.require("roles.manage")
        return self._roles.list_all()

    def permission_groups(self) -> list[tuple[str, list[tuple[str, str]]]]:
        """Return [(group, [(code, label), ...]), ...] ordered for the UI (§20)."""
        self._authz.require("roles.manage")
        codes = self._perms.list_codes()
        groups: dict[str, list[tuple[str, str]]] = {}
        for code in codes:
            group = code.split(".", 1)[0]
            groups.setdefault(group, []).append((code, label_for(code)))
        ordered = [(g, sorted(groups[g])) for g in _GROUP_ORDER if g in groups]
        # Any group not in the explicit order goes last, alphabetically.
        for g in sorted(groups):
            if g not in _GROUP_ORDER:
                ordered.append((g, sorted(groups[g])))
        return ordered

    def permissions_for_role(self, role_id: int) -> set[str]:
        self._authz.require("roles.manage")
        return self._roles.permissions_for_role(role_id)

    def create_role(self, *, code: str, name: str, description: str | None = None) -> int:
        self._authz.require("roles.manage")
        code = (code or "").strip().upper()
        name = (name or "").strip()
        if not code or not name:
            raise ValidationError("Role code and name are required.",
                                  user_message="Role code and name are required.")
        if self._roles.get_by_code(code) is not None:
            raise ValidationError("Duplicate role code.",
                                  user_message="That role code already exists.")
        with self._db.transaction():
            rid = self._roles.create(code=code, name=name, description=description)
            self._audit.record(action="roles.create", user_id=self._session.user_id,
                               username=self._session.username, entity_type="role",
                               entity_id=rid, details=f"code={code}")
        return rid

    def set_permissions(self, role_id: int, permission_codes: list[str]) -> None:
        self._authz.require("roles.manage")
        role = self._roles.list_all()
        role = next((r for r in role if r["id"] == role_id), None)
        if role is None:
            raise ValidationError("No such role.")
        # System Administrator role must always retain every permission.
        if role["code"] == "ADMINISTRATOR":
            all_codes = set(self._perms.list_codes())
            if set(permission_codes) != all_codes:
                raise ValidationError(
                    "The Administrator role must retain all permissions.",
                    user_message="The Administrator role always has every permission.")
        mapping = self._perms.map_codes()
        ids = []
        for code in permission_codes:
            if code not in mapping:
                raise ValidationError(f"Unknown permission {code!r}.")
            ids.append(mapping[code])
        with self._db.transaction():
            self._roles.set_permissions(role_id, ids)
            self._audit.record(action="roles.set_permissions", user_id=self._session.user_id,
                               username=self._session.username, entity_type="role",
                               entity_id=role_id, details=f"count={len(ids)}")
