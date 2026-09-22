"""Frozen-application entry point for the Windows test build.

PyInstaller freezes this thin wrapper. It simply calls the same
``zenith_business.app:main`` used by ``python -m zenith_business`` and the
console script, so the packaged executable follows the exact production
startup path (no behaviour change).
"""

from __future__ import annotations

from zenith_business.app import main

if __name__ == "__main__":
    main()
