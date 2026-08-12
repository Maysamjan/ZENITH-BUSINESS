"""Print-preview workspace (Prompt 01G §7).

A real document-preview workspace: paper size (A4/A5), orientation (Portrait),
language (English/Dari), zoom (Fit Width / Fit Page / −/+), and Print. The
document is rendered to a pixmap and scaled, so zoom and fit behave like a real
preview. Same demonstration transaction as the on-screen invoice.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import LANG_DARI, LANG_ENGLISH, Translator
from zenith_business.ui.components import primary_button, secondary_button, vertical_line
from zenith_business.ui.design.tokens import Spacing
from zenith_business.ui.mock.demo_invoice import InvoiceData, build_demo_invoice
from zenith_business.ui.print.invoice_document import PAPERS, InvoicePrintDocument


class PrintPreviewPage(QWidget):
    """A4/A5 print-preview workspace with zoom and language controls."""

    _ZOOMS = [0.5, 0.65, 0.8, 1.0, 1.25, 1.5]

    def __init__(
        self, translator: Translator, *, on_back=None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._t = translator
        self._on_back = on_back
        self._data: InvoiceData = build_demo_invoice()
        self._paper_key = "A4"
        self._lang = translator.language
        self._zoom = 0.8
        self._fit = "width"  # 'width' | 'page' | None
        self._base: QPixmap | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.SM, Spacing.SM, Spacing.SM, Spacing.SM)
        root.setSpacing(Spacing.SM)
        root.addWidget(self._build_toolbar())

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._backdrop = QWidget(); self._backdrop.setObjectName("PreviewBackdrop")
        self._backdrop.setStyleSheet("#PreviewBackdrop { background: #5C6675; }")
        bl = QVBoxLayout(self._backdrop)
        bl.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        bl.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._canvas = QLabel(); self._canvas.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        bl.addWidget(self._canvas, alignment=Qt.AlignmentFlag.AlignHCenter)
        self._scroll.setWidget(self._backdrop)
        root.addWidget(self._scroll, stretch=1)

        self._render_base()
        self._apply_zoom()

    # ---- toolbar ---------------------------------------------------------

    def _seg(self, text: str, cb) -> QPushButton:
        b = QPushButton(text); b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(lambda _c=False: cb())
        return b

    def _group_label(self, key: str) -> QLabel:
        l = QLabel(self._t.gettext(key)); l.setProperty("role", "muted")
        return l

    def _build_toolbar(self) -> QWidget:
        bar = QFrame(); bar.setProperty("role", "actionbar")
        row = QHBoxLayout(bar)
        row.setContentsMargins(Spacing.MD, Spacing.XS, Spacing.MD, Spacing.XS)
        row.setSpacing(Spacing.SM)

        self._back = secondary_button(self._t.gettext("print.back"))
        if self._on_back is not None:
            self._back.clicked.connect(lambda: self._on_back())
        row.addWidget(self._back)
        row.addWidget(vertical_line())

        self._lbl_paper = self._group_label("print.paper"); row.addWidget(self._lbl_paper)
        self._paper_buttons: dict[str, QPushButton] = {}
        for key in ("A4", "A5"):
            b = self._seg(key, lambda k=key: self._set_paper(k))
            self._paper_buttons[key] = b; row.addWidget(b)
        row.addWidget(vertical_line())

        self._lbl_lang = self._group_label("print.language"); row.addWidget(self._lbl_lang)
        self._lang_buttons: dict[str, QPushButton] = {}
        for code, txt in ((LANG_ENGLISH, "EN"), (LANG_DARI, "دری")):
            b = self._seg(txt, lambda c=code: self._set_lang(c))
            self._lang_buttons[code] = b; row.addWidget(b)
        row.addWidget(vertical_line())

        self._lbl_zoom = self._group_label("print.zoom"); row.addWidget(self._lbl_zoom)
        row.addWidget(self._seg("−", self._zoom_out))
        self._zoom_label = QLabel("80%"); self._zoom_label.setMinimumWidth(44)
        self._zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self._zoom_label)
        row.addWidget(self._seg("+", self._zoom_in))
        self._btn_fit_w = self._seg(self._t.gettext("print.fit_width"), lambda: self._set_fit("width"))
        self._btn_fit_p = self._seg(self._t.gettext("print.fit_page"), lambda: self._set_fit("page"))
        row.addWidget(self._btn_fit_w); row.addWidget(self._btn_fit_p)

        row.addStretch(1)
        self._orient = QLabel(self._t.gettext("print.orientation")); self._orient.setProperty("role", "muted")
        row.addWidget(self._orient); row.addWidget(vertical_line())
        self._print = primary_button(self._t.gettext("si.act_print"))
        row.addWidget(self._print)
        return bar

    # ---- public ----------------------------------------------------------

    def show_invoice(self, data: InvoiceData) -> None:
        self._data = data
        self._render_base(); self._apply_zoom()

    def set_paper(self, key: str) -> None:
        self._set_paper(key)

    # ---- state -----------------------------------------------------------

    def _set_paper(self, key: str) -> None:
        if key in PAPERS:
            self._paper_key = key
            self._render_base(); self._apply_fit_or_zoom()

    def _set_lang(self, code: str) -> None:
        self._lang = code
        self._render_base(); self._apply_fit_or_zoom()

    def _set_fit(self, mode: str) -> None:
        self._fit = mode
        self._apply_fit_or_zoom()

    def _zoom_in(self) -> None:
        self._fit = None
        self._zoom = min(self._ZOOMS[-1], self._next_zoom(1))
        self._apply_zoom()

    def _zoom_out(self) -> None:
        self._fit = None
        self._zoom = max(self._ZOOMS[0], self._next_zoom(-1))
        self._apply_zoom()

    def _next_zoom(self, direction: int) -> float:
        import bisect
        idx = bisect.bisect_left(self._ZOOMS, self._zoom)
        idx = max(0, min(len(self._ZOOMS) - 1, idx + direction))
        return self._ZOOMS[idx]

    # ---- rendering -------------------------------------------------------

    def _render_base(self) -> None:
        doc = InvoicePrintDocument(self._data, Translator(self._lang), PAPERS[self._paper_key])
        doc.show()
        # Let the layout settle before grabbing.
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()
        self._base = doc.grab()
        doc.deleteLater()
        for key, b in self._paper_buttons.items():
            b.setProperty("variant", "primary" if key == self._paper_key else None)
            b.style().unpolish(b); b.style().polish(b)
        for code, b in self._lang_buttons.items():
            b.setProperty("variant", "primary" if code == self._lang else None)
            b.style().unpolish(b); b.style().polish(b)

    def _apply_fit_or_zoom(self) -> None:
        if self._fit == "width":
            self._set_fit_width()
        elif self._fit == "page":
            self._set_fit_page()
        else:
            self._apply_zoom()

    def _set_fit_width(self) -> None:
        if self._base is None:
            return
        avail = max(200, self._scroll.viewport().width() - 2 * Spacing.XL - 8)
        self._zoom = avail / self._base.width()
        self._apply_zoom(update_fit=False)

    def _set_fit_page(self) -> None:
        if self._base is None:
            return
        avail_h = max(200, self._scroll.viewport().height() - 2 * Spacing.XL - 8)
        # base may contain multiple pages; fit one page height (paper.h * scale of grab)
        page_h = PAPERS[self._paper_key].h
        self._zoom = avail_h / page_h
        self._apply_zoom(update_fit=False)

    def _apply_zoom(self, update_fit: bool = True) -> None:
        if update_fit:
            self._fit = None
        if self._base is None:
            return
        w = max(1, int(self._base.width() * self._zoom))
        scaled = self._base.scaledToWidth(w, Qt.TransformationMode.SmoothTransformation)
        self._canvas.setPixmap(scaled)
        self._canvas.setFixedSize(scaled.size())
        self._zoom_label.setText(f"{round(self._zoom * 100)}%")

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # Apply fit-to-width once the viewport has a real size.
        if self._fit == "width":
            self._set_fit_width()

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._back.setText(translator.gettext("print.back"))
        self._print.setText(translator.gettext("si.act_print"))
        self._lbl_paper.setText(translator.gettext("print.paper"))
        self._lbl_lang.setText(translator.gettext("print.language"))
        self._lbl_zoom.setText(translator.gettext("print.zoom"))
        self._btn_fit_w.setText(translator.gettext("print.fit_width"))
        self._btn_fit_p.setText(translator.gettext("print.fit_page"))
        self._orient.setText(translator.gettext("print.orientation"))
