"""Inventory report print-preview workspace (Stage 06) — A4 only.

Reuses the LOCKED preview workspace (EN/Dari, zoom, Fit Width/Page, Print, Back)
and swaps in an :class:`InventoryReportPrintDocument`. Like the Sales Report, A5
is not offered: an inventory table is wide and shrinking it hurts readability.
A5 remains available for invoices, receipts and vouchers.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from zenith_business.core.i18n import Translator
from zenith_business.ui.pages.print_preview import PrintPreviewPage
from zenith_business.ui.print.inventory_report_document import (
    InventoryReportPrintData,
    InventoryReportPrintDocument,
)
from zenith_business.ui.print.invoice_document import PAPERS


class InventoryReportPreviewPage(PrintPreviewPage):
    """Print-preview workspace that renders an inventory report (A4 only)."""

    def __init__(self, translator, *, on_back=None, parent=None) -> None:
        super().__init__(translator, on_back=on_back, parent=parent)
        self._restrict_to_a4()

    def _restrict_to_a4(self) -> None:
        self._paper_key = "A4"
        a5 = self._paper_buttons.pop("A5", None)
        if a5 is not None:
            a5.hide()
            a5.setParent(None)

    def _set_paper(self, key: str) -> None:  # ignore anything but A4
        if key != "A4":
            return
        super()._set_paper(key)

    def show_report(self, data: InventoryReportPrintData) -> None:
        self._data = data
        self._paper_key = "A4"
        self._render_base(); self._apply_zoom()

    def _render_base(self) -> None:
        if not isinstance(self._data, InventoryReportPrintData):
            return super()._render_base()
        doc = InventoryReportPrintDocument(
            self._data, Translator(self._lang), PAPERS[self._paper_key])
        doc.show()
        QApplication.processEvents()
        self._base = doc.grab()
        doc.deleteLater()
        for key, b in self._paper_buttons.items():
            b.setProperty("variant", "primary" if key == self._paper_key else None)
            b.style().unpolish(b); b.style().polish(b)
        for code, b in self._lang_buttons.items():
            b.setProperty("variant", "primary" if code == self._lang else None)
            b.style().unpolish(b); b.style().polish(b)
