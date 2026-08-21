"""Pass 4: New Item form records opening stock via the EXISTING inventory
service (inventory.record_opening -> one OPENING movement). UI-orchestration
test — no new inventory behavior is introduced.
"""

from __future__ import annotations

import pytest

from PyQt6.QtWidgets import QComboBox, QLineEdit

from zenith_business.core.i18n import Translator
from zenith_business.core.money import D


@pytest.fixture
def biz(admin_context):
    ctx = admin_context
    ctx.financial_years.create(name="FY26", start_date="2026-01-01",
                               end_date="2026-12-31", make_active=True)
    ctx.wh = ctx.warehouses.create(code="MAIN", name="Main Store", is_default=True)
    return ctx


def _capture_dialog(monkeypatch):
    """Make FormDialog.exec a no-op that records the instance for driving."""
    from zenith_business.ui.master.framework import FormDialog
    captured = {}

    def fake_exec(self):
        captured["dlg"] = self
        return 0

    monkeypatch.setattr(FormDialog, "exec", fake_exec, raising=True)
    return captured


def test_new_item_records_opening_stock(biz, qapp, monkeypatch):
    from zenith_business.ui.master.pages import ItemsPage

    page = ItemsPage(biz, Translator())
    captured = _capture_dialog(monkeypatch)
    page._new()  # constructs + "exec"s the dialog (captured, not shown)
    dlg = captured["dlg"]

    # tree order: code, barcode, name, alt, purchase, sale, min, opening_qty
    edits = dlg.findChildren(QLineEdit)
    combos = dlg.findChildren(QComboBox)     # category, unit, opening_warehouse
    edits[0].setText("RICE")                 # code
    edits[2].setText("Basmati Rice 50kg")    # name
    edits[-1].setText("50")                  # opening quantity (last line edit)
    # unit combo must resolve to a real base unit
    assert combos[1].currentData() is not None
    # opening warehouse combo defaulted to the default warehouse
    assert combos[-1].currentData() == biz.wh

    dlg._on_save()  # triggers the submit closure

    item = next(i for i in biz.items.list() if i["item_code"] == "RICE")
    # opening stock recorded to the chosen warehouse via the existing service
    assert D(biz.inventory_repo.stock_on_hand(item["id"], biz.wh)) == D("50")


def test_new_item_without_opening_qty_records_no_movement(biz, qapp, monkeypatch):
    from zenith_business.ui.master.pages import ItemsPage

    page = ItemsPage(biz, Translator())
    captured = _capture_dialog(monkeypatch)
    page._new()
    dlg = captured["dlg"]
    edits = dlg.findChildren(QLineEdit)  # code, barcode, name, alt, ...
    edits[0].setText("SUGAR")
    edits[2].setText("White Sugar 50kg")
    edits[-1].setText("0")  # no opening stock
    dlg._on_save()

    item = next(i for i in biz.items.list() if i["item_code"] == "SUGAR")
    assert D(biz.inventory_repo.stock_on_hand(item["id"], biz.wh)) == D("0")
