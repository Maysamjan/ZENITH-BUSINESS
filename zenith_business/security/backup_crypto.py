"""Encrypted, tamper-evident backup container (Stage 10 hardening §2).

A backup used to be a plain SQLite file. Anyone who picked up the USB stick could
read every customer, price and balance in the business, and anyone who edited a
byte could hand it back to be restored. Both are fixed by putting the database
inside an authenticated container.

Format — ``.zbak`` v1
---------------------
::

    magic      8 bytes   b"ZBAK1\\x00\\x00\\x00"[:8]
    header_len 4 bytes   big-endian
    header     JSON, UTF-8, NOT encrypted but AUTHENTICATED
    nonce     12 bytes
    body                 AES-256-GCM ciphertext + 16-byte tag

The header carries the created-at time, the schema version and a KDF
description. It is deliberately readable **without** the passphrase, so the
Backup screen can list and describe backups — a customer should not have to
unlock a file to find out which one it is. It is fed to GCM as additional
authenticated data, so it cannot be edited either.

Key derivation is **scrypt** (n=2^15, r=8, p=1) over a 16-byte random salt.
Encryption is **AES-256-GCM** from `cryptography` — authenticated, so a single
altered byte anywhere in the header or the body fails the tag check and the file
is refused *before* a restore begins. There is no "decrypt and hope" path.

Two deliberate decisions
------------------------
**Legacy plain ``.db`` backups still restore.** Existing customer backups were
written before this existed and must not become unreadable — that would be this
change destroying data instead of protecting it. :func:`looks_encrypted` tells
the two apart by magic bytes.

**The passphrase is not stored anywhere.** That is the point, and it is also the
risk: a lost passphrase means a backup that cannot be opened, by anyone,
including us. The application says so plainly rather than quietly keeping a copy
that would undo the protection.
"""

from __future__ import annotations

import json
import os
import struct
from dataclasses import dataclass
from pathlib import Path

MAGIC = b"ZBAK1\x00\x00\x00"
SALT_BYTES = 16
NONCE_BYTES = 12
KEY_BYTES = 32
TAG_BYTES = 16

#: scrypt work factors. Chosen to cost a noticeable fraction of a second on a
#: desktop: enough to make guessing a weak passphrase expensive, not enough to
#: make a backup feel broken.
SCRYPT_N = 2 ** 15
SCRYPT_R = 8
SCRYPT_P = 1


class BackupCryptoError(Exception):
    """The container could not be produced or opened."""


class WrongPassphrase(BackupCryptoError):
    """Authentication failed: wrong passphrase, or the file was altered."""


@dataclass(frozen=True)
class BackupHeader:
    """What a backup says about itself without being unlocked."""

    created_at: str
    schema_version: int | None
    app_version: str
    product: str
    hint: str = ""

    def to_json(self) -> dict:
        return {"v": 1, "created_at": self.created_at,
                "schema_version": self.schema_version,
                "app_version": self.app_version, "product": self.product,
                "hint": self.hint, "kdf": "scrypt",
                "n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P,
                "cipher": "AES-256-GCM"}

    @staticmethod
    def from_json(data: dict) -> "BackupHeader":
        return BackupHeader(
            created_at=str(data.get("created_at", "")),
            schema_version=data.get("schema_version"),
            app_version=str(data.get("app_version", "")),
            product=str(data.get("product", "")),
            hint=str(data.get("hint", "")))


def available() -> bool:
    """Whether this build can encrypt backups."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt    # noqa: F401
    except Exception:
        return False
    return True


def looks_encrypted(path: str | Path) -> bool:
    """True for a ``.zbak`` container, False for a plain SQLite backup."""
    try:
        with open(path, "rb") as handle:
            return handle.read(len(MAGIC)) == MAGIC
    except OSError:
        return False


def _derive(passphrase: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    kdf = Scrypt(salt=salt, length=KEY_BYTES, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_file(source: str | Path, target: str | Path, passphrase: str, *,
                 header: BackupHeader) -> Path:
    """Wrap a plain SQLite file into an authenticated ``.zbak`` container."""
    if not available():
        raise BackupCryptoError("No encryption backend available in this build.")
    if not passphrase:
        raise BackupCryptoError("A backup passphrase is required.")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    plaintext = Path(source).read_bytes()
    salt = os.urandom(SALT_BYTES)
    nonce = os.urandom(NONCE_BYTES)
    # The salt travels inside the authenticated header, so it cannot be swapped
    # for one an attacker precomputed against.
    header_bytes = json.dumps(
        {**header.to_json(), "salt": salt.hex()},
        sort_keys=True, separators=(",", ":")).encode("utf-8")

    key = _derive(passphrase, salt)
    body = AESGCM(key).encrypt(nonce, plaintext, header_bytes)

    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = target.with_name(target.name + ".writing")
    with open(staged, "wb") as handle:
        handle.write(MAGIC)
        handle.write(struct.pack(">I", len(header_bytes)))
        handle.write(header_bytes)
        handle.write(nonce)
        handle.write(body)
    os.replace(staged, target)
    return target


def read_header(path: str | Path) -> BackupHeader | None:
    """The header of a ``.zbak``, without the passphrase. None if unreadable."""
    try:
        with open(path, "rb") as handle:
            if handle.read(len(MAGIC)) != MAGIC:
                return None
            (length,) = struct.unpack(">I", handle.read(4))
            if length <= 0 or length > 1_000_000:
                return None
            return BackupHeader.from_json(json.loads(handle.read(length)))
    except (OSError, ValueError, struct.error, json.JSONDecodeError):
        return None


def decrypt_file(source: str | Path, target: str | Path, passphrase: str) -> Path:
    """Unwrap a ``.zbak`` to a plain SQLite file.

    Raises :class:`WrongPassphrase` if the passphrase is wrong **or the file was
    altered** — GCM cannot tell those apart, and for the customer they mean the
    same thing: this file cannot be trusted.
    """
    if not available():
        raise BackupCryptoError("No encryption backend available in this build.")
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    try:
        raw = Path(source).read_bytes()
    except OSError as exc:
        raise BackupCryptoError(f"Cannot read {source}: {exc}") from exc

    if raw[:len(MAGIC)] != MAGIC:
        raise BackupCryptoError("Not an encrypted Zenith backup.")
    cursor = len(MAGIC)
    try:
        (length,) = struct.unpack(">I", raw[cursor:cursor + 4])
    except struct.error as exc:
        raise BackupCryptoError("Backup header is truncated.") from exc
    cursor += 4
    header_bytes = raw[cursor:cursor + length]
    if len(header_bytes) != length:
        raise BackupCryptoError("Backup header is truncated.")
    cursor += length
    nonce = raw[cursor:cursor + NONCE_BYTES]
    if len(nonce) != NONCE_BYTES:
        raise BackupCryptoError("Backup is truncated.")
    cursor += NONCE_BYTES
    body = raw[cursor:]
    if len(body) <= TAG_BYTES:
        raise BackupCryptoError("Backup is truncated.")

    try:
        salt = bytes.fromhex(json.loads(header_bytes).get("salt", ""))
    except (ValueError, json.JSONDecodeError) as exc:
        raise BackupCryptoError("Backup header is not readable.") from exc
    if len(salt) != SALT_BYTES:
        raise BackupCryptoError("Backup header is not readable.")

    key = _derive(passphrase or "", salt)
    try:
        plaintext = AESGCM(key).decrypt(nonce, body, header_bytes)
    except InvalidTag as exc:
        raise WrongPassphrase(
            "The backup did not authenticate: wrong passphrase, or the file "
            "has been altered.") from exc

    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    staged = target.with_name(target.name + ".opening")
    staged.write_bytes(plaintext)
    os.replace(staged, target)
    return target
