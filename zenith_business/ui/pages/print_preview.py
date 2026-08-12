"""Print-preview workspace with A4/A5 selection (Prompt 01F §6, §16).

Hosts the paginated print document on a neutral backdrop with a toolbar (paper
size toggle, Print, Back to Invoice). Same demonstration transaction as the
on-screen invoice.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Translator
from zenith_business.ui.components import apply_shadow, primary_button, secondary_button
from zenith_business.ui.design.tokens import Spacing
from zenith_business.ui.mock.demo_invoice import InvoiceData, build_demo_invoice
from zenith_business.ui.print.invoice_document import PAPERS, InvoicePrintDocument


class PrintPreviewPage(QWidget):
    """A4/A5 print-preview page with a toolbar."""

    def __init__(
        self, translator: Translator, *, on_back=None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._t = translator
        self._on_back = on_back
        self._data: InvoiceData = build_demo_invoice()
        self._paper_key = "A4"
        self._doc: InvoicePrintDocument | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        root.setSpacing(Spacing.SM)

        bar = QHBoxLayout(); bar.setSpacing(Spacing.SM)
        self._back = secondary_button(self._t.gettext("print.back"))
        if on_back is not None:
            self._back.clicked.connect(lambda: on_back())
        bar.addWidget(self._back)
        bar.addStretch(1)
        self._title = secondary_button(self._t.gettext("print.preview_title"))
        self._title.setEnabled(False)
        bar.addWidget(self._title)
        # Paper size toggle.
        self._paper_buttons: dict[str, QPushButton] = {}
        for key in ("A4", "A5"):
            b = QPushButton(key)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _c=False, k=key: self._set_paper(k))
            self._paper_buttons[key] = b
            bar.addWidget(b)
        bar.addStretch(1)
        self._print = primary_button(self._t.gettext("si.act_print"))
        bar.addWidget(self._print)
        root.addLayout(bar)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._backdrop = QWidget(); self._backdrop.setObjectName("PreviewBackdrop")
        self._backdrop.setStyleSheet("#PreviewBackdrop { background: #6B7688; }")
        self._bl = QVBoxLayout(self._backdrop)
        self._bl.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        self._bl.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._backdrop)
        root.addWidget(self._scroll, stretch=1)

        self._rebuild()

    def show_invoice(self, data: InvoiceData) -> None:
        self._data = data
        self._rebuild()

    def set_paper(self, key: str) -> None:
        self._set_paper(key)

    def _set_paper(self, key: str) -> None:
        if key in PAPERS:
            self._paper_key = key
            self._rebuild()

    def _rebuild(self) -> None:
        while self._bl.count():
            item = self._bl.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None); w.deleteLater()
        self._doc = InvoicePrintDocument(self._data, self._t, PAPERS[self._paper_key])
        apply_shadow(self._doc, blur=40, y=8, alpha=90)
        self._bl.addWidget(self._doc, alignment=Qt.AlignmentFlag.AlignHCenter)
        for key, b in self._paper_buttons.items():
            b.setProperty("variant", "primary" if key == self._paper_key else None)
            b.style().unpolish(b); b.style().polish(b)

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext("print.preview_title"))
        self._back.setText(translator.gettext("print.back"))
        self._print.setText(translator.gettext("si.act_print"))
        self._rebuild()
