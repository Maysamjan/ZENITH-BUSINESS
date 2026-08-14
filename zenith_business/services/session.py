"""Authenticated session context (Stage 02 §15).

After a successful login the application holds a single :class:`SessionContext`
describing WHO is acting and WHAT they may do. Every service consults it for the
acting user id (audit/attribution) and permission set (authorization). Nothing
here touches the database — it is a plain, immutable-ish snapshot loaded at login
and refreshed only through explicit calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CurrentUser:
    """Immutable snapshot of the signed-in user (no password material)."""

    id: int
    username: str
    full_name: str
    preferred_language: str
    role_codes: tuple[str, ...] = ()
    permissions: frozenset[str] = field(default_factory=frozenset)

    def has_permission(self, code: str) -> bool:
        return code in self.permissions

    def has_any(self, *codes: str) -> bool:
        return any(c in self.permissions for c in codes)


class SessionContext:
    """Holds the currently authenticated user for the running application.

    A single instance lives in the :class:`ApplicationContext`. It is empty
    before login and after logout; services that require a user raise rather than
    silently acting as nobody.
    """

    def __init__(self) -> None:
        self._user: CurrentUser | None = None

    @property
    def user(self) -> CurrentUser | None:
        return self._user

    @property
    def is_authenticated(self) -> bool:
        return self._user is not None

    @property
    def user_id(self) -> int | None:
        return self._user.id if self._user else None

    @property
    def username(self) -> str | None:
        return self._user.username if self._user else None

    def start(self, user: CurrentUser) -> None:
        self._user = user

    def clear(self) -> None:
        self._user = None

    def has_permission(self, code: str) -> bool:
        return self._user is not None and self._user.has_permission(code)
