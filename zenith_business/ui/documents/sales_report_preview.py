"""Sales Report print-preview workspace (Stage 05 final).

Reuses the LOCKED print-preview workspace unchanged (A4/A5 paper, EN/Dari
language, zoom, Fit Width/Page, Print, Back) and only swaps the rendered document
to a :class:`SalesReportPrintDocument`. No locked file is modified.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from zenith_business.core.i18n import Translator
from zenith_business.ui.pages.print_preview import PrintPreviewPage
from zenith_business.ui.print.invoice_document import PAPERS
from zenith_business.ui.print.sales_report_document import (
    SalesReportPrintData,
    SalesReportPrintDocument,
)


class SalesReportPreviewPage(PrintPreviewPage):
    """Print-preview workspace that renders a Sales Report."""

    def show_report(self, data: SalesReportPrintData) -> None:
        self._data = data
        self._render_base(); self._apply_zoom()

    def _render_base(self) -> None:  # override to render a report; keep the workspace
        if not isinstance(self._data, SalesReportPrintData):
            return super()._render_base()
        doc = SalesReportPrintDocument(self._data, Translator(self._lang), PAPERS[self._paper_key])
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
