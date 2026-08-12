"""A4 printed invoice + Save & Print workflow (Prompt 01E §16-§19)."""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6.QtWidgets")

from zenith_business.core.i18n import Translator  # noqa: E402
from zenith_business.ui.mock.demo_invoice import build_demo_invoice  # noqa: E402
from zenith_business.ui.pages.print_preview import PrintPreviewPage  # noqa: E402
from zenith_business.ui.print import A4InvoiceDocument  # noqa: E402


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
        assert (doc.width(), doc.height()) == (A4InvoiceDocument.WIDTH, A4InvoiceDocument.HEIGHT)


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
