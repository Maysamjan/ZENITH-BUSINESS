"""Frozen entry point for the Zenith Soft License Manager (vendor only).

A file of its own because PyInstaller needs a script rather than a package, and
because the import path has to be set up before the vendor package is reachable
when running from a frozen bundle.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from vendor.zenith_license_manager.ui.main_window import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
