"""Request Codes and Product Keys — licensing by copy and paste (Stage 10 final).

The security model does not change here. A Product Key is the **same signed
licence** as a ``.zlic``: same Ed25519 signature, same machine binding, same
expiry, same public-key-only verification in the customer application. What
changes is the shape it travels in — a line of text a customer can copy out of
a message and paste into a box, instead of a file they have to save, attach and
find again.

Why a compact binary payload
----------------------------
A ``.zlic`` is readable JSON, which is right for a file and hopeless for a key:
base64 of it runs past a thousand characters. So the same facts are packed into
a fixed binary layout and then encoded as base32, which gives roughly 180-220
characters — long enough that it is meant to be **pasted, not typed**, and short
enough to survive a WhatsApp message intact.

Nothing is dropped to achieve that. The fingerprint, every machine trait, the
licence type, the issue and expiry dates, the serial and the customer name are
all present, all covered by the signature, and all checked exactly as the file
path checks them.

Two codes, and why the request needs one too
--------------------------------------------
``ZBR1-…`` **Request Code** — what the customer sends. It carries this machine's
fingerprint and hashed traits, so the vendor can bind the licence to it. A short
human Machine ID alone would not be enough: the traits are what let a licence
survive a disk swap, and they cannot be recovered from a truncated id. It is not
secret and not signed — the customer has nothing to sign with, which is the
whole point — so it carries a checksum instead, to catch a code that was mangled
in transit before a licence is issued against the wrong machine.

``ZB1-…`` **Product Key** — what comes back. Signed, and useless on any other
computer.

This module has **no keys and cannot sign**. It packs, unpacks and describes.
Signing exists only in the vendor tool.
"""

from __future__ import annotations

import base64
import binascii
import struct
from dataclasses import dataclass
from datetime import date

from zenith_business.security.license_format import (
    PRODUCT_ID,
    TYPE_DEMO,
    TYPE_FULL,
    LicenseFormatError,
)

#: Prefixes, so a customer pasting the wrong one is told which is which.
REQUEST_PREFIX = "ZBR1"
LICENSE_PREFIX = "ZB1"

#: Format version, first byte of both payloads.
VERSION = 1

#: Traits in a FIXED order — the bitmap and the layout both depend on it.
TRAIT_ORDER = ("machine_guid", "volume_serial", "mac", "cpu", "hostname")

#: Bytes kept per trait hash. The fingerprint (16 bytes) is what decides a
#: match; traits only ever *tolerate* a change, so four bytes each is ample and
#: keeps the key short. A collision here would have to happen on a machine that
#: already failed the fingerprint check.
TRAIT_BYTES = 4
FINGERPRINT_BYTES = 16

#: Dates travel as days since this epoch, in two bytes — good to 2199.
EPOCH = date(2020, 1, 1)

#: A name longer than this is truncated rather than making the key unwieldy.
MAX_NAME = 40

_TYPE_CODES = {TYPE_DEMO: 0, TYPE_FULL: 1}
_CODE_TYPES = {v: k for k, v in _TYPE_CODES.items()}

#: Characters a paste or a retype commonly mangles. Base32 has no 0/1/8/9, so
#: these are unambiguous repairs rather than guesses.
_CONFUSIONS = str.maketrans({"0": "O", "1": "I", "8": "B", "9": "G"})

_ALPHABET = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")


class ProductKeyError(LicenseFormatError):
    """The code is not a well-formed Zenith request or product key."""


# ---------------------------------------------------------------------------
# text <-> bytes
# ---------------------------------------------------------------------------


def _group(text: str, size: int = 5) -> str:
    return "-".join(text[i:i + size] for i in range(0, len(text), size))


def encode_text(prefix: str, payload: bytes) -> str:
    """Base32, uppercase, no padding, dashed into readable groups."""
    body = base64.b32encode(payload).decode("ascii").rstrip("=")
    return f"{prefix}-{_group(body)}"


def decode_text(prefix: str, text: str) -> bytes:
    """Undo :func:`encode_text`, forgiving whitespace, case and the odd typo."""
    if not text:
        raise ProductKeyError("No code was entered.")
    cleaned = "".join(text.split()).upper().replace("—", "-").replace("–", "-")
    # The prefix is matched with or WITHOUT its dash. Both prefixes contain a
    # digit that base32 does not use, so they can never be part of the body and
    # this cannot mis-detect — while a message that reflowed and swallowed the
    # first separator still activates instead of being refused over a hyphen.
    for candidate in (REQUEST_PREFIX, LICENSE_PREFIX):
        if cleaned.startswith(candidate):
            if candidate != prefix:
                raise ProductKeyError(
                    f"That is a {candidate} code, not a {prefix} code.")
            cleaned = cleaned[len(candidate):].lstrip("-")
            break
    else:
        raise ProductKeyError(f"A {prefix} code must start with {prefix}-.")

    body = cleaned.replace("-", "").translate(_CONFUSIONS)
    if not body or any(ch not in _ALPHABET for ch in body):
        raise ProductKeyError("The code contains characters that are not part of it.")
    padding = "=" * (-len(body) % 8)
    try:
        return base64.b32decode(body + padding)
    except (binascii.Error, ValueError) as exc:
        raise ProductKeyError("The code is incomplete or damaged.") from exc


def _checksum(data: bytes) -> bytes:
    return struct.pack(">H", binascii.crc32(data) & 0xFFFF)


# ---------------------------------------------------------------------------
# machine traits <-> bytes
# ---------------------------------------------------------------------------


def _pack_traits(traits: dict[str, str]) -> tuple[int, bytes]:
    bitmap = 0
    packed = b""
    for index, name in enumerate(TRAIT_ORDER):
        value = (traits or {}).get(name)
        if not value:
            continue
        try:
            raw = bytes.fromhex(value[:TRAIT_BYTES * 2])
        except ValueError:
            continue
        if len(raw) != TRAIT_BYTES:
            continue
        bitmap |= 1 << index
        packed += raw
    return bitmap, packed


def _unpack_traits(bitmap: int, data: bytes) -> tuple[dict[str, str], int]:
    traits: dict[str, str] = {}
    cursor = 0
    for index, name in enumerate(TRAIT_ORDER):
        if not bitmap & (1 << index):
            continue
        chunk = data[cursor:cursor + TRAIT_BYTES]
        if len(chunk) != TRAIT_BYTES:
            raise ProductKeyError("The code is incomplete or damaged.")
        traits[name] = chunk.hex()
        cursor += TRAIT_BYTES
    return traits, cursor


def _pack_day(value: str | None) -> int:
    if not value:
        return 0
    try:
        day = date.fromisoformat(str(value)[:10])
    except ValueError:
        return 0
    delta = (day - EPOCH).days
    return delta if 0 < delta < 0xFFFF else 0


def _unpack_day(value: int) -> str | None:
    if not value:
        return None
    from datetime import timedelta

    return (EPOCH + timedelta(days=value)).isoformat()


# ---------------------------------------------------------------------------
# request code
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActivationRequest:
    """What a Request Code says: which machine is asking."""

    fingerprint: str
    traits: dict[str, str]

    @property
    def machine_short(self) -> str:
        text = self.fingerprint.upper()
        return "-".join(text[i:i + 4] for i in range(0, min(len(text), 16), 4))


def encode_request(*, fingerprint: str, traits: dict[str, str]) -> str:
    """Build the code a customer copies and sends to the vendor."""
    try:
        raw = bytes.fromhex(fingerprint)[:FINGERPRINT_BYTES]
    except ValueError as exc:
        raise ProductKeyError("The machine fingerprint is not readable.") from exc
    if len(raw) != FINGERPRINT_BYTES:
        raise ProductKeyError("The machine fingerprint is the wrong length.")
    bitmap, packed = _pack_traits(traits)
    body = struct.pack(">BB", VERSION, bitmap) + raw + packed
    return encode_text(REQUEST_PREFIX, body + _checksum(body))


def decode_request(text: str) -> ActivationRequest:
    """Read a Request Code. Raises :class:`ProductKeyError` — never guesses."""
    data = decode_text(REQUEST_PREFIX, text)
    if len(data) < 2 + FINGERPRINT_BYTES + 2:
        raise ProductKeyError("The code is incomplete or damaged.")
    body, checksum = data[:-2], data[-2:]
    if _checksum(body) != checksum:
        # Caught here rather than by the vendor, who would otherwise issue a
        # licence bound to a machine that does not exist.
        raise ProductKeyError("The code did not check out — a character is wrong "
                              "or missing. Please copy it again.")
    version, bitmap = struct.unpack(">BB", body[:2])
    if version != VERSION:
        raise ProductKeyError(f"Unsupported request code version {version}.")
    fingerprint = body[2:2 + FINGERPRINT_BYTES].hex()
    traits, _ = _unpack_traits(bitmap, body[2 + FINGERPRINT_BYTES:])
    return ActivationRequest(fingerprint=fingerprint, traits=traits)


# ---------------------------------------------------------------------------
# product key
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProductKeyLicense:
    """A decoded Product Key, shaped like a parsed ``.zlic``.

    It deliberately exposes the same names as
    :class:`~zenith_business.security.license_format.LicenseFile`, so the
    licence service verifies and judges both through one code path. Two
    verification routines for two file shapes is how they drift apart.
    """

    signed_bytes: bytes
    signature: bytes
    license_type: str
    machine_fingerprint: str
    machine_traits: dict[str, str]
    issued_at: str
    expires_at: str | None
    serial: int
    issued_to: str

    @property
    def product_id(self) -> str:
        # A Product Key is issued for this product by construction: the vendor
        # tool writes this format and nothing else reads it.
        return PRODUCT_ID

    @property
    def license_id(self) -> str:
        return f"ZB-{self.license_type}-{self.serial:06d}"


def build_license_payload(*, license_type: str, fingerprint: str,
                          traits: dict[str, str], issued_at: str,
                          expires_at: str | None, serial: int,
                          issued_to: str = "") -> bytes:
    """The exact bytes a Product Key signature is computed over.

    Public because the vendor tool signs these bytes and the customer
    application verifies them; both must agree to the byte, and the only way to
    guarantee that is for both to call this.
    """
    kind = _TYPE_CODES.get((license_type or "").upper())
    if kind is None:
        raise ProductKeyError(f"Unknown license type {license_type!r}.")
    try:
        raw = bytes.fromhex(fingerprint)[:FINGERPRINT_BYTES]
    except ValueError as exc:
        raise ProductKeyError("The machine fingerprint is not readable.") from exc
    if len(raw) != FINGERPRINT_BYTES:
        raise ProductKeyError("The machine fingerprint is the wrong length.")
    bitmap, packed = _pack_traits(traits)
    name = (issued_to or "").strip()[:MAX_NAME].encode("utf-8")[:MAX_NAME]
    return (struct.pack(">BBB", VERSION, kind, bitmap) + raw + packed
            + struct.pack(">HHIB", _pack_day(issued_at), _pack_day(expires_at),
                          int(serial) & 0xFFFFFFFF, len(name)) + name)


def encode_license(payload: bytes, signature: bytes) -> str:
    """Wrap a signed payload into the key the customer pastes."""
    if len(signature) != 64:
        raise ProductKeyError("An Ed25519 signature is 64 bytes.")
    return encode_text(LICENSE_PREFIX, payload + signature)


def decode_license(text: str) -> ProductKeyLicense:
    """Read a Product Key WITHOUT trusting any of it.

    Nothing returned here has been verified — the signature check happens in the
    licence service, over :attr:`ProductKeyLicense.signed_bytes`, before any
    field is believed. This function's only job is to fail cleanly on anything
    that is not the right shape.
    """
    data = decode_text(LICENSE_PREFIX, text)
    if len(data) < 3 + FINGERPRINT_BYTES + 9 + 64:
        raise ProductKeyError("The product key is incomplete or damaged.")
    payload, signature = data[:-64], data[-64:]

    version, kind, bitmap = struct.unpack(">BBB", payload[:3])
    if version != VERSION:
        raise ProductKeyError(f"Unsupported product key version {version}.")
    license_type = _CODE_TYPES.get(kind)
    if license_type is None:
        raise ProductKeyError("The product key names a license type this build "
                              "does not understand.")
    cursor = 3
    fingerprint = payload[cursor:cursor + FINGERPRINT_BYTES].hex()
    cursor += FINGERPRINT_BYTES
    traits, used = _unpack_traits(bitmap, payload[cursor:])
    cursor += used

    tail = payload[cursor:cursor + 9]
    if len(tail) != 9:
        raise ProductKeyError("The product key is incomplete or damaged.")
    issued, expires, serial, name_length = struct.unpack(">HHIB", tail)
    cursor += 9
    name_bytes = payload[cursor:cursor + name_length]
    if len(name_bytes) != name_length:
        raise ProductKeyError("The product key is incomplete or damaged.")

    issued_at = _unpack_day(issued)
    if issued_at is None:
        raise ProductKeyError("The product key has no issue date.")
    return ProductKeyLicense(
        signed_bytes=payload, signature=signature, license_type=license_type,
        machine_fingerprint=fingerprint, machine_traits=traits,
        issued_at=issued_at, expires_at=_unpack_day(expires), serial=serial,
        issued_to=name_bytes.decode("utf-8", "replace"))


def looks_like_product_key(text: str) -> bool:
    """Whether this text is meant to be a Product Key, valid or not."""
    return "".join((text or "").split()).upper().startswith(LICENSE_PREFIX + "-")
