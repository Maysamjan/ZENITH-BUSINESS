# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Zenith Business Windows test build.

Produces a one-directory application bundle (dist/ZenithBusiness/):
    ZenithBusiness.exe  +  _internal/   (Qt runtime, Python, app code, resources)

Notes
-----
* Bundles the whole ``zenith_business/resources`` tree at the SAME package-
  relative path the app resolves at runtime (core/fonts.py builds the font
  directory from ``__file__``), so Vazirmatn loads inside the frozen build and
  Dari renders identically to development.
* ``collect_submodules`` pulls in every zenith_business submodule (including the
  per-stage migration modules) so nothing is missed by static analysis.
* Windowed build (no console window) for a clean owner experience. Runtime logs
  are still written under the app data directory (see READ-ME-FIRST).

Invoke from the repository root:
    pyinstaller packaging/zenith_business.spec --noconfirm
"""

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Resolve paths from the spec's own location so the build works regardless of the
# current working directory. SPECPATH is the directory containing this spec.
_SPEC_DIR = SPECPATH
_ROOT = os.path.dirname(_SPEC_DIR)  # repository root (packaging/..)

hiddenimports = collect_submodules("zenith_business")

# Only the RESOURCE files (Vazirmatn fonts, logo, licence) are collected as data,
# placed at their package-relative path so core/fonts.py (which resolves the font
# directory from ``__file__``) finds them inside the frozen build. The Python code
# itself is analysed normally and embedded in the archive, so all stdlib/PyQt6
# dependencies are discovered.
datas = collect_data_files("zenith_business")

block_cipher = None

a = Analysis(
    [os.path.join(_SPEC_DIR, "run_zenith.py")],
    # Put the repository root on the analysis path so the source package is
    # importable during PyInstaller's isolated module analysis (it is not
    # installed into site-packages; an editable/CWD install is not visible to
    # the analysis subprocess without this).
    pathex=[_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "pytest_qt", "tkinter", "_tkinter"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ZenithBusiness",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ZenithBusiness",
)
