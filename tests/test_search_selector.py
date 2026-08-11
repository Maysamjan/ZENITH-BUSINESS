"""Search-selector architecture + Sales Invoice rapid-entry (Prompt 01D §1-§5, §12)."""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from zenith_business.core.i18n import Translator  # noqa: E402
from zenith_business.ui.mock.demo_search import (  # noqa: E402
    DemoCustomerProvider,
    DemoItemProvider,
)
from zenith_business.ui.pages.sales_invoice_demo import (  # noqa: E402
    COL_CODE,
    COL_TOTAL,
    SalesInvoiceDemoPage,
)
from zenith_business.ui.widgets.search_selector import SearchSelector  # noqa: E402


@pytest.fixture(autouse=True)
def _qt(qapp):
    return qapp


# ---- providers (data-agnostic contract) ---------------------------------


def test_item_provider_matches_name_and_code() -> None:
    provider = DemoItemProvider()
    assert len(provider.columns()) == 5
    by_name = provider.search("bas")
    assert len(by_name) == 3  # the three Basmati items
    assert all("Basmati" in r.values[1] for r in by_name)
    # Payload carries structured data so nothing is re-typed downstream.
    assert {"code", "name", "unit", "stock", "price"} <= set(by_name[0].payload)
    by_code = provider.search("IT-1004")
    assert by_code and by_code[0].payload["code"] == "IT-1004"


def test_customer_provider_matches_name_code_phone() -> None:
    provider = DemoCustomerProvider()
    assert provider.search("kabul")
    assert provider.search("C-1002")
    assert provider.search("070111")  # by phone digits


# ---- selector widget behavior -------------------------------------------


def test_selector_opens_and_selects_by_keyboard() -> None:
    provider = DemoItemProvider()
    selected: list = []
    sel = SearchSelector(provider, display_index=1)
    sel.rowSelected.connect(selected.append)
    sel.show()  # needs a window for the overlay panel
    sel.open_with("bas")
    assert sel.is_panel_open()
    assert len(sel.current_rows()) == 3
    # Accept the highlighted (first) row.
    sel._accept_index(0)
    assert not sel.is_panel_open()
    assert selected and selected[0].payload["name"].startswith("Basmati")
    # The line edit shows the display column (item name).
    assert sel.text().startswith("Basmati")


def test_selector_hides_when_no_match() -> None:
    sel = SearchSelector(DemoItemProvider())
    sel.show()
    sel.open_with("zzzzz")
    assert not sel.is_panel_open()


# ---- invoice rapid-entry flow -------------------------------------------


def test_invoice_prefilled_lines_and_totals() -> None:
    page = SalesInvoiceDemoPage(Translator("en"))
    # 3 committed demo lines + 1 active entry row.
    assert page._table.rowCount() == 4
    # Grand total reflects only committed lines (73,450.00).
    assert "73,450" in page._grand_value.text()


def test_invoice_item_selection_populates_row_and_commits() -> None:
    page = SalesInvoiceDemoPage(Translator("en"))
    before = page._table.rowCount()
    page.open_item_search("bas")
    page.select_item(index=0, qty="10")
    # Active row now has a code and a computed total.
    assert page._table.item(page._active_row, COL_CODE).text().startswith("IT-")
    assert page._table.item(page._active_row, COL_TOTAL).text()
    # Committing opens a fresh active row (row count grows).
    page._commit_active_row()
    assert page._table.rowCount() == before + 1


def test_invoice_customer_autocomplete_fills_info() -> None:
    page = SalesInvoiceDemoPage(Translator("en"))
    page.select_customer(0)  # Kabul General Store
    balance_chip = page._chip_balance._value  # type: ignore[attr-defined]
    assert "12,500" in balance_chip.text()


def test_invoice_constructs_in_dari_rtl() -> None:
    page = SalesInvoiceDemoPage(Translator("fa_AF"))
    page.retranslate(Translator("en"))
    page.retranslate(Translator("fa_AF"))
    assert page._table.columnCount() == 9
