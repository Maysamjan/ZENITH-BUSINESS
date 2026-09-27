"""License and activation-request file formats (Stage 10 §7, §9).

Two files cross the boundary between the customer's PC and the vendor:

``.zreq`` — **activation request**, produced here. It carries this machine's
hashed traits and the product it is for. It is not secret and is not signed:
the customer has nothing to sign with, which is the whole point.

``.zlic`` — **signed license**, produced by the vendor and imported here. It is
a payload plus an Ed25519 signature over that payload::

    {"format": "zenith-license-1",
     "payload": {...},
     "signature": "<base64>"}

The signature covers :func:`canonical_bytes` of the payload — JSON with sorted
keys, no insignificant whitespace, UTF-8. Canonicalisation is what makes "any
modification invalidates the signature" true rather than hopeful: two payloads
that differ in any value, any key, or any nesting produce different bytes, and
re-ordering keys or re-indenting produces the *same* bytes, so a licence cannot
be invalidated by a harmless reformat either.

This module contains **no keys** and cannot sign. It parses, canonicalises and
describes; verification lives in the license service and signing exists only in
test tooling.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

#: Product this build is licensed for. A licence for anything else is rejected.
PRODUCT_ID = "ZENITH-BUSINESS"

LICENSE_FORMAT = "zenith-license-1"
REQUEST_FORMAT = "zenith-activation-request-1"

LICENSE_SUFFIX = ".zlic"
REQUEST_SUFFIX = ".zreq"

#: The licence types this application understands.
TYPE_DEMO = "DEMO"
TYPE_FULL = "FULL"
LICENSE_TYPES = (TYPE_DEMO, TYPE_FULL)

#: Payload fields that must be present and signed (§9). A licence missing any of
#: them is malformed, not merely unusual.
REQUIRED_PAYLOAD_FIELDS = (
    "product_id", "license_id", "license_type", "machine", "issued_at",
)


class LicenseFormatError(ValueError):
    """The file is not a well-formed license or activation request."""


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    """The exact bytes a signature is computed over.

    Sorted keys and compact separators, so the mapping from payload to bytes is
    one-to-one regardless of how the file was written.
    """
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def b64decode(text: str) -> bytes:
    """Strict base64 decode; raises :class:`LicenseFormatError` on anything else."""
    try:
        return base64.b64decode(text.encode("ascii"), validate=True)
    except Exception as exc:                       # binascii.Error, UnicodeError
        raise LicenseFormatError("Signature is not valid base64.") from exc


@dataclass(frozen=True)
class LicenseFile:
    """A parsed ``.zlic``: the payload as signed, plus the signature bytes."""

    payload: dict[str, Any]
    signature: bytes

    @property
    def signed_bytes(self) -> bytes:
        return canonical_bytes(self.payload)

    # -- the signed fields, read back with safe defaults -------------------
    @property
    def product_id(self) -> str:
        return str(self.payload.get("product_id", ""))

    @property
    def license_id(self) -> str:
        return str(self.payload.get("license_id", ""))

    @property
    def license_type(self) -> str:
        return str(self.payload.get("license_type", "")).upper()

    @property
    def issued_at(self) -> str:
        return str(self.payload.get("issued_at", ""))

    @property
    def issued_to(self) -> str:
        return str(self.payload.get("issued_to", "") or "")

    @property
    def expires_at(self) -> str | None:
        value = self.payload.get("expires_at")
        return str(value) if value else None

    @property
    def machine_fingerprint(self) -> str:
        machine = self.payload.get("machine") or {}
        return str(machine.get("fingerprint", "")) if isinstance(machine, dict) else ""

    @property
    def machine_traits(self) -> dict[str, str]:
        machine = self.payload.get("machine") or {}
        traits = machine.get("traits") if isinstance(machine, dict) else None
        if not isinstance(traits, dict):
            return {}
        return {str(k): str(v) for k, v in traits.items()}


def parse_license(text: str | bytes) -> LicenseFile:
    """Parse a ``.zlic``. Raises :class:`LicenseFormatError` — never returns junk."""
    if isinstance(text, (bytes, bytearray)):
        try:
            text = bytes(text).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LicenseFormatError("License file is not UTF-8 text.") from exc
    try:
        document = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise LicenseFormatError("License file is not valid JSON.") from exc
    if not isinstance(document, dict):
        raise LicenseFormatError("License file is not a JSON object.")
    if document.get("format") != LICENSE_FORMAT:
        raise LicenseFormatError(
            f"Unsupported license format: {document.get('format')!r}.")

    payload = document.get("payload")
    if not isinstance(payload, dict):
        raise LicenseFormatError("License file has no payload object.")
    missing = [f for f in REQUIRED_PAYLOAD_FIELDS if f not in payload]
    if missing:
        raise LicenseFormatError(f"License payload is missing {', '.join(missing)}.")

    signature_text = document.get("signature")
    if not isinstance(signature_text, str) or not signature_text:
        raise LicenseFormatError("License file has no signature.")
    return LicenseFile(payload=payload, signature=b64decode(signature_text))


def build_request(*, machine_fingerprint: str, machine_traits: dict[str, str],
                  app_version: str, requested_at: str, request_id: str,
                  business_name: str | None = None) -> str:
    """Serialise an activation request (``.zreq``) for the vendor."""
    document = {
        "format": REQUEST_FORMAT,
        "product_id": PRODUCT_ID,
        "app_version": app_version,
        "requested_at": requested_at,
        "request_id": request_id,
        "business_name": business_name or "",
        "machine": {"fingerprint": machine_fingerprint,
                    "traits": dict(machine_traits)},
    }
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def parse_request(text: str | bytes) -> dict[str, Any]:
    """Parse a ``.zreq`` — used by tests and by the future vendor tool."""
    if isinstance(text, (bytes, bytearray)):
        text = bytes(text).decode("utf-8")
    document = json.loads(text)
    if not isinstance(document, dict) or document.get("format") != REQUEST_FORMAT:
        raise LicenseFormatError("Not a Zenith activation request.")
    return document
