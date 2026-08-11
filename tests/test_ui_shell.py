"""UI shell foundation (Prompt 01 §12-§14, §33, §32).

Runs headlessly via the offscreen Qt platform (see conftest).
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from PyQt6.QtCore import Qt  # noqa: E402

from zenith_business.core.config import load_config  # noqa: E402
from zenith_business.core.i18n import Direction  # noqa: E402
from zenith_business.core.paths import resolve_paths  # noqa: E402
from zenith_business.database import Database  # noqa: E402
from zenith_business.database.connection import MEMORY  # noqa: E402
from zenith_business.ui.design.theme import build_stylesheet  # noqa: E402
from zenith_business.ui.main_window import MainWindow  # noqa: E402


@pytest.fixture
def window(qapp, data_home: Path) -> MainWindow:
    paths = resolve_paths().ensure()
    config = load_config(paths)
    db = Database(MEMORY)
    db.connect()
    return MainWindow(config, database=db)


def test_stylesheet_builds() -> None:
    css = build_stylesheet()
    assert "QMenuBar" in css
    assert "QStatusBar" in css


def test_window_has_title_and_menus(window: MainWindow) -> None:
    assert "Zenith Business" in window.windowTitle()
    # Top navigation exists as a menu bar (not a left sidebar).
    menus = window.menuBar().findChildren(type(window.menuBar().addMenu("x")))
    assert window.menuBar().actions()  # has top-level menus


def test_top_menu_business_items_are_placeholders(window: MainWindow) -> None:
    # Every business menu should contain only disabled placeholder actions,
    # i.e. no functional business commands (§33).
    menubar = window.menuBar()
    base_data_action = menubar.actions()[0]
    submenu = base_data_action.menu()
    assert submenu is not None
    assert all(not a.isEnabled() for a in submenu.actions())


def test_status_bar_shows_real_state_only(window: MainWindow) -> None:
    bar = window.statusBar()
    assert bar is not None
    # Development/unlicensed truth is displayed, never a faked activation.
    texts = [lbl.text() for lbl in bar.findChildren(type(_first_label(window)))]
    assert any("Development" in t or "توسعه" in t for t in texts)


def test_default_direction_is_rtl_for_dari(window: MainWindow) -> None:
    # Default language is Dari → RTL layout.
    assert window.current_direction() == Direction.RTL
    assert window.layoutDirection() == Qt.LayoutDirection.RightToLeft


def test_language_switch_flips_direction(window: MainWindow) -> None:
    window._switch_language("en")  # exercised via the same path the menu uses
    assert window.current_direction() == Direction.LTR
    assert window.layoutDirection() == Qt.LayoutDirection.LeftToRight


def _first_label(window: MainWindow):
    from PyQt6.QtWidgets import QLabel

    return window.statusBar().findChild(QLabel)
