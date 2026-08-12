"""Application logging foundation (Prompt 01 §7).

This is *technical* application logging only. It is deliberately separate from
the future business Audit Log (which records user/business actions and lives in
the security/audit layer).

Guarantees:
    * Levels DEBUG/INFO/WARNING/ERROR/CRITICAL are supported.
    * Logs are written to the user-data logs directory with size-based rotation
      so files cannot grow without bound.
    * Secrets must never be logged (passwords, license private secrets, auth
      tokens). This module provides the plumbing; callers must not pass secrets.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from zenith_business.core.config import LoggingConfig

#: Root logger name for the whole application. All app loggers are children of
#: this, so third-party library logging is not affected.
ROOT_LOGGER_NAME = "zenith"

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Guards against attaching duplicate handlers if setup runs more than once.
_configured = False


def get_logger(name: str | None = None) -> logging.Logger:
    """Return an application logger (a child of the Zenith root logger)."""
    if not name:
        return logging.getLogger(ROOT_LOGGER_NAME)
    if name.startswith(ROOT_LOGGER_NAME):
        return logging.getLogger(name)
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")


def setup_logging(
    logs_dir: Path,
    config: LoggingConfig | None = None,
    *,
    console: bool = True,
) -> logging.Logger:
    """Initialize application logging and return the root Zenith logger.

    Parameters
    ----------
    logs_dir:
        Directory for log files (created if missing).
    config:
        Logging configuration (level, rotation). Defaults are used if omitted.
    console:
        Also emit to stderr (useful during development).
    """
    global _configured

    cfg = config or LoggingConfig()
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "zenith_business.log"

    logger = logging.getLogger(ROOT_LOGGER_NAME)
    level = getattr(logging, cfg.level.upper(), logging.INFO)
    logger.setLevel(level)
    # Do not propagate to the Python root logger (avoids duplicate output).
    logger.propagate = False

    if _configured:
        # Re-entrancy: update level but do not stack handlers.
        for handler in logger.handlers:
            handler.setLevel(level)
        return logger

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=cfg.max_bytes,
        backupCount=cfg.backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if console:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level)
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    _configured = True
    logger.debug("Logging initialized at level %s -> %s", cfg.level, log_file)
    return logger


def reset_logging_for_tests() -> None:
    """Detach handlers and reset state. Test-only helper."""
    global _configured
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    _configured = False
