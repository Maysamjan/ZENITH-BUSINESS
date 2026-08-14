"""Password policy (Stage 02 §10, §37).

A single place that decides whether a chosen password is acceptable, so the
Login/Setup UI and the user-management service enforce the same rules. The policy
is intentionally modest but real: it blocks empty, too-short and obviously weak
passwords (including the forbidden ``admin`` default), without imposing rules that
frustrate legitimate users.
"""

from __future__ import annotations

from zenith_business.services.exceptions import ValidationError

MIN_LENGTH = 8

# Obvious weak/default choices that must never be accepted (§10 forbids admin/admin).
_FORBIDDEN = {
    "admin", "administrator", "password", "12345678", "123456789",
    "qwerty", "11111111", "00000000", "zenith", "changeme",
}


def validate_password(password: str, *, username: str | None = None) -> None:
    """Raise :class:`ValidationError` if ``password`` is unacceptable."""
    if not isinstance(password, str) or password == "":
        raise ValidationError("Password is required.",
                              user_message="Please enter a password.")
    if len(password) < MIN_LENGTH:
        raise ValidationError(
            "Password too short.",
            user_message=f"Password must be at least {MIN_LENGTH} characters.")
    if password.lower() in _FORBIDDEN:
        raise ValidationError(
            "Password is too common/weak.",
            user_message="This password is too common. Choose a stronger one.")
    if username and password.lower() == username.strip().lower():
        raise ValidationError(
            "Password must not equal the username.",
            user_message="Password must be different from the username.")
