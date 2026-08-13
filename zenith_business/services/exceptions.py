"""Service-layer error types (Stage 02 §11, §14, §48).

These subclass the Stage 01 :class:`SecurityError` / :class:`ZenithError`
hierarchy so the global handler and callers can distinguish expected,
user-presentable failures from bugs. No secrets or passwords are ever placed in
these messages.
"""

from __future__ import annotations

from zenith_business.core.exceptions import SecurityError, ZenithError


class AuthenticationError(SecurityError):
    """Login failed (bad credentials, inactive/locked account)."""

    default_user_message = "Incorrect username or password."


class AccountLockedError(AuthenticationError):
    """The account is temporarily locked after too many failed attempts."""

    default_user_message = "This account is locked. Please try again later."


class AccountInactiveError(AuthenticationError):
    """The account exists but has been deactivated."""

    default_user_message = "This account is not active. Contact your administrator."


class AuthorizationError(SecurityError):
    """The current user lacks the permission required for an action."""

    default_user_message = "You do not have permission to perform this action."


class ValidationError(ZenithError):
    """A service rejected invalid input before touching the database."""

    default_user_message = "Some information is missing or invalid."


class SetupError(ZenithError):
    """Initial-setup preconditions were violated (e.g. setup already done)."""

    default_user_message = "The initial setup could not be completed."
