"""Ed25519 signing for TESTS ONLY — the vendor side, simulated.

This is what the future vendor License Manager will do; it exists here so the
customer-side verification can be proven against real signatures instead of
being taken on trust.

**This file must never be imported by the application.** It is under ``tests/``
and the PyInstaller spec collects only the ``zenith_business`` package, so it
cannot reach a build. Keys made here are generated per test run, held in memory,
and never written to the repository.
"""

from __future__ import annotations

import base64
from datetime import date

from zenith_business.security.license_format import (
    LICENSE_FORMAT,
    PRODUCT_ID,
    TYPE_FULL,
    canonical_bytes,
)


def generate_keypair() -> tuple[bytes, bytes]:
    """A throwaway (private, public) Ed25519 pair for one test run."""
    from cryptography.hazmat.primitives import serialization as ser
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    private = Ed25519PrivateKey.generate()
    private_raw = private.private_bytes(
        ser.Encoding.Raw, ser.PrivateFormat.Raw, ser.NoEncryption())
    public_raw = private.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)
    return private_raw, public_raw


def sign(private_key: bytes, message: bytes) -> bytes:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    return Ed25519PrivateKey.from_private_bytes(private_key).sign(message)


def make_license(private_key: bytes, *, machine_fingerprint: str,
                 machine_traits: dict[str, str], license_id: str = "ZB-TEST-000001",
                 license_type: str = TYPE_FULL, product_id: str = PRODUCT_ID,
                 issued_to: str = "Acceptance Test", issued_at: str | None = None,
                 expires_at: str | None = None, extra: dict | None = None) -> str:
    """Build a signed ``.zlic`` document, exactly as the vendor tool will."""
    payload = {
        "product_id": product_id,
        "license_id": license_id,
        "license_type": license_type,
        "issued_to": issued_to,
        "issued_at": issued_at or date.today().isoformat(),
        "machine": {"fingerprint": machine_fingerprint,
                    "traits": dict(machine_traits)},
    }
    if expires_at is not None:
        payload["expires_at"] = expires_at
    if extra:
        payload.update(extra)
    signature = sign(private_key, canonical_bytes(payload))
    import json
    return json.dumps({
        "format": LICENSE_FORMAT,
        "payload": payload,
        "signature": base64.b64encode(signature).decode("ascii"),
    }, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def tamper(license_text: str, field: str, value) -> str:
    """Change one signed field WITHOUT re-signing — the attack the tests must catch."""
    import json
    document = json.loads(license_text)
    target = document["payload"]
    if "." in field:
        head, tail = field.split(".", 1)
        target = target[head]
        field = tail
    target[field] = value
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
