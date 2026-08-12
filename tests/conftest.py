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
