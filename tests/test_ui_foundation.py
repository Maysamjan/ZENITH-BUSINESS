"""Pass 1 shared-UI foundation: FormDialog scroll/pinned-footer/screen clamp,
and the RowActions inline+overflow action control (design system §G/§I).

These are pure-presentation contracts — no business logic is exercised.
"""

from __future__ import annotations

import pytest

from PyQt6.QtWidgets import QLineEdit, QScrollArea, QToolButton

from zenith_business.core.i18n import Translator


@pytest.fixture(autouse=True)
def _needs_qt(qapp):
    return qapp


# ---- FormDialog: header + scrollable body + pinned footer + clamp --------

def test_form_dialog_has_scrollable_body_and_pinned_footer():
    from zenith_business.ui.master.framework import FormDialog

    dlg = FormDialog(Translator(), "Test")
    # body is inside a QScrollArea so tall forms scroll instead of overflowing
    assert isinstance(dlg._scroll, QScrollArea)
    assert dlg._scroll.widgetResizable() is True
    # public API unchanged
    grid = dlg.add_section("Section")
    dlg.add_field(grid, 0, 0, "Field", QLineEdit())
    # Save/Cancel exist and Save is the default (Enter submits)
    assert dlg._save.isDefault()
    fired = []
    dlg.set_submit(lambda: fired.append(1))
    dlg._save.click()
    assert fired == [1]
    # error region still works (check explicit shown-state; dialog isn't shown)
    dlg.set_error("boom")
    assert not dlg._error.isHidden()
    dlg.clear_error()
    assert dlg._error.isHidden()


def test_form_dialog_clamps_to_screen_height():
    from PyQt6.QtWidgets import QApplication

    from zenith_business.ui.master.framework import FormDialog

    dlg = FormDialog(Translator(), "Tall")
    grid = dlg.add_section("Big")
    for i in range(40):  # force a very tall body
        dlg.add_field(grid, i, 0, f"Field {i}", QLineEdit())
    dlg.show()
    QApplication.processEvents()
    screen = dlg.screen() or QApplication.primaryScreen()
    avail = screen.availableGeometry().height()
    # a real clamp was applied (not the default QWIDGETSIZE_MAX) and it fits
    assert dlg.maximumHeight() <= avail
    assert dlg.height() <= avail
    dlg.close()


# ---- RowActions: inline buttons + ⋯ overflow menu ------------------------

def test_row_actions_inline_only_when_few():
    from zenith_business.ui.components import RowActions

    ra = RowActions()
    ra.add_button("Edit", lambda: None)
    ra.add_button("Deactivate", lambda: None)
    assert ra.findChild(QToolButton) is None  # no kebab for 2 inline actions


def test_row_actions_overflow_menu_when_many():
    from zenith_business.ui.components import RowActions

    seen = []
    ra = RowActions()
    ra.add_button("View", lambda: seen.append("view"), variant="accent")
    a_edit = ra.add_menu_action("Edit", lambda: seen.append("edit"))
    ra.add_menu_action("Deactivate", lambda: seen.append("deact"))
    kebab = ra.findChild(QToolButton)
    assert kebab is not None and kebab.property("role") == "kebab"
    assert len(ra._menu.actions()) == 2
    a_edit.trigger()
    assert seen == ["edit"]


def test_management_page_collapses_three_actions_into_menu():
    from zenith_business.ui.components import RowActions
    from zenith_business.ui.master.framework import Column, ManagementPage

    page = ManagementPage(
        Translator(), title_key="persons.title", subtitle_key=None,
        columns=[Column("name", "persons.col_name", stretch=True)],
        on_new=None, on_edit=lambda d: None, on_toggle_active=lambda d: None,
        on_view=lambda d: None)
    page.set_rows([{"id": 1, "name": "Acme", "is_active": 1}])
    cell = page._table.cellWidget(0, 1)  # actions column
    assert isinstance(cell, RowActions)
    kebab = cell.findChild(QToolButton)  # 3 actions -> 1 inline + ⋯ menu
    assert kebab is not None
    assert len(cell._menu.actions()) == 2  # edit + deactivate in the menu
