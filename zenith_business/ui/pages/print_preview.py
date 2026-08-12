"""Print-preview workspace hosting the A4 Sales Invoice (Prompt 01E §16, §19).

Shows the customer-facing A4 document on a neutral preview backdrop with a small
toolbar (title, Print, Back to Invoice). Reached from the invoice's Save & Print
/ Print actions with the same demonstration transaction.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Translator
from zenith_business.ui.components import apply_shadow, primary_button, secondary_button
from zenith_business.ui.design.tokens import Spacing
from zenith_business.ui.mock.demo_invoice import InvoiceData, build_demo_invoice
from zenith_business.ui.print import A4InvoiceDocument


class PrintPreviewPage(QWidget):
    """A4 print-preview page with a toolbar."""

    def __init__(
        self, translator: Translator, *, on_back=None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._t = translator
        self._on_back = on_back
        self._data: InvoiceData = build_demo_invoice()
        self._doc: A4InvoiceDocument | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.MD, Spacing.MD, Spacing.MD, Spacing.MD)
        root.setSpacing(Spacing.SM)

        # Toolbar.
        bar = QHBoxLayout(); bar.setSpacing(Spacing.SM)
        self._title = secondary_button(self._t.gettext("print.preview_title"))
        self._title.setEnabled(False)
        self._back = secondary_button(self._t.gettext("print.back"))
        if on_back is not None:
            self._back.clicked.connect(lambda: on_back())
        self._print = primary_button(self._t.gettext("si.act_print"))
        bar.addWidget(self._back)
        bar.addStretch(1)
        bar.addWidget(self._title)
        bar.addStretch(1)
        bar.addWidget(self._print)
        root.addLayout(bar)

        # Preview backdrop.
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._backdrop = QWidget()
        self._backdrop.setObjectName("PreviewBackdrop")
        self._backdrop.setStyleSheet("#PreviewBackdrop { background: #6B7688; }")
        self._backdrop_layout = QVBoxLayout(self._backdrop)
        self._backdrop_layout.setContentsMargins(Spacing.XXL, Spacing.XXL, Spacing.XXL, Spacing.XXL)
        self._backdrop_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._scroll.setWidget(self._backdrop)
        root.addWidget(self._scroll, stretch=1)

        self._rebuild()

    def show_invoice(self, data: InvoiceData) -> None:
        self._data = data
        self._rebuild()

    def _rebuild(self) -> None:
        if self._doc is not None:
            self._doc.setParent(None)
            self._doc.deleteLater()
        self._doc = A4InvoiceDocument(self._data, self._t)
        apply_shadow(self._doc, blur=40, y=8, alpha=90)
        # Clear then add so only one page is present.
        while self._backdrop_layout.count():
            item = self._backdrop_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        self._backdrop_layout.addWidget(self._doc, alignment=Qt.AlignmentFlag.AlignHCenter)

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext("print.preview_title"))
        self._back.setText(translator.gettext("print.back"))
        self._print.setText(translator.gettext("si.act_print"))
        self._rebuild()
