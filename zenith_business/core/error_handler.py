"""Global exception handling (Prompt 01 §8).

Installs a process-wide ``sys.excepthook`` so unexpected exceptions are always
logged and never silently ignored. When a Qt application is running, a friendly,
non-technical dialog is shown; raw stack traces are not displayed to normal
users (they go to the log).

This module must not import UI at module import time — Qt is imported lazily,
inside the handler, so the core layer stays independent of the UI layer.
"""

from __future__ import annotations

import sys
import traceback
from types import TracebackType

from zenith_business.core.exceptions import ZenithError
from zenith_business.core.logging_setup import get_logger

_logger = get_logger("core.errors")

# Keep a reference to the previous hook so we can chain to it if needed.
_previous_hook = None


def _friendly_message(exc: BaseException) -> str:
    """Return a user-safe message for an exception."""
    if isinstance(exc, ZenithError):
        return exc.user_message
    return "An unexpected error occurred. The problem has been logged."


def handle_exception(
    exc_type: type[BaseException],
    exc_value: BaseException,
    exc_tb: TracebackType | None,
) -> None:
    """Log an unhandled exception and, if possible, notify the user gracefully."""
    # Never intercept Ctrl+C — let it behave normally.
    if issubclass(exc_type, KeyboardInterrupt):
        if _previous_hook:
            _previous_hook(exc_type, exc_value, exc_tb)
        return

    tb_text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _logger.critical("Unhandled exception:\n%s", tb_text)

    _try_show_dialog(_friendly_message(exc_value))


def _try_show_dialog(message: str) -> None:
    """Show a Qt error dialog if a QApplication is active; otherwise do nothing."""
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
    except Exception:  # pragma: no cover - PyQt6 not installed
        return

    app = QApplication.instance()
    if app is None:
        return

    try:
        box = QMessageBox()
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("Zenith Business")
        box.setText(message)
        box.exec()
    except Exception:  # pragma: no cover - defensive; never raise from handler
        _logger.exception("Failed to display error dialog")


def install_global_exception_handler() -> None:
    """Install the application-wide exception hook (idempotent)."""
    global _previous_hook
    if sys.excepthook is not handle_exception:
        _previous_hook = sys.excepthook
        sys.excepthook = handle_exception
        _logger.debug("Global exception handler installed")
