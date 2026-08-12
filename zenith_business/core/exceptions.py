"""Foundation exception hierarchy (Prompt 01 §8, §24).

A small, clean base for future domain-specific exceptions. Domain modules
(accounting, inventory, sales, ...) will subclass :class:`ZenithError` rather
than raising bare ``Exception``. This lets the global handler and the service
layer distinguish *expected, user-presentable* errors from *unexpected* bugs.

Never swallow exceptions broadly (``except: pass``). Catch specific types and
either handle or re-raise.
"""

from __future__ import annotations


class ZenithError(Exception):
    """Base class for all application-raised errors.

    Parameters
    ----------
    message:
        Technical message for logs/developers.
    user_message:
        Optional friendly message safe to show a non-technical user. When
        omitted, callers should show a generic message rather than the raw
        technical text.
    """

    #: Default user-facing message when a subclass provides none.
    default_user_message = "An unexpected error occurred."

    def __init__(self, message: str, *, user_message: str | None = None) -> None:
        super().__init__(message)
        self.user_message = user_message or self.default_user_message


class ConfigurationError(ZenithError):
    """Raised when configuration cannot be loaded or is invalid."""

    default_user_message = "The application configuration could not be loaded."


class DatabaseError(ZenithError):
    """Raised for database infrastructure failures (connection, pragmas, etc.)."""

    default_user_message = "A database error occurred."


class TransactionError(DatabaseError):
    """Raised when a database transaction cannot be started/committed/rolled back."""

    default_user_message = "The operation could not be completed safely."


class SecurityError(ZenithError):
    """Base for authentication/authorization/licensing failures."""

    default_user_message = "A security check failed."


class LicensingError(SecurityError):
    """Raised for licensing/activation failures (future engine)."""

    default_user_message = "The application license could not be verified."
