"""Financial statement print-preview workspace (Stage 09) — A4 only.

The Stage 08 costing preview with one change: it renders the Stage 09 sheet, so
an ageing statement gets its columnar totals row. Everything else — EN/Dari
switching, zoom, Fit Width / Fit Page, Print, Back — is inherited unchanged.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from zenith_business.core.i18n import Translator
from zenith_business.ui.documents.costing_report_preview import CostingReportPreviewPage
from zenith_business.ui.print.accounting_report_document import (
    AccountingReportPrintDocument,
)
from zenith_business.ui.print.costing_report_document import CostingReportPrintData
from zenith_business.ui.print.invoice_document import PAPERS


class AccountingReportPreviewPage(CostingReportPreviewPage):
    """Print-preview workspace that renders a financial statement (A4 only)."""

    def _render_base(self) -> None:
        if not isinstance(self._data, CostingReportPrintData):
            return super()._render_base()
        doc = AccountingReportPrintDocument(
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
