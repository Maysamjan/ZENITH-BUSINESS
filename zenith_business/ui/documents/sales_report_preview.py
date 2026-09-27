"""Sales Report print-preview workspace (Stage 05 final).

Reuses the LOCKED print-preview workspace (EN/Dari language, zoom, Fit
Width/Page, Print, Back) and only swaps the rendered document to a
:class:`SalesReportPrintDocument`. No locked file is modified.

**A4 only.** A detailed Sales Report carries nine columns; squeezing them onto
A5 hurts readability, so this preview exposes A4 exclusively (both English and
Dari). A5 remains available for documents where it makes sense — invoices,
receipts and vouchers — via their own preview workspaces.
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
    """Print-preview workspace that renders a Sales Report (A4 only)."""

    def __init__(self, translator, *, on_back=None, parent=None) -> None:
        super().__init__(translator, on_back=on_back, parent=parent)
        self._restrict_to_a4()

    def _restrict_to_a4(self) -> None:
        """Remove the A5 paper option — the report is A4 only (readability)."""
        self._paper_key = "A4"
        a5 = self._paper_buttons.pop("A5", None)
        if a5 is not None:
            a5.hide()
            a5.setParent(None)

    def _set_paper(self, key: str) -> None:  # ignore any request other than A4
        if key != "A4":
            return
        super()._set_paper(key)

    def show_report(self, data: SalesReportPrintData) -> None:
        self._data = data
        self._paper_key = "A4"
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
