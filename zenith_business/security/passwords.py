"""Password hashing readiness (Prompt 01 §29, §38-security).

The application must NEVER store or compare plaintext passwords. This module
provides a correct, dependency-free hashing primitive so no part of the system
is ever tempted to design around plaintext.

Algorithm: PBKDF2-HMAC-SHA256 with a per-password random salt and a high
iteration count, from the Python standard library (``hashlib``). This is a
legitimate, widely accepted password KDF. The full user-management/security
module may later upgrade to Argon2id/bcrypt behind this same interface; the
stored format is versioned (the ``pbkdf2_sha256`` prefix) so a future migration
can detect and rehash old hashes.

Stored format (single self-describing string, safe to keep in a DB column)::

    pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>

No secrets, keys, or passwords are logged or hard-coded here.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

_ALGORITHM = "pbkdf2_sha256"
_DEFAULT_ITERATIONS = 240_000  # tuned for interactive login; revisit periodically
_SALT_BYTES = 16
_HASH_BYTES = 32


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def hash_password(password: str, *, iterations: int = _DEFAULT_ITERATIONS) -> str:
    """Return a self-describing PBKDF2 hash for ``password``.

    A fresh random salt is generated per call, so identical passwords yield
    different stored values.
    """
    if not isinstance(password, str) or password == "":
        raise ValueError("Password must be a non-empty string.")
    salt = os.urandom(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, dklen=_HASH_BYTES
    )
    return f"{_ALGORITHM}${iterations}${_b64(salt)}${_b64(derived)}"


def verify_password(password: str, stored: str) -> bool:
    """Verify ``password`` against a stored hash using constant-time compare.

    Returns False for malformed stored values rather than raising, so callers
    cannot accidentally authenticate on a parse error.
    """
    try:
        algorithm, iter_text, salt_text, hash_text = stored.split("$", 3)
        if algorithm != _ALGORITHM:
            return False
        iterations = int(iter_text)
        salt = _unb64(salt_text)
        expected = _unb64(hash_text)
    except (ValueError, AttributeError):
        return False

    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, dklen=len(expected)
    )
    return hmac.compare_digest(derived, expected)


def needs_rehash(stored: str, *, iterations: int = _DEFAULT_ITERATIONS) -> bool:
    """Return True if a stored hash uses weaker parameters and should be rehashed."""
    try:
        algorithm, iter_text, _, _ = stored.split("$", 3)
    except (ValueError, AttributeError):
        return True
    return algorithm != _ALGORITHM or int(iter_text) < iterations
