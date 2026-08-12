"""Zenith Business — offline business management and accounting system.

Developed under the Zenith Soft brand.

This top-level package intentionally contains no business logic. It exposes the
application identity and version so other layers can import a single source of
truth (see :mod:`zenith_business.core.identity`).
"""

from __future__ import annotations

from zenith_business.core.identity import APP_VERSION

__all__ = ["APP_VERSION"]
__version__ = APP_VERSION
