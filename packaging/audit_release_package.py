#!/usr/bin/env python3
"""Scan a built Windows package for anything that must not ship (Stage 10 §7).

This inspects the **actual package directory** — every file that would reach a
customer, including the bytes inside the frozen executable and the PyInstaller
archive — rather than the source tree. A source-level check would miss exactly
the failure that matters: a file that was never meant to be collected but was.

    python packaging/audit_release_package.py dist/package

Two different questions, deliberately kept apart:

**Is there key material or a tool that must not ship?** Asked of EVERY file: a
real PEM private key (header *and* a plausible base64 body), our signing-key
file shape, a packaged `.zlic`/`.zreq`, the vendor tool, the test signing
tooling, a licence generator, a bypass switch, a backdoor, a default password.
Any hit fails the build.

**Does OUR code contain signing capability?** That cannot honestly be asked of a
frozen package. We bundle `cryptography`, a general-purpose library that
contains `Ed25519PrivateKey` and `private_bytes` because it supports signing for
everyone who uses it, and PyInstaller embeds its Python modules inside the
executable — so those strings appear in the exe no matter what our code does.
Qt6Network.dll likewise contains the literal `-----BEGIN RSA PRIVATE KEY-----`
because it *parses* PEM, not because it holds a key.

Treating those as findings would be a false alarm that trains everyone to ignore
the report. So capability inside vendored third-party payloads is **reported as
information**, and the real guarantee — that no module under `zenith_business/`
references a private-key type — is enforced at source level by
`tests/test_stage10_licensing.py::test_no_module_in_the_application_package_can_sign`.

What this CANNOT do is prove the licence path is present and working. PyInstaller
zlib-compresses the Python archive, so our own module strings are not visible to
a byte scan — an absence here means nothing. That half is proved by running the
frozen executable with ``--selftest``, which is a separate CI step.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

# Hard failures — asked of every file in the package. (label, regex, why)
FORBIDDEN: list[tuple[str, re.Pattern[bytes], str]] = [
    # A real key, not merely the header literal that PEM parsers carry: the
    # header must be followed by base64 body characters.
    ("PEM private key",
     re.compile(rb"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\r\n]+[A-Za-z0-9+/=]{40}"),
     "a private key would let anyone issue licences"),
    ("signing key file", re.compile(rb'"kind"\s*:\s*"zenith-signing-key"'),
     "the vendor signing key must never be packaged"),
    ("packaged licence file", re.compile(rb'"format"\s*:\s*"zenith-license-1"'),
     "a licence must be imported by the customer, never shipped"),
    ("vendor tool", re.compile(rb"zenith_license_tool"),
     "the vendor licensing tool must not ship"),
    ("test signing tooling", re.compile(rb"tests[./\\]tooling|license_signing"),
     "test signing tooling must not ship"),
    ("licence generator", re.compile(rb"def\s+make_license\b"),
     "no licence-generation capability may ship"),
    ("licence bypass", re.compile(rb"ZENITH_SKIP_LICEN[CS]E|LICENSE_BYPASS|skip_license"),
     "a bypass switch would defeat licensing entirely"),
    ("debug backdoor", re.compile(rb"BACKDOOR|MASTER_PASSWORD|master_password"),
     "no backdoor may exist"),
    ("default password", re.compile(rb'(?:default|hardcoded|admin)_password\s*=\s*["\'][^"\']{3,}'),
     "a hard-coded default password would be a shared secret"),
]

#: Signing capability inside a vendored library is expected and is reported, not
#: failed. See the module docstring for why this cannot be a hard rule here.
CAPABILITY = [
    ("Ed25519PrivateKey", re.compile(rb"Ed25519PrivateKey")),
    ("private_bytes", re.compile(rb"private_bytes")),
]

#: Third-party payloads. Capability strings in these are informational.
VENDORED = ("cryptography", "PyQt6", "Qt6", "_rust", "openssl", "libcrypto",
            "libssl", "base_library.zip", "python3", "ZenithBusiness.exe")

#: Files whose own text legitimately contains a forbidden word (this script).
SELF = {"audit_release_package.py"}

#: Extensions worth scanning as text/bytes. Fonts and images are skipped.
SKIP_SUFFIXES = {".ttf", ".otf", ".woff", ".woff2", ".png", ".jpg", ".jpeg",
                 ".ico", ".gif", ".svg"}


def _iter_payloads(root: Path):
    """Yield (label, bytes) for every file, unpacking zip archives inside it."""
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name in SELF:
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        yield str(path.relative_to(root)), data

        # PyInstaller keeps the Python modules in an archive; look inside it.
        if zipfile.is_zipfile(path):
            try:
                with zipfile.ZipFile(path) as archive:
                    for name in archive.namelist():
                        try:
                            yield f"{path.relative_to(root)}!{name}", archive.read(name)
                        except (KeyError, RuntimeError, zipfile.BadZipFile):
                            continue
            except (zipfile.BadZipFile, OSError):
                pass


def audit(root: Path) -> int:
    if not root.is_dir():
        print(f"ERROR: {root} is not a directory", file=sys.stderr)
        return 2

    findings: list[str] = []
    capability: list[str] = []
    scanned = 0
    saw_public_key_module = False
    saw_verification = False

    for label, data in _iter_payloads(root):
        scanned += 1
        if b"EMBEDDED_PUBLIC_KEY_B64" in data:
            saw_public_key_module = True
        if b"Ed25519PublicKey" in data:
            saw_verification = True
        for name, pattern, why in FORBIDDEN:
            # The PATH is searched as well as the content: a file named
            # zenith_license_tool.py ships whether or not its text happens to
            # mention its own name.
            match = pattern.search(data) or pattern.search(label.encode("utf-8"))
            if match:
                excerpt = match.group(0)[:60].decode("utf-8", "replace")
                findings.append(f"{name}: {label}  ({why})\n      matched: {excerpt!r}")
        vendored = any(marker in label for marker in VENDORED)
        for name, pattern in CAPABILITY:
            if pattern.search(data):
                entry = f"{name} in {label}"
                if vendored:
                    if entry not in capability:
                        capability.append(entry)
                else:
                    findings.append(
                        f"signing capability: {label}  (our own files must not "
                        f"be able to sign)\n      matched: {name!r}")

    print(f"Scanned {scanned} payload(s) under {root}")
    print()
    if findings:
        print("FAIL — the package contains things that must not ship:")
        for finding in findings:
            print("  *", finding)
        return 1

    print("PASS — no private key, no licence file, no signing tool, no generator,")
    print("       no bypass, no backdoor and no default password in the package.")
    print()
    print(f"  crypto backend bundled    : {saw_verification}")
    if capability:
        print()
        print("  Signing capability inside VENDORED libraries (expected, not a finding):")
        for entry in capability:
            print("   -", entry)
        print("   These are general-purpose libraries that support signing for all")
        print("   their users. That OUR code never uses it is enforced at source")
        print("   level by test_no_module_in_the_application_package_can_sign.")
    if not saw_verification:
        print()
        print("FAIL — no Ed25519 verification backend was bundled.")
        return 1
    print()
    print("  (That the licence path WORKS is proved separately, by running the")
    print("   frozen executable with --selftest.)")
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/package")
    raise SystemExit(audit(target))
