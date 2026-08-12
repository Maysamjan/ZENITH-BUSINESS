"""A4 printed invoice + Save & Print workflow (Prompt 01E §16-§19)."""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from zenith_business.core.i18n import Translator  # noqa: E402
from zenith_business.core.numbers import amount_in_words  # noqa: E402
from zenith_business.ui.mock.demo_invoice import (  # noqa: E402
    build_demo_invoice,
    build_demo_invoice_n,
)
from zenith_business.ui.pages.print_preview import PrintPreviewPage  # noqa: E402
from zenith_business.ui.print import (  # noqa: E402
    A4,
    A5,
    A4InvoiceDocument,
    InvoicePrintDocument,
    paginate,
)


@pytest.fixture(autouse=True)
def _qt(qapp):
    return qapp


def test_demo_invoice_totals() -> None:
    d = build_demo_invoice()
    assert d.subtotal == pytest.approx(73500.0)
    assert d.discount_total == pytest.approx(50.0)
    assert d.grand_total == pytest.approx(73450.0)
    assert d.paid == pytest.approx(40000.0)
    assert d.remaining == pytest.approx(33450.0)


def test_a4_document_constructs_both_directions() -> None:
    data = build_demo_invoice()
    for lang in ("en", "fa_AF"):
        doc = A4InvoiceDocument(data, Translator(lang))
        assert doc.width() == A4.w  # page width is fixed to the paper


def test_amount_in_words() -> None:
    assert amount_in_words(73450, "AFN", "en") == "Seventy-three thousand four hundred fifty Afghanis Only"
    fa = amount_in_words(73450, "AFN", "fa_AF")
    assert "افغانی" in fa and "هزار" in fa
    assert amount_in_words(0, "AFN", "en").startswith("Zero")


def test_print_reflow_pagination() -> None:
    # Short invoice → single page (totals fit).
    assert paginate(1, A4.rows_per_page, A4.last_reserve) == [(0, 1, True)]
    assert paginate(3, A4.rows_per_page, A4.last_reserve) == [(0, 3, True)]
    # Long invoice → multiple pages, last page flagged, every page >= 1 row.
    pages = paginate(40, A4.rows_per_page, A4.last_reserve)
    assert len(pages) >= 2
    assert pages[-1][2] is True
    assert all(end > start for start, end, _ in pages)
    # Rows are covered exactly once, in order.
    assert pages[0][0] == 0 and pages[-1][1] == 40


def test_multipage_a4_builds_multiple_pages() -> None:
    doc = InvoicePrintDocument(build_demo_invoice_n(40), Translator("en"), A4)
    # One QFrame page per paginated slice.
    from PyQt6.QtWidgets import QFrame
    pages = [c for c in doc.findChildren(QFrame) if c.objectName() == "Page"]
    assert len(pages) >= 2


def test_a5_single_item_is_compact_single_page() -> None:
    doc = InvoicePrintDocument(build_demo_invoice_n(1), Translator("en"), A5)
    from PyQt6.QtWidgets import QFrame
    pages = [c for c in doc.findChildren(QFrame) if c.objectName() == "Page"]
    assert len(pages) == 1
    assert doc.width() == A5.w


def test_print_preview_page() -> None:
    page = PrintPreviewPage(Translator("en"))
    page.show_invoice(build_demo_invoice())
    page.retranslate(Translator("fa_AF"))  # must not raise


def test_save_and_print_opens_preview_with_same_transaction(data_home) -> None:
    from zenith_business.core.config import load_config
    from zenith_business.core.paths import resolve_paths
    from zenith_business.ui.main_window import MainWindow

    win = MainWindow(load_config(resolve_paths().ensure()))
    win.show_sales_invoice()
    # Trigger the invoice's Save & Print pathway.
    win.sales_invoice_page._trigger_print()
    assert win.content.currentWidget() is win.print_preview_page
    # The preview uses the SAME transaction shown in the invoice (§19).
    assert win.print_preview_page._data is win.sales_invoice_page.demo_invoice
