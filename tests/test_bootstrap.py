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


def test_bootstrap_migrates_production_schema(data_home: Path) -> None:
    """Stage 02: bootstrap opens the DB and applies the production migrations.

    (Stage 01 previously asserted an empty database; Stage 02 deliberately
    creates and migrates the production schema at startup.)
    """
    boot = Bootstrap()
    boot.initialize()
    try:
        conn = boot.database.connection()
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        # Migrations have run and core business tables now exist.
        assert "schema_migrations" in tables
        for expected in ("users", "roles", "permissions", "sales", "items", "audit_log"):
            assert expected in tables
        # Baseline seed is present, but no user account yet → initial setup is required.
        assert boot.context is not None
        assert boot.context.is_setup_required is True
        assert conn.execute("SELECT COUNT(*) FROM permissions").fetchone()[0] > 0
    finally:
        boot.shutdown()
