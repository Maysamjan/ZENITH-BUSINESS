"""Voucher print-preview workspace (Stage 05).

Reuses the LOCKED Stage 01 :class:`PrintPreviewPage` workspace unchanged (paper
A4/A5, language EN/Dari, zoom, Fit Width/Page, Print, Back) and only swaps the
rendered document to a :class:`VoucherPrintDocument`. No locked file is modified.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from zenith_business.core.i18n import Translator
from zenith_business.ui.pages.print_preview import PrintPreviewPage
from zenith_business.ui.print.invoice_document import PAPERS
from zenith_business.ui.print.voucher_document import VoucherData, VoucherPrintDocument


class VoucherPreviewPage(PrintPreviewPage):
    """Print-preview workspace that renders a money voucher."""

    def show_voucher(self, data: VoucherData) -> None:
        self._data = data
        self._render_base(); self._apply_zoom()

    def _render_base(self) -> None:  # override to render a voucher, keep the workspace
        if not isinstance(self._data, VoucherData):
            # initial construction uses the base demo invoice; never shown to the
            # user for vouchers (replaced by the first show_voucher call).
            return super()._render_base()
        doc = VoucherPrintDocument(self._data, Translator(self._lang), PAPERS[self._paper_key])
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
