"""Ed25519 signature **verification** — pure standard library (RFC 8032).

Why this module exists at all
-----------------------------
License verification must be **asymmetric**: the customer application has to be
able to check a signature without holding anything that could produce one
(§26-§28, and the Stage 10 rule that no private key and no license-generation
capability may ship). The project also declares its runtime dependencies as
PyQt6 and nothing else (Master Spec §2), and a licensing check is exactly the
wrong place to add a heavyweight native dependency that must then be bundled,
signed and kept current inside a PyInstaller build.

So verification is implemented here against RFC 8032 using ``hashlib`` and
Python integers only.

**This module can verify. It cannot sign.** There is deliberately no function
here that accepts a private key, expands a seed, or produces a signature —
signing lives only in test tooling that never enters the application package.
The elliptic-curve arithmetic below is public mathematics; the secret is the
vendor's private key, which does not exist anywhere in this repository's
application code.

Correctness is not taken on trust: ``tests/test_stage10_ed25519.py`` checks this
implementation against fixed RFC 8032 test vectors **and** cross-checks it
against the reference ``cryptography`` implementation over randomised
keys/messages, including rejection of tampered signatures, wrong keys and
malformed input.
"""

from __future__ import annotations

import hashlib

# Curve25519 / edwards25519 domain parameters (RFC 8032 §5.1).
_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)

#: Base point B.
_BY = 4 * pow(5, _P - 2, _P) % _P
_BX = 15112221349535400772501151409588531511454012693041857206046113283949847762202

SIGNATURE_BYTES = 64
PUBLIC_KEY_BYTES = 32

# Points are kept in extended homogeneous coordinates (X, Y, Z, T) with
# x = X/Z, y = Y/Z and x*y = T/Z. Affine arithmetic would need a modular
# inverse per step; this needs one at the very end.
_Point = tuple[int, int, int, int]

_BASE: _Point = (_BX, _BY, 1, _BX * _BY % _P)
_IDENTITY: _Point = (0, 1, 1, 0)


def _add(p: _Point, q: _Point) -> _Point:
    """Twisted Edwards addition (RFC 8032 §5.1.4), complete for this curve."""
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = (y1 - x1) * (y2 - x2) % _P
    b = (y1 + x1) * (y2 + x2) % _P
    c = 2 * t1 * t2 * _D % _P
    dd = 2 * z1 * z2 % _P
    e = b - a
    f = dd - c
    g = dd + c
    h = b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _scalar_mult(point: _Point, scalar: int) -> _Point:
    """Constant-shape double-and-add. Verification handles only public data."""
    result = _IDENTITY
    addend = point
    while scalar > 0:
        if scalar & 1:
            result = _add(result, addend)
        addend = _add(addend, addend)
        scalar >>= 1
    return result


def _equal(p: _Point, q: _Point) -> bool:
    """Compare two projective points without leaving projective space."""
    x1, y1, z1, _ = p
    x2, y2, z2, _ = q
    if (x1 * z2 - x2 * z1) % _P != 0:
        return False
    return (y1 * z2 - y2 * z1) % _P == 0


def _recover_x(y: int, sign: int) -> int | None:
    """Recover the x coordinate from a compressed point, or None if invalid."""
    if y >= _P:
        return None
    u = (y * y - 1) % _P
    v = (_D * y * y + 1) % _P
    # x = u*v^3 * (u*v^7)^((p-5)/8)  — RFC 8032 §5.1.3. Both halves matter: an
    # earlier form here dropped the (u*v^7) factor and rejected every genuine
    # signature, which the negative tests could not have caught.
    x = (u * pow(v, 3, _P) % _P) * pow(u * pow(v, 7, _P) % _P, (_P - 5) // 8, _P) % _P
    if (v * x * x - u) % _P != 0:
        x = x * _SQRT_M1 % _P
        if (v * x * x - u) % _P != 0:
            return None              # not a point on the curve
    if x == 0 and sign:
        return None                  # non-canonical encoding of zero
    if x % 2 != sign:
        x = _P - x
    return x


def _decompress(data: bytes) -> _Point | None:
    """Decode a 32-byte compressed point, or None when it is not a valid point."""
    if len(data) != PUBLIC_KEY_BYTES:
        return None
    value = int.from_bytes(data, "little")
    sign = value >> 255
    y = value & ((1 << 255) - 1)
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Return True only if ``signature`` is a valid Ed25519 signature.

    Returns False — never raises — for every malformed input, so a caller can
    never accidentally treat a parse failure as a valid licence.
    """
    if not isinstance(public_key, (bytes, bytearray)) \
            or not isinstance(signature, (bytes, bytearray)) \
            or not isinstance(message, (bytes, bytearray)):
        return False
    if len(signature) != SIGNATURE_BYTES or len(public_key) != PUBLIC_KEY_BYTES:
        return False

    try:
        a_point = _decompress(bytes(public_key))
        if a_point is None:
            return False
        r_bytes = bytes(signature[:32])
        r_point = _decompress(r_bytes)
        if r_point is None:
            return False
        s = int.from_bytes(signature[32:], "little")
        # S must be canonically reduced: without this check a valid signature
        # can be trivially mutated into another "valid" one (malleability).
        if s >= _L:
            return False

        digest = hashlib.sha512(r_bytes + bytes(public_key) + bytes(message)).digest()
        k = int.from_bytes(digest, "little") % _L

        # [S]B == R + [k]A
        left = _scalar_mult(_BASE, s)
        right = _add(r_point, _scalar_mult(a_point, k))
        return _equal(left, right)
    except (ValueError, OverflowError):
        return False
