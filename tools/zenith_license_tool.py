#!/usr/bin/env python3
"""Zenith Soft VENDOR tool — generate a signing key, and sign licence files.

    THIS FILE IS FOR THE VENDOR ONLY. IT IS NOT PART OF ZENITH BUSINESS.
    It is never installed, never packaged, and must never be given to a
    customer. The PyInstaller build collects the ``zenith_business`` package
    only, so nothing here can reach a customer build.

It needs nothing but a standard Python 3.11+ install: no pip, no internet, no
extra packages. Ed25519 is implemented here from RFC 8032 so the tool can run
on an offline machine you control.

    KEEP THE PRIVATE KEY FILE. Anyone who has it can issue licences for your
    product. Back it up somewhere safe and offline. If it is lost, every future
    licence must be re-issued under a new key and the application rebuilt.

Usage
-----
Create your signing key (once, ever)::

    python zenith_license_tool.py generate --out zenith-signing-key.json

It prints a PUBLIC KEY line. Send ONLY that line to your developer; it goes into
the application. Keep the .json file private.

Issue a licence from a customer's activation request::

    python zenith_license_tool.py sign --key zenith-signing-key.json \\
        --request zenith-activation-XXXX.zreq --out customer.zlic \\
        --license-id ZB-FULL-000001 --issued-to "Kabul Traders Ltd"

Send the .zlic back to the customer to import. Add ``--type DEMO`` and
``--expires 2027-01-31`` for a time-limited demo licence.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import sys
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Ed25519 (RFC 8032) — signing side. Standard library only.
# ---------------------------------------------------------------------------

_P = 2 ** 255 - 19
_L = 2 ** 252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_SQRT_M1 = pow(2, (_P - 1) // 4, _P)
_BY = 4 * pow(5, _P - 2, _P) % _P
_BX = 15112221349535400772501151409588531511454012693041857206046113283949847762202
_BASE = (_BX, _BY, 1, _BX * _BY % _P)


def _add(p, q):
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = (y1 - x1) * (y2 - x2) % _P
    b = (y1 + x1) * (y2 + x2) % _P
    c = 2 * t1 * t2 * _D % _P
    dd = 2 * z1 * z2 % _P
    e, f, g, h = b - a, dd - c, dd + c, b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _mult(point, scalar):
    result = (0, 1, 1, 0)
    addend = point
    while scalar > 0:
        if scalar & 1:
            result = _add(result, addend)
        addend = _add(addend, addend)
        scalar >>= 1
    return result


def _encode(point) -> bytes:
    x, y, z, _ = point
    inv = pow(z, _P - 2, _P)
    x, y = x * inv % _P, y * inv % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _clamp(seed_hash: bytes) -> int:
    a = bytearray(seed_hash[:32])
    a[0] &= 248
    a[31] &= 127
    a[31] |= 64
    return int.from_bytes(a, "little")


def public_key_from_seed(seed: bytes) -> bytes:
    return _encode(_mult(_BASE, _clamp(hashlib.sha512(seed).digest())))


def sign(seed: bytes, message: bytes) -> bytes:
    digest = hashlib.sha512(seed).digest()
    a = _clamp(digest)
    prefix = digest[32:]
    public = _encode(_mult(_BASE, a))
    r = int.from_bytes(hashlib.sha512(prefix + message).digest(), "little") % _L
    big_r = _encode(_mult(_BASE, r))
    k = int.from_bytes(hashlib.sha512(big_r + public + message).digest(), "little") % _L
    s = (r + k * a) % _L
    return big_r + int.to_bytes(s, 32, "little")


# ---------------------------------------------------------------------------
# licence format — must match zenith_business/security/license_format.py
# ---------------------------------------------------------------------------

PRODUCT_ID = "ZENITH-BUSINESS"
LICENSE_FORMAT = "zenith-license-1"
REQUEST_FORMAT = "zenith-activation-request-1"


def canonical_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def cmd_generate(args) -> int:
    seed = secrets.token_bytes(32)
    public = public_key_from_seed(seed)
    out = Path(args.out)
    if out.exists() and not args.force:
        print(f"ERROR: {out} already exists. Refusing to overwrite a signing key.\n"
              f"       Use --force only if you are certain it is not in use.",
              file=sys.stderr)
        return 2
    out.write_text(json.dumps({
        "kind": "zenith-signing-key",
        "product_id": PRODUCT_ID,
        "created_at": date.today().isoformat(),
        "private_key": base64.b64encode(seed).decode("ascii"),
        "public_key": base64.b64encode(public).decode("ascii"),
    }, indent=2) + "\n", encoding="utf-8")
    try:
        out.chmod(0o600)
    except OSError:
        pass
    print("Signing key written to:", out.resolve())
    print()
    print("  KEEP THIS FILE PRIVATE AND BACKED UP.")
    print("  Anyone who has it can issue licences for your product.")
    print()
    print("Send ONLY the line below to your developer:")
    print()
    print("PUBLIC KEY:", base64.b64encode(public).decode("ascii"))
    print()
    return 0


def _load_key(path: Path) -> bytes:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("kind") != "zenith-signing-key":
        raise SystemExit(f"{path} is not a Zenith signing key file.")
    return base64.b64decode(data["private_key"])


def cmd_sign(args) -> int:
    seed = _load_key(Path(args.key))
    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    if request.get("format") != REQUEST_FORMAT:
        raise SystemExit(f"{args.request} is not a Zenith activation request.")
    if request.get("product_id") != PRODUCT_ID:
        raise SystemExit(f"Request is for {request.get('product_id')!r}, not {PRODUCT_ID}.")

    machine = request.get("machine") or {}
    if not machine.get("fingerprint"):
        raise SystemExit("Request carries no machine fingerprint.")

    payload = {
        "product_id": PRODUCT_ID,
        "license_id": args.license_id,
        "license_type": args.type.upper(),
        "issued_to": args.issued_to or request.get("business_name", ""),
        "issued_at": args.issued_at or date.today().isoformat(),
        "machine": {"fingerprint": machine["fingerprint"],
                    "traits": machine.get("traits") or {}},
    }
    if args.expires:
        payload["expires_at"] = args.expires

    signature = sign(seed, canonical_bytes(payload))
    document = {"format": LICENSE_FORMAT, "payload": payload,
                "signature": base64.b64encode(signature).decode("ascii")}
    out = Path(args.out)
    out.write_text(json.dumps(document, indent=2, sort_keys=True,
                              ensure_ascii=False) + "\n", encoding="utf-8")
    print("Licence written to:", out.resolve())
    print(f"  id        : {payload['license_id']}")
    print(f"  type      : {payload['license_type']}")
    print(f"  issued to : {payload['issued_to'] or '(not set)'}")
    print(f"  machine   : {payload['machine']['fingerprint'][:16]}…")
    print(f"  expires   : {payload.get('expires_at', 'never')}")
    print()
    print("Send this .zlic file to the customer to import.")
    return 0


def cmd_show(args) -> int:
    """Print what a request or licence contains, without changing anything."""
    document = json.loads(Path(args.file).read_text(encoding="utf-8"))
    print(json.dumps(document, indent=2, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Zenith Soft vendor licensing tool (NOT for customers).")
    sub = parser.add_subparsers(dest="command", required=True)

    g = sub.add_parser("generate", help="create your Ed25519 signing key (once)")
    g.add_argument("--out", default="zenith-signing-key.json")
    g.add_argument("--force", action="store_true",
                   help="overwrite an existing key file (dangerous)")
    g.set_defaults(func=cmd_generate)

    s = sub.add_parser("sign", help="sign a licence from an activation request")
    s.add_argument("--key", required=True, help="your signing key .json")
    s.add_argument("--request", required=True, help="the customer's .zreq")
    s.add_argument("--out", required=True, help="licence file to write (.zlic)")
    s.add_argument("--license-id", required=True, help="e.g. ZB-FULL-000001")
    s.add_argument("--issued-to", default="", help="customer business name")
    s.add_argument("--type", default="FULL", choices=["FULL", "DEMO"])
    s.add_argument("--issued-at", default="", help="YYYY-MM-DD (default: today)")
    s.add_argument("--expires", default="", help="YYYY-MM-DD (omit for no expiry)")
    s.set_defaults(func=cmd_sign)

    v = sub.add_parser("show", help="print a .zreq or .zlic file")
    v.add_argument("file")
    v.set_defaults(func=cmd_show)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
