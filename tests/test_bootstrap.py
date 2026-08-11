"""Headless startup steps (Prompt 01 §4, §32)."""

from __future__ import annotations

from pathlib import Path

from zenith_business.app import Bootstrap
from zenith_business.core.config import AppConfig
from zenith_business.database import check_health


def test_bootstrap_initialize(data_home: Path) -> None:
    boot = Bootstrap()
    config = boot.initialize()
    try:
        assert isinstance(config, AppConfig)
        # Database infrastructure is ready and healthy.
        assert boot.database is not None
        health = check_health(boot.database)
        assert health.ok is True
        # License provider reports a development (unlicensed) build.
        assert boot.license_provider.current_state().is_activated is False
    finally:
        boot.shutdown()


def test_bootstrap_creates_no_business_tables(data_home: Path) -> None:
    boot = Bootstrap()
    boot.initialize()
    try:
        conn = boot.database.connection()
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]
        # Stage 01 must not create ANY tables (business or otherwise).
        assert tables == []
    finally:
        boot.shutdown()
