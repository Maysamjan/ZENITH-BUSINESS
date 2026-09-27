# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Zenith Soft License Manager — the VENDOR tool.

    THIS BUILD IS FOR ZENITH SOFT ONLY. It issues licences, so it is the one
    program that must never reach a customer. It is published as a separate
    download from the Zenith Business package and is never placed inside it.

Produces dist/ZenithLicenseManager/ZenithLicenseManager.exe.

What it deliberately bundles
----------------------------
``zenith_business.security.product_key`` and its siblings, because the Manager
packs a licence with the **same** codec the customer application unpacks it
with. Two independent packers would drift on the first field anybody added, and
the failure would look like a customer's key being rejected for no reason.

What it deliberately does NOT bundle
------------------------------------
Any signing key. Keys are created by this program at run time, encrypted with
the vendor's passphrase, and stored under the vendor's own application data —
never in the repository, never in a build. A key inside this executable would
be a key inside anything the executable was ever copied to.

Invoke from the repository root:
    pyinstaller packaging/zenith_license_manager.spec --noconfirm
"""

import os

from PyInstaller.utils.hooks import collect_submodules

_SPEC_DIR = SPECPATH
_ROOT = os.path.dirname(_SPEC_DIR)

# The vendor package, plus the customer-side codec it shares.
hiddenimports = collect_submodules("vendor")
hiddenimports += [
    "zenith_business.security.product_key",
    "zenith_business.security.license_format",
    "zenith_business.security.machine_id",
    # Signing and key encryption import the backend inside function bodies, so
    # static analysis cannot see them. A Manager that cannot sign is useless,
    # so they are named rather than left to discovery.
    "cryptography",
    "cryptography.hazmat.primitives.asymmetric.ed25519",
    "cryptography.hazmat.primitives.ciphers.aead",
    "cryptography.hazmat.primitives.kdf.scrypt",
    "cryptography.hazmat.primitives.serialization",
]

analysis = Analysis(
    [os.path.join(_ROOT, "packaging", "license_manager_entry.py")],
    pathex=[_ROOT],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # The customer application is a separate product and has no business being
    # inside the vendor tool.
    excludes=["zenith_business.ui", "zenith_business.services",
              "zenith_business.database", "zenith_business.repositories"],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="ZenithLicenseManager",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ZenithLicenseManager",
)
