"""Pass 7: responsive regression — at 1366×768 / 1600×900 / 1920×1080 no action
button falls below the visible area on the pinned-footer screens, and the
FormDialog stays within the available screen. Presentation-only checks.
"""

from __future__ import annotations

import pytest

from PyQt6.QtWidgets import QApplication, QLineEdit, QPushButton

from zenith_business.core.i18n import Translator

RESOLUTIONS = [(1366, 768), (1600, 900), (1920, 1080)]


@pytest.fixture
def biz(admin_context):
    ctx = admin_context
    ctx.financial_years.create(name="FY26", start_date="2026-01-01",
                               end_date="2026-12-31", make_active=True)
    ctx.wh = ctx.warehouses.create(code="MAIN", name="Main Store", is_default=True)
    ctx.bag = ctx.units_repo.id_by_code("BAG")
    ctx.rice = ctx.items.create(item_code="RICE", name="Basmati Rice 50kg",
                                base_unit_id=ctx.bag, purchase_price="1600",
                                default_sale_price="1980")
    ctx.cust = ctx.parties.create(party_code="C1", name="Kabul Store", is_customer=True)
    return ctx


def _all_buttons_visible(widget) -> bool:
    """Every push button's bottom edge sits within the widget's height."""
    h = widget.height()
    for btn in widget.findChildren(QPushButton):
        if not btn.isVisibleTo(widget):
            continue
        bottom = btn.mapTo(widget, btn.rect().bottomLeft()).y()
        if bottom > h + 1:
            return False
    return True


@pytest.mark.parametrize("w,h", RESOLUTIONS)
def test_sales_invoice_actions_reachable(biz, qapp, w, h):
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    from zenith_business.ui.widgets.search_selector import SearchRow

    pg = DocumentEntryPage(biz, Translator(), mode="sale")
    pg.set_party(SearchRow(values=["C1", "Kabul Store"], payload={"party_id": biz.cust}))
    payload = {"item_id": biz.rice, "base_unit_id": biz.bag, "item_code": "RICE",
               "name": "Basmati Rice 50kg", "unit_symbol": "bag", "sale_price": "1980"}
    for _ in range(12):  # many lines — table must scroll internally, not push actions off
        pg.add_line(payload, qty="5", price="1980")
    pg.resize(w, h)
    pg.show()
    QApplication.processEvents()
    QApplication.processEvents()
    assert pg.line_count == 12
    assert _all_buttons_visible(pg), f"an action button fell off-screen at {w}x{h}"
    pg.close()


@pytest.mark.parametrize("w,h", RESOLUTIONS)
def test_receipt_entry_actions_reachable(biz, qapp, w, h):
    from zenith_business.ui.documents.money_page import MoneyEntryPage

    pg = MoneyEntryPage(biz, Translator(), mode="receipt")
    pg.resize(w, h)
    pg.show()
    QApplication.processEvents()
    assert _all_buttons_visible(pg), f"a receipt action fell off-screen at {w}x{h}"
    pg.close()


def test_walkin_customer_fields_clear_and_stable(biz, qapp):
    """Walk-in fields are full-height labelled inputs and stay usable after
    switching Registered <-> Walk-in several times (no compression / stale gaps).
    """
    from zenith_business.ui.design.theme import build_stylesheet
    from zenith_business.ui.documents.entry_page import DocumentEntryPage
    from zenith_business.ui.design.tokens import ControlSize

    QApplication.instance().setStyleSheet(build_stylesheet())
    pg = DocumentEntryPage(biz, Translator(), mode="sale")
    pg.resize(1366, 768)
    pg.show()
    for _ in range(4):  # stability across repeated toggles
        pg._set_customer_mode("walkin")
        pg._set_customer_mode("registered")
    pg._set_customer_mode("walkin")
    QApplication.processEvents()
    QApplication.processEvents()
    assert pg._walkin_wrap.isVisible()
    for edit in (pg._walkin_name, pg._walkin_phone, pg._walkin_address):
        assert edit.isVisibleTo(pg._walkin_wrap)
        # NOT the old compact styling (26px muted inputs that caused the crush)
        assert edit.property("size") != "compact"
        # full professional input height under the app stylesheet
        assert edit.height() >= int(ControlSize.INPUT_HEIGHT)
    # Address/Note gets more width than Phone (stretch 4 vs 2)
    assert pg._walkin_address.width() > pg._walkin_phone.width()
    pg.close()


def test_walkin_panel_not_clipped_in_real_main_window(biz, qapp):
    """Regression: inside the real MainWindow at 1366×768 the header must NOT be
    squeezed by the Expanding items table, so the (taller) walk-in panel is shown
    at its full content height instead of clipping the input fields.
    """
    from zenith_business.core.config import AppConfig, LANG_DARI
    from zenith_business.ui.design.theme import build_stylesheet
    from zenith_business.ui.main_window import MainWindow

    QApplication.instance().setStyleSheet(build_stylesheet())
    cfg = AppConfig(); cfg.ui.language = LANG_DARI
    win = MainWindow(cfg, database=biz.db, current_user=biz.session.user, context=biz)
    win.resize(1366, 768)
    entry = win._s4_sales_entry
    win.content.setCurrentWidget(entry)
    entry._set_customer_mode("walkin")
    win.show()
    QApplication.processEvents()
    QApplication.processEvents()
    panel = entry._walkin_wrap
    # the panel gets its full content height (was clipped to ~78px before the fix)
    assert panel.height() >= panel.minimumSizeHint().height() - 1
    # and the action bar stays on-screen
    assert entry._btn_post.mapTo(win, entry._btn_post.rect().bottomLeft()).y() <= win.height()
    win.close()


def test_form_dialog_footer_within_screen(qapp):
    from zenith_business.ui.master.framework import FormDialog

    dlg = FormDialog(Translator(), "Tall form")
    grid = dlg.add_section("Many")
    for i in range(50):
        dlg.add_field(grid, i, 0, f"Field {i}", QLineEdit())
    dlg.show()
    QApplication.processEvents()
    screen = dlg.screen() or QApplication.primaryScreen()
    avail_h = screen.availableGeometry().height()
    # Save/Cancel are pinned in a footer OUTSIDE the scroll area, so the whole
    # dialog (and therefore the footer) fits within the available screen height.
    assert dlg.height() <= avail_h
    assert _all_buttons_visible(dlg)
    dlg.close()
