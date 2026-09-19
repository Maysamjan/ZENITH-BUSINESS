#!/usr/bin/env python3
"""Scan a built Windows package for anything that must not ship (Stage 10 §7).

This inspects the **actual package directory** — every file that would reach a
customer, including the bytes inside the frozen executable and the PyInstaller
archive — rather than the source tree. A source-level check would miss exactly
the failure that matters: a file that was never meant to be collected but was.

    python packaging/audit_release_package.py dist/package

Exits non-zero, and names the file, if it finds any of:

* a private key of any kind (PEM blocks, our signing-key file shape, Ed25519
  private-key constructors);
* the vendor signing tool, or the test signing tooling;
* a licence-generation capability;
* a debug or licence-bypass switch;
* a default password, hard-coded secret or backdoor account.

It also confirms the things that MUST be there: the public-key module, and a
verification path.
"""

from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

# Patterns that must never appear in a shipped file. (label, regex, why)
FORBIDDEN: list[tuple[str, re.Pattern[bytes], str]] = [
    ("PEM private key", re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
     "a private key would let anyone issue licences"),
    ("signing key file", re.compile(rb'"kind"\s*:\s*"zenith-signing-key"'),
     "the vendor signing key must never be packaged"),
    ("Ed25519 private key use", re.compile(rb"Ed25519PrivateKey"),
     "the customer build must not be able to sign"),
    ("private_bytes", re.compile(rb"private_bytes"),
     "serialising a private key implies holding one"),
    ("vendor tool", re.compile(rb"zenith_license_tool"),
     "the vendor licensing tool must not ship"),
    ("test signing tooling", re.compile(rb"tests[./\\]tooling"),
     "test signing tooling must not ship"),
    ("licence generator", re.compile(rb"def\s+make_license\b"),
     "no licence-generation capability may ship"),
    ("licence bypass", re.compile(rb"ZENITH_SKIP_LICEN[CS]E|LICENSE_BYPASS|skip_license"),
     "a bypass switch would defeat licensing entirely"),
    ("debug backdoor", re.compile(rb"BACKDOOR|backdoor|MASTER_PASSWORD|master_password"),
     "no backdoor may exist"),
    ("default password", re.compile(rb'password\s*=\s*["\'](?!\s*["\'])[^"\']{3,}["\']'),
     "a hard-coded default password would be a shared secret"),
]

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
    scanned = 0
    saw_public_key_module = False
    saw_verification = False

    for label, data in _iter_payloads(root):
        scanned += 1
        if b"EMBEDDED_PUBLIC_KEY_B64" in data:
            saw_public_key_module = True
        if b"Ed25519PublicKey" in data or b"signatures" in data:
            saw_verification = True
        for name, pattern, why in FORBIDDEN:
            match = pattern.search(data)
            if match:
                excerpt = match.group(0)[:60].decode("utf-8", "replace")
                findings.append(f"{name}: {label}  ({why})\n      matched: {excerpt!r}")

    print(f"Scanned {scanned} payload(s) under {root}")
    print()
    if findings:
        print("FAIL — the package contains things that must not ship:")
        for finding in findings:
            print("  *", finding)
        return 1

    print("PASS — no private key, no signing tool, no generator, no bypass,")
    print("       no backdoor and no default password found in the package.")
    print()
    print(f"  public-key module present : {saw_public_key_module}")
    print(f"  verification path present : {saw_verification}")
    if not (saw_public_key_module and saw_verification):
        print()
        print("FAIL — the package is missing the licence verification path.")
        return 1
    return 0


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/package")
    raise SystemExit(audit(target))
