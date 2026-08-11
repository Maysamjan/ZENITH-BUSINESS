"""Global exception handling (Prompt 01 §8, §32)."""

from __future__ import annotations

import sys

from zenith_business.core.error_handler import (
    handle_exception,
    install_global_exception_handler,
)
from zenith_business.core.exceptions import ZenithError


def test_install_sets_excepthook() -> None:
    original = sys.excepthook
    try:
        install_global_exception_handler()
        assert sys.excepthook is handle_exception
    finally:
        sys.excepthook = original


def test_handler_logs_unhandled(data_home, caplog) -> None:
    import logging

    from zenith_business.core.logging_setup import ROOT_LOGGER_NAME, get_logger

    get_logger()  # ensure the logger exists
    with caplog.at_level(logging.CRITICAL, logger=ROOT_LOGGER_NAME):
        try:
            raise ZenithError("boom", user_message="Friendly message")
        except ZenithError:
            handle_exception(*sys.exc_info())  # type: ignore[arg-type]
    assert any("Unhandled exception" in r.message for r in caplog.records)


def test_zenith_error_carries_user_message() -> None:
    err = ZenithError("technical detail", user_message="Please try again.")
    assert err.user_message == "Please try again."
    # Default user message when none supplied.
    assert ZenithError("x").user_message == ZenithError.default_user_message
