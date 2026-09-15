"""Costing report print-preview workspace (Stage 08) — A4 only.

The same preview chrome the inventory report uses (EN/Dari, zoom, Fit Width /
Fit Page, Print, Back), rendering the Stage 08 sheet instead: item counts that
count items, a totals block of its own, and Dari pinned to the bundled font.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from zenith_business.core.i18n import Translator
from zenith_business.ui.documents.inventory_report_preview import InventoryReportPreviewPage
from zenith_business.ui.print.costing_report_document import (
    CostingReportPrintData,
    CostingReportPrintDocument,
)
from zenith_business.ui.print.invoice_document import PAPERS


class CostingReportPreviewPage(InventoryReportPreviewPage):
    """Print-preview workspace that renders a costing report (A4 only)."""

    def show_report(self, data: CostingReportPrintData) -> None:
        self._data = data
        self._paper_key = "A4"
        self._render_base(); self._apply_zoom()

    def _render_base(self) -> None:
        if not isinstance(self._data, CostingReportPrintData):
            return super()._render_base()
        doc = CostingReportPrintDocument(
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
