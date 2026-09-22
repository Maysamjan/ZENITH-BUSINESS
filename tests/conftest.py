"""Shared pytest fixtures for Stage 01 foundation tests.

The Qt platform is forced to ``offscreen`` so UI-shell tests run headlessly in
CI/dev containers without a display server.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator

import pytest

# Must be set before PyQt6 imports a platform plugin.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from zenith_business.core import logging_setup  # noqa: E402
from zenith_business.core.paths import DATA_HOME_ENV, resolve_paths  # noqa: E402


@pytest.fixture
def data_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate all app data locations inside a temp directory."""
    monkeypatch.setenv(DATA_HOME_ENV, str(tmp_path))
    logging_setup.reset_logging_for_tests()
    yield tmp_path
    logging_setup.reset_logging_for_tests()


@pytest.fixture
def app_paths(data_home: Path):
    """Resolved + created AppPaths rooted in the temp data home."""
    return resolve_paths().ensure()


@pytest.fixture(scope="session")
def qapp() -> Iterator[object]:
    """A single QApplication for UI tests (offscreen)."""
    pytest.importorskip("PyQt6.QtWidgets")
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


# ---- Stage 02 fixtures --------------------------------------------------


@pytest.fixture
def context(tmp_path: Path):
    """A fully-migrated in-memory ApplicationContext (Stage 02)."""
    from zenith_business.database.connection import Database, MEMORY
    from zenith_business.services.context import open_application_context

    db = Database(MEMORY)
    ctx = open_application_context(db, backups_dir=tmp_path / "backups")
    try:
        yield ctx
    finally:
        db.close()


@pytest.fixture
def admin_context(context):
    """Context with a signed-in administrator (setup completed)."""
    context.setup.create_administrator(
        username="admin", password="Str0ngPass!", full_name="System Admin",
        company_name="Test Co.")
    context.auth.login("admin", "Str0ngPass!")
    return context


# ---- Stage 10 final: licensing ------------------------------------------


def activate_for_tests(ctx, *, license_type: str = "FULL",
                       expires_at: str | None = None) -> bytes:
    """Give a context a genuine, signed licence for the machine running it.

    Licensing is a **pre-login gate** from Stage 10 final onwards: an
    unactivated installation stops at the activation screen and never reaches
    login or the workspace. Every test about something behind that gate
    therefore needs a real licence, not a bypass — there is no bypass, which is
    the point. The keypair is generated per call, lives in memory, and the
    private half never leaves this process.
    """
    from tests.tooling.license_signing import generate_keypair, make_license

    private, public = generate_keypair()
    ctx.licensing._explicit_key = public
    me = ctx.licensing.machine
    text = make_license(private, machine_fingerprint=me.fingerprint,
                        machine_traits=me.traits, license_type=license_type,
                        license_id=f"ZB-{license_type}-TEST01",
                        expires_at=expires_at)
    ctx.licensing.license_path.parent.mkdir(parents=True, exist_ok=True)
    ctx.licensing.license_path.write_text(text, encoding="utf-8")
    return public


@pytest.fixture
def licensed_context(context):
    """A fully-migrated context that has been activated, so the gate lets it by."""
    pytest.importorskip("cryptography", reason="test signing tooling only")
    activate_for_tests(context)
    return context
