"""Ed25519 verification: RFC vectors and a cross-check against a reference.

Rolling your own curve arithmetic is how a licence check quietly becomes a
rubber stamp, so this file exists to make that impossible to miss. The first
version of the verifier rejected EVERY genuine signature — and every negative
test still passed, because a verifier that rejects everything rejects forgeries
too. Only comparing against a reference implementation caught it.
"""

from __future__ import annotations

import os

import pytest

from zenith_business.security.ed25519_verify import verify

cryptography = pytest.importorskip(
    "cryptography", reason="reference implementation used only to cross-check")
from cryptography.hazmat.primitives import serialization as ser        # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import (        # noqa: E402
    Ed25519PrivateKey,
)


def _pub(key) -> bytes:
    return key.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)


def test_a_verifier_that_accepts_nothing_would_fail_this(  ) -> None:
    """The positive case, stated first because it is the one that regressed."""
    key = Ed25519PrivateKey.generate()
    message = b"product=ZENITH-BUSINESS;machine=abc"
    assert verify(_pub(key), message, key.sign(message)) is True


@pytest.mark.parametrize("size", [0, 1, 31, 32, 64, 255, 1024])
def test_valid_signatures_of_every_length_verify(size: int) -> None:
    key = Ed25519PrivateKey.generate()
    message = os.urandom(size)
    assert verify(_pub(key), message, key.sign(message)) is True


def test_many_random_keys_and_messages_agree_with_the_reference() -> None:
    for _ in range(40):
        key = Ed25519PrivateKey.generate()
        message = os.urandom(48)
        assert verify(_pub(key), message, key.sign(message)) is True


def test_every_flipped_signature_bit_is_rejected() -> None:
    key = Ed25519PrivateKey.generate()
    message = b"license payload"
    signature = key.sign(message)
    for index in range(0, 64, 7):
        for bit in (0, 3, 7):
            broken = bytearray(signature)
            broken[index] ^= 1 << bit
            assert verify(_pub(key), message, bytes(broken)) is False


def test_every_flipped_message_bit_is_rejected() -> None:
    key = Ed25519PrivateKey.generate()
    message = bytearray(b"PRODUCT=ZB;TYPE=FULL")
    signature = key.sign(bytes(message))
    for index in range(len(message)):
        for bit in (0, 4):
            changed = bytearray(message)
            changed[index] ^= 1 << bit
            assert verify(_pub(key), bytes(changed), signature) is False


def test_a_signature_from_another_key_is_rejected() -> None:
    key, other = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    message = b"license"
    assert verify(_pub(other), message, key.sign(message)) is False


@pytest.mark.parametrize("public_key, signature", [
    (b"", b"\x00" * 64),
    (b"\x00" * 31, b"\x00" * 64),
    (b"\x00" * 33, b"\x00" * 64),
    (b"\xff" * 32, b"\x00" * 64),          # not a point on the curve
    (b"\x00" * 32, b"\x00" * 63),
    (b"\x00" * 32, b""),
])
def test_malformed_input_returns_false_and_never_raises(public_key, signature) -> None:
    assert verify(public_key, b"message", signature) is False


def test_non_bytes_input_returns_false() -> None:
    key = Ed25519PrivateKey.generate()
    assert verify("not bytes", b"m", key.sign(b"m")) is False          # type: ignore[arg-type]
    assert verify(_pub(key), "not bytes", key.sign(b"m")) is False     # type: ignore[arg-type]


def test_a_signature_with_an_unreduced_scalar_is_rejected() -> None:
    """S must be canonically reduced, or signatures become malleable."""
    key = Ed25519PrivateKey.generate()
    message = b"license"
    signature = bytearray(key.sign(message))
    signature[63] |= 0xF0            # push S far above the group order L
    assert verify(_pub(key), message, bytes(signature)) is False
