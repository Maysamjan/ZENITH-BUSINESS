"""Authorization service — permission enforcement (Stage 02 §14).

Permissions are enforced HERE, at the service layer, not merely by hiding UI
controls. Every guarded business operation calls :meth:`require` before doing
work, so an unauthorized call fails even if it bypasses the UI.
"""

from __future__ import annotations

from zenith_business.services.exceptions import AuthenticationError, AuthorizationError
from zenith_business.services.session import SessionContext


class AuthorizationService:
    def __init__(self, session: SessionContext) -> None:
        self._session = session

    def can(self, code: str) -> bool:
        user = self._session.user
        return user is not None and user.has_permission(code)

    def require(self, code: str) -> None:
        """Raise unless the current user holds ``code``.

        Raises :class:`AuthenticationError` when nobody is signed in, and
        :class:`AuthorizationError` when signed in without the permission.
        """
        user = self._session.user
        if user is None:
            raise AuthenticationError("No authenticated user for a permission-guarded action.")
        if not user.has_permission(code):
            raise AuthorizationError(
                f"User {user.username!r} lacks required permission {code!r}."
            )

    def require_any(self, *codes: str) -> None:
        user = self._session.user
        if user is None:
            raise AuthenticationError("No authenticated user for a permission-guarded action.")
        if not user.has_any(*codes):
            raise AuthorizationError(
                f"User {user.username!r} lacks any of the required permissions {codes!r}."
            )
