"""Ed25519 signature verification for licences (Stage 10 hardening §4).

**This delegates to `cryptography`, a well-vetted, widely-audited library.** An
earlier revision carried a hand-written RFC 8032 implementation to keep the
runtime dependency list at PyQt6 alone. That trade is not worth making for the
one piece of code whose failure mode is silent: the hand-written verifier's
first revision rejected *every* genuine signature because of a dropped factor in
the x-recovery formula, and every negative test still passed, because a verifier
that rejects everything also rejects forgeries. A subtler error in the other
direction — accepting something it should not — would have been just as quiet.

So the curve arithmetic is now somebody else's job, and a well-reviewed
somebody's.

**Fail-closed.** If the library cannot be imported, :func:`verify` returns False
rather than raising or, worse, waving the licence through. A build that cannot
verify is a build that is not licensed.

The application can verify and cannot sign: nothing here accepts a private key,
and `cryptography`'s signing classes are never imported.
"""

from __future__ import annotations

from zenith_business.core.logging_setup import get_logger

_logger = get_logger("security.signatures")

SIGNATURE_BYTES = 64
PUBLIC_KEY_BYTES = 32


def backend_available() -> bool:
    """Whether a verification backend is present in this build."""
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: F401
            Ed25519PublicKey,
        )
    except Exception:
        return False
    return True


def backend_name() -> str:
    """What is doing the verifying, for the License screen and the audit trail."""
    try:
        import cryptography

        return f"cryptography {cryptography.__version__}"
    except Exception:
        return "unavailable"


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """True only if ``signature`` is a valid Ed25519 signature over ``message``.

    Returns False — never raises — for every malformed input and for a missing
    backend, so no caller can mistake an error for a valid licence.
    """
    if not isinstance(public_key, (bytes, bytearray)) \
            or not isinstance(signature, (bytes, bytearray)) \
            or not isinstance(message, (bytes, bytearray)):
        return False
    if len(signature) != SIGNATURE_BYTES or len(public_key) != PUBLIC_KEY_BYTES:
        return False

    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except Exception:
        # No verification backend: refuse rather than assume.
        _logger.error("No Ed25519 backend available; licences cannot be verified.")
        return False

    try:
        key = Ed25519PublicKey.from_public_bytes(bytes(public_key))
    except Exception:
        return False        # not a valid point / malformed key

    try:
        key.verify(bytes(signature), bytes(message))
    except InvalidSignature:
        return False
    except Exception:
        return False
    return True
