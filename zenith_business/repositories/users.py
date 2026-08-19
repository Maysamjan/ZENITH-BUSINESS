"""User / role / permission repositories (Stage 02 §9, §12, §13, §16)."""

from __future__ import annotations

from zenith_business.core.clock import now_iso
from zenith_business.repositories.base import BaseRepository


def normalize_username(username: str) -> str:
    return (username or "").strip().lower()


class UserRepository(BaseRepository):
    def count(self) -> int:
        return int(self._scalar("SELECT COUNT(*) FROM users") or 0)

    def count_active(self) -> int:
        return int(self._scalar("SELECT COUNT(*) FROM users WHERE is_active = 1") or 0)

    def get_by_id(self, user_id: int) -> dict | None:
        return self._one("SELECT * FROM users WHERE id = ?", (user_id,))

    def get_by_username(self, username: str) -> dict | None:
        return self._one(
            "SELECT * FROM users WHERE username_norm = ?", (normalize_username(username),)
        )

    def username_exists(self, username: str) -> bool:
        return self._scalar(
            "SELECT 1 FROM users WHERE username_norm = ?", (normalize_username(username),)
        ) is not None

    def create(
        self,
        *,
        username: str,
        password_hash: str,
        full_name: str,
        email: str | None = None,
        phone: str | None = None,
        preferred_language: str = "fa_AF",
        created_by: int | None = None,
    ) -> int:
        ts = now_iso()
        return self._insert(
            "INSERT INTO users (username, username_norm, password_hash, full_name, email,"
            " phone, preferred_language, password_changed_at, created_at, updated_at, created_by)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (username.strip(), normalize_username(username), password_hash, full_name,
             email, phone, preferred_language, ts, ts, ts, created_by),
        )

    def list_all(self, *, include_inactive: bool = True) -> list[dict]:
        sql = "SELECT id, username, full_name, email, phone, is_active, is_locked, last_login_at FROM users"
        if not include_inactive:
            sql += " WHERE is_active = 1"
        return self._all(sql + " ORDER BY full_name")

    def search(self, term: str, *, limit: int = 50) -> list[dict]:
        like = f"%{term.strip()}%"
        return self._all(
            "SELECT id, username, full_name, email, phone, is_active, is_locked, last_login_at"
            " FROM users WHERE username LIKE ? OR full_name LIKE ? OR email LIKE ?"
            " ORDER BY full_name LIMIT ?", (like, like, like, limit))

    def count_active_with_role(self, role_code: str) -> int:
        """Active users holding a given role (for last-administrator protection)."""
        return int(self._scalar(
            "SELECT COUNT(DISTINCT u.id) FROM users u"
            " JOIN user_roles ur ON ur.user_id = u.id"
            " JOIN roles r ON r.id = ur.role_id"
            " WHERE u.is_active = 1 AND r.code = ?", (role_code,)) or 0)

    def has_role(self, user_id: int, role_code: str) -> bool:
        return self._scalar(
            "SELECT 1 FROM user_roles ur JOIN roles r ON r.id = ur.role_id"
            " WHERE ur.user_id = ? AND r.code = ?", (user_id, role_code)) is not None

    # ---- authentication metadata ----

    def record_login_success(self, user_id: int) -> None:
        ts = now_iso()
        self._exec(
            "UPDATE users SET last_login_at = ?, failed_login_attempts = 0,"
            " last_failed_login_at = NULL, updated_at = ? WHERE id = ?",
            (ts, ts, user_id),
        )

    def record_login_failure(self, user_id: int) -> int:
        ts = now_iso()
        self._exec(
            "UPDATE users SET failed_login_attempts = failed_login_attempts + 1,"
            " last_failed_login_at = ?, updated_at = ? WHERE id = ?",
            (ts, ts, user_id),
        )
        return int(self._scalar(
            "SELECT failed_login_attempts FROM users WHERE id = ?", (user_id,)) or 0)

    def set_active(self, user_id: int, active: bool) -> None:
        self._exec(
            "UPDATE users SET is_active = ?, updated_at = ? WHERE id = ?",
            (1 if active else 0, now_iso(), user_id),
        )

    def set_locked(self, user_id: int, locked: bool, locked_until: str | None = None) -> None:
        self._exec(
            "UPDATE users SET is_locked = ?, locked_until = ?, updated_at = ? WHERE id = ?",
            (1 if locked else 0, locked_until, now_iso(), user_id),
        )

    def update_password(self, user_id: int, password_hash: str) -> None:
        ts = now_iso()
        self._exec(
            "UPDATE users SET password_hash = ?, password_changed_at = ?, updated_at = ?"
            " WHERE id = ?",
            (password_hash, ts, ts, user_id),
        )

    def update_username(self, user_id: int, username: str) -> None:
        ts = now_iso()
        self._exec(
            "UPDATE users SET username = ?, username_norm = ?, updated_at = ? WHERE id = ?",
            (username.strip(), normalize_username(username), ts, user_id),
        )

    def update_language(self, user_id: int, language: str) -> None:
        self._exec(
            "UPDATE users SET preferred_language = ?, updated_at = ? WHERE id = ?",
            (language, now_iso(), user_id),
        )

    def update_profile(self, user_id: int, *, full_name: str, email: str | None, phone: str | None) -> None:
        self._exec(
            "UPDATE users SET full_name = ?, email = ?, phone = ?, updated_at = ? WHERE id = ?",
            (full_name, email, phone, now_iso(), user_id),
        )

    # ---- roles / permissions ----

    def assign_role(self, user_id: int, role_id: int) -> None:
        self._exec(
            "INSERT OR IGNORE INTO user_roles (user_id, role_id) VALUES (?, ?)",
            (user_id, role_id),
        )

    def remove_role(self, user_id: int, role_id: int) -> None:
        self._exec("DELETE FROM user_roles WHERE user_id = ? AND role_id = ?", (user_id, role_id))

    def roles_for_user(self, user_id: int) -> list[dict]:
        return self._all(
            "SELECT r.id, r.code, r.name FROM roles r JOIN user_roles ur ON ur.role_id = r.id"
            " WHERE ur.user_id = ? AND r.is_active = 1 ORDER BY r.name",
            (user_id,),
        )

    def permissions_for_user(self, user_id: int) -> set[str]:
        rows = self._all(
            "SELECT DISTINCT p.code FROM permissions p"
            " JOIN role_permissions rp ON rp.permission_id = p.id"
            " JOIN roles r ON r.id = rp.role_id"
            " JOIN user_roles ur ON ur.role_id = r.id"
            " WHERE ur.user_id = ? AND r.is_active = 1",
            (user_id,),
        )
        return {row["code"] for row in rows}


class RoleRepository(BaseRepository):
    def list_all(self) -> list[dict]:
        return self._all("SELECT * FROM roles ORDER BY is_system DESC, name")

    def get_by_code(self, code: str) -> dict | None:
        return self._one("SELECT * FROM roles WHERE code = ?", (code,))

    def id_by_code(self, code: str) -> int | None:
        return self._scalar("SELECT id FROM roles WHERE code = ?", (code,))

    def create(self, *, code: str, name: str, description: str | None = None,
               is_system: bool = False) -> int:
        ts = now_iso()
        return self._insert(
            "INSERT INTO roles (code, name, description, is_system, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (code, name, description, 1 if is_system else 0, ts, ts),
        )

    def set_permissions(self, role_id: int, permission_ids: list[int]) -> None:
        self._exec("DELETE FROM role_permissions WHERE role_id = ?", (role_id,))
        for pid in permission_ids:
            self._exec(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES (?, ?)",
                (role_id, pid),
            )

    def permissions_for_role(self, role_id: int) -> set[str]:
        rows = self._all(
            "SELECT p.code FROM permissions p JOIN role_permissions rp ON rp.permission_id = p.id"
            " WHERE rp.role_id = ?",
            (role_id,),
        )
        return {r["code"] for r in rows}


class PermissionRepository(BaseRepository):
    def list_codes(self) -> list[str]:
        return [r["code"] for r in self._all("SELECT code FROM permissions ORDER BY code")]

    def id_by_code(self, code: str) -> int | None:
        return self._scalar("SELECT id FROM permissions WHERE code = ?", (code,))

    def map_codes(self) -> dict[str, int]:
        return {r["code"]: r["id"] for r in self._all("SELECT id, code FROM permissions")}
