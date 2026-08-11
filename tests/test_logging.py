"""Logging foundation (Prompt 01 §7, §32)."""

from __future__ import annotations

import logging
from pathlib import Path

from zenith_business.core.config import LoggingConfig
from zenith_business.core.logging_setup import (
    ROOT_LOGGER_NAME,
    get_logger,
    setup_logging,
)


def test_setup_creates_log_file_and_writes(app_paths) -> None:
    logger = setup_logging(app_paths.logs_dir, LoggingConfig(level="DEBUG"), console=False)
    logger.info("hello world")
    for handler in logger.handlers:
        handler.flush()
    log_file = app_paths.logs_dir / "zenith_business.log"
    assert log_file.exists()
    assert "hello world" in log_file.read_text(encoding="utf-8")


def test_setup_is_idempotent_no_duplicate_handlers(app_paths) -> None:
    setup_logging(app_paths.logs_dir, console=False)
    count = len(logging.getLogger(ROOT_LOGGER_NAME).handlers)
    setup_logging(app_paths.logs_dir, console=False)
    assert len(logging.getLogger(ROOT_LOGGER_NAME).handlers) == count


def test_get_logger_is_namespaced() -> None:
    log = get_logger("database")
    assert log.name == f"{ROOT_LOGGER_NAME}.database"


def test_rotation_configured(app_paths) -> None:
    cfg = LoggingConfig(level="INFO", max_bytes=1024, backup_count=3)
    logger = setup_logging(app_paths.logs_dir, cfg, console=False)
    from logging.handlers import RotatingFileHandler

    rotating = [h for h in logger.handlers if isinstance(h, RotatingFileHandler)]
    assert rotating
    assert rotating[0].maxBytes == 1024
    assert rotating[0].backupCount == 3
