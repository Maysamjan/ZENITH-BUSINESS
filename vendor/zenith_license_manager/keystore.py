"""The vendor's signing keys, encrypted at rest (Vendor Manager §5).

    THIS PACKAGE IS FOR ZENITH SOFT ONLY. It is never installed on a customer
    machine, never collected by the Zenith Business build, and never carries a
    key into one. The customer application holds a public verification key and
    nothing else.

A private Ed25519 key is the whole product: anyone holding it can issue licences
for every customer, past and future. So it is never stored as a bare file the
way the first command-line tool wrote it.

How it is protected
-------------------
The key lives **outside the repository**, under the vendor's own application
data directory, in a file encrypted with a passphrase only the vendor knows::

    magic        8 bytes   b"ZKEY1\\x00\\x00\\x00"[:8]
    header_len   4 bytes   big-endian
    header       JSON, UTF-8, readable but AUTHENTICATED
    nonce       12 bytes
    body                   AES-256-GCM(seed) + tag

**scrypt** (n=2^17, r=8, p=1) derives the key from the passphrase — four times
the work factor the backup format uses, because a backup protects one customer's
data for one customer, while this protects every licence Zenith Soft will ever
issue. The header carries the product, the public key and when the key was made;
it is readable so the Manager can list keys and show which product each belongs
to without unlocking anything, and it is fed to GCM as additional data so it
cannot be edited either.

**The passphrase is not stored.** That is the point, and it is also the risk: a
forgotten passphrase means a signing key nobody can open, and every licence must
then be reissued under a new key with a rebuilt application. The Manager says so
plainly rather than keeping a copy that would undo the protection.

**The raw seed never leaves this module** except to the signing call, and never
reaches the interface, a log line, the history file or an error message.
"""

from __future__ import annotations

import json
import os
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

MAGIC = b"ZKEY1\x00\x00\x00"
SALT_BYTES = 16
NONCE_BYTES = 12
KEY_BYTES = 32
SEED_BYTES = 32

#: Deliberately heavier than the backup container's 2**15. A backup guards one
#: customer's books; this guards the ability to issue licences at all.
SCRYPT_N = 2 ** 17
SCRYPT_R = 8
SCRYPT_P = 1


class KeystoreError(Exception):
    """The key file could not be produced or opened."""


class WrongPassphrase(KeystoreError):
    """Authentication failed: wrong passphrase, or the file was altered."""


def default_key_dir() -> Path:
    """Where vendor keys live — beside the vendor's own data, never in the repo.

    Keeping this out of any checkout is the single most effective protection
    against the accident that matters: a signing key committed to git.
    """
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "ZenithSoft" / "LicenseManager" / "keys"


@dataclass(frozen=True)
class KeyInfo:
    """What a key file says about itself without being unlocked."""

    product_id: str
    public_key_b64: str
    created_at: str
    label: str
    path: Path

    @property
    def name(self) -> str:
        return self.path.stem


def available() -> bool:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
        from cryptography.hazmat.primitives.kdf.scrypt import Scrypt    # noqa: F401
    except Exception:
        return False
    return True


def _derive(passphrase: str, salt: bytes) -> bytes:
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    kdf = Scrypt(salt=salt, length=KEY_BYTES, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return kdf.derive(passphrase.encode("utf-8"))


def generate_seed() -> tuple[bytes, bytes]:
    """A fresh Ed25519 keypair as (private seed, public key)."""
    from cryptography.hazmat.primitives import serialization as ser
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private = Ed25519PrivateKey.generate()
    seed = private.private_bytes(ser.Encoding.Raw, ser.PrivateFormat.Raw,
                                 ser.NoEncryption())
    public = private.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)
    return seed, public


def public_key_for(seed: bytes) -> bytes:
    from cryptography.hazmat.primitives import serialization as ser
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private = Ed25519PrivateKey.from_private_bytes(seed)
    return private.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)


def sign(seed: bytes, message: bytes) -> bytes:
    """Sign with the vendor key. The ONLY place the raw seed is used."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    return Ed25519PrivateKey.from_private_bytes(seed).sign(message)


# ---------------------------------------------------------------------------
# the encrypted file
# ---------------------------------------------------------------------------


def write_key(path: Path | str, seed: bytes, passphrase: str, *,
              product_id: str, label: str = "") -> KeyInfo:
    """Encrypt a signing key to disk. Refuses to overwrite silently."""
    import base64

    if not available():
        raise KeystoreError("No encryption backend available.")
    if not passphrase:
        raise KeystoreError("A passphrase is required to protect a signing key.")
    if len(seed) != SEED_BYTES:
        raise KeystoreError("An Ed25519 private key is 32 bytes.")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    path = Path(path)
    if path.exists():
        # Overwriting a signing key destroys every licence issued under it.
        raise KeystoreError(f"{path.name} already exists. Choose another name.")

    public = public_key_for(seed)
    salt = os.urandom(SALT_BYTES)
    nonce = os.urandom(NONCE_BYTES)
    header = {
        "v": 1, "kind": "zenith-vendor-signing-key", "product_id": product_id,
        "label": label,
        "public_key": base64.b64encode(public).decode("ascii"),
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kdf": "scrypt", "n": SCRYPT_N, "r": SCRYPT_R, "p": SCRYPT_P,
        "cipher": "AES-256-GCM", "salt": salt.hex(),
    }
    header_bytes = json.dumps(header, sort_keys=True,
                              separators=(",", ":")).encode("utf-8")
    body = AESGCM(_derive(passphrase, salt)).encrypt(nonce, seed, header_bytes)

    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_name(path.name + ".writing")
    with open(staged, "wb") as handle:
        handle.write(MAGIC)
        handle.write(struct.pack(">I", len(header_bytes)))
        handle.write(header_bytes)
        handle.write(nonce)
        handle.write(body)
    os.replace(staged, path)
    try:
        os.chmod(path, 0o600)          # no effect on Windows; harmless there
    except OSError:
        pass
    return read_info(path)


def read_info(path: Path | str) -> KeyInfo:
    """Describe a key file WITHOUT the passphrase. Never returns key material."""
    path = Path(path)
    try:
        with open(path, "rb") as handle:
            if handle.read(len(MAGIC)) != MAGIC:
                raise KeystoreError(f"{path.name} is not a Zenith signing key.")
            (length,) = struct.unpack(">I", handle.read(4))
            if length <= 0 or length > 1_000_000:
                raise KeystoreError(f"{path.name} is damaged.")
            header = json.loads(handle.read(length))
    except (OSError, ValueError, struct.error, json.JSONDecodeError) as exc:
        raise KeystoreError(f"{path.name} could not be read: {exc}") from exc
    return KeyInfo(product_id=str(header.get("product_id", "")),
                   public_key_b64=str(header.get("public_key", "")),
                   created_at=str(header.get("created_at", "")),
                   label=str(header.get("label", "")), path=path)


def load_seed(path: Path | str, passphrase: str) -> bytes:
    """Unlock a signing key. Raises rather than returning anything on failure."""
    if not available():
        raise KeystoreError("No encryption backend available.")
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    path = Path(path)
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise KeystoreError(f"Cannot read {path}: {exc}") from exc

    if raw[:len(MAGIC)] != MAGIC:
        raise KeystoreError(f"{path.name} is not a Zenith signing key.")
    cursor = len(MAGIC)
    try:
        (length,) = struct.unpack(">I", raw[cursor:cursor + 4])
    except struct.error as exc:
        raise KeystoreError(f"{path.name} is damaged.") from exc
    cursor += 4
    header_bytes = raw[cursor:cursor + length]
    if len(header_bytes) != length:
        raise KeystoreError(f"{path.name} is damaged.")
    cursor += length
    nonce = raw[cursor:cursor + NONCE_BYTES]
    cursor += NONCE_BYTES
    body = raw[cursor:]
    if len(nonce) != NONCE_BYTES or len(body) <= 16:
        raise KeystoreError(f"{path.name} is truncated.")
    try:
        salt = bytes.fromhex(json.loads(header_bytes).get("salt", ""))
    except (ValueError, json.JSONDecodeError) as exc:
        raise KeystoreError(f"{path.name} is damaged.") from exc
    if len(salt) != SALT_BYTES:
        raise KeystoreError(f"{path.name} is damaged.")

    try:
        seed = AESGCM(_derive(passphrase or "", salt)).decrypt(nonce, body, header_bytes)
    except InvalidTag as exc:
        raise WrongPassphrase(
            "Wrong passphrase, or the key file has been altered.") from exc
    if len(seed) != SEED_BYTES:
        raise KeystoreError(f"{path.name} does not contain an Ed25519 key.")
    return seed


def list_keys(directory: Path | str | None = None) -> list[KeyInfo]:
    """Every key file in the vendor key directory, described but not unlocked."""
    folder = Path(directory) if directory is not None else default_key_dir()
    if not folder.is_dir():
        return []
    found = []
    for path in sorted(folder.glob("*.zkey")):
        try:
            found.append(read_info(path))
        except KeystoreError:
            continue
    return found
