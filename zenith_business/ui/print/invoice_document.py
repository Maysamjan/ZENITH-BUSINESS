"""A4 printed Sales Invoice document (Prompt 01E §16-§19).

A real customer-facing invoice — not a screenshot of the app. Ink-friendly:
white page, restrained navy/brand accents used only for the header rule, title,
totals and separators (§17). Direction-aware for English LTR and Dari RTL (§18).
Driven by the shared demo transaction so it matches the on-screen invoice (§19).

Self-contained styling (its own stylesheet) so the customer document never
inherits application chrome.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Direction, Translator
from zenith_business.core.identity import IDENTITY
from zenith_business.ui.design.tokens import Color, Radius, Spacing, Typography
from zenith_business.ui.mock.demo_invoice import InvoiceData


def _money(v: float) -> str:
    return f"{v:,.2f}"


def _print_stylesheet() -> str:
    c = Color
    t = Typography
    return f"""
    QWidget#A4Page {{ background: {c.PRINT_BG}; }}
    QWidget#A4Page QLabel {{ background: transparent; color: {c.PRINT_INK};
        font-family: {t.FAMILY}; font-size: 9.5pt; }}
    QWidget#A4Page QLabel[p="company"] {{ font-size: 14pt; font-weight: {t.WEIGHT_BOLD};
        color: {c.PRINT_ACCENT}; }}
    QWidget#A4Page QLabel[p="muted"] {{ color: {c.PRINT_MUTED}; font-size: 9pt; }}
    QWidget#A4Page QLabel[p="title"] {{ font-size: 21pt; font-weight: {t.WEIGHT_BOLD};
        color: {c.PRINT_ACCENT}; letter-spacing: 1px; }}
    QWidget#A4Page QLabel[p="meta-label"] {{ color: {c.PRINT_MUTED}; font-size: 9pt; }}
    QWidget#A4Page QLabel[p="meta-value"] {{ color: {c.PRINT_INK}; font-size: 9.5pt;
        font-weight: {t.WEIGHT_MEDIUM}; }}
    QWidget#A4Page QLabel[p="section"] {{ color: {c.PRINT_ACCENT}; font-size: 10pt;
        font-weight: {t.WEIGHT_SEMIBOLD}; }}
    QWidget#A4Page QLabel[p="cust-name"] {{ font-size: 12pt; font-weight: {t.WEIGHT_SEMIBOLD}; }}
    QWidget#A4Page QLabel[p="total-label"] {{ color: {c.PRINT_MUTED}; font-size: 10pt; }}
    QWidget#A4Page QLabel[p="total-value"] {{ color: {c.PRINT_INK}; font-size: 10pt;
        font-weight: {t.WEIGHT_MEDIUM}; }}
    QWidget#A4Page QLabel[p="paid"] {{ color: {c.POSITIVE}; font-weight: {t.WEIGHT_SEMIBOLD}; }}
    QWidget#A4Page QLabel[p="due"] {{ color: {c.NEGATIVE}; font-weight: {t.WEIGHT_BOLD}; }}
    QWidget#A4Page QLabel[p="thanks"] {{ color: {c.PRINT_ACCENT}; font-size: 11pt;
        font-weight: {t.WEIGHT_SEMIBOLD}; }}
    QWidget#A4Page QLabel[p="logo"] {{ background: {c.PRINT_ACCENT}; color: #FFFFFF;
        font-size: 22pt; font-weight: {t.WEIGHT_BOLD}; border-radius: {Radius.MD}px; }}
    QWidget#A4Page QFrame[p="rule"] {{ background: {c.PRINT_ACCENT}; max-height: 3px;
        min-height: 3px; border: none; }}
    QWidget#A4Page QFrame[p="thin"] {{ background: {c.PRINT_RULE}; max-height: 1px;
        min-height: 1px; border: none; }}
    QWidget#A4Page QFrame[p="grand"] {{ background: {c.PRINT_ACCENT};
        border-radius: {Radius.MD}px; }}
    QWidget#A4Page QLabel[p="grand-label"] {{ color: #FFFFFF; font-size: 12pt;
        font-weight: {t.WEIGHT_SEMIBOLD}; }}
    QWidget#A4Page QLabel[p="grand-value"] {{ color: #FFFFFF; font-size: 15pt;
        font-weight: {t.WEIGHT_BOLD}; }}
    QWidget#A4Page QFrame[p="sign"] {{ background: {c.PRINT_RULE}; max-height: 1px;
        min-height: 1px; }}
    QWidget#A4Page QTableWidget {{ background: {c.PRINT_BG}; border: 1px solid {c.PRINT_RULE};
        gridline-color: {c.PRINT_RULE}; font-size: 9.5pt; color: {c.PRINT_INK}; }}
    QWidget#A4Page QHeaderView::section {{ background: {c.PRINT_ACCENT_SOFT};
        color: {c.PRINT_ACCENT}; border: none; border-bottom: 1px solid {c.PRINT_RULE};
        padding: 5px 6px; font-weight: {t.WEIGHT_SEMIBOLD}; }}
    """


class A4InvoiceDocument(QWidget):
    """A single A4 portrait page (approx. 96 dpi: 794×1123)."""

    WIDTH = 794
    HEIGHT = 1123

    def __init__(
        self, data: InvoiceData, translator: Translator, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._d = data
        self._t = translator
        self.setObjectName("A4Page")
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setStyleSheet(_print_stylesheet())
        self.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft if translator.direction == Direction.RTL
            else Qt.LayoutDirection.LeftToRight
        )

        page = QVBoxLayout(self)
        page.setContentsMargins(44, 40, 44, 36)
        page.setSpacing(Spacing.LG)

        page.addLayout(self._header())
        rule = QFrame(); rule.setProperty("p", "rule"); page.addWidget(rule)
        page.addLayout(self._bill_and_meta())
        page.addWidget(self._items_table())
        page.addLayout(self._summary())
        page.addStretch(1)
        page.addWidget(self._footer())

    # ---- header ----------------------------------------------------------

    def _header(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(Spacing.LG)
        # Company block with logo placeholder.
        left = QHBoxLayout(); left.setSpacing(Spacing.MD)
        logo = QLabel(IDENTITY.product[:1]); logo.setProperty("p", "logo")
        logo.setFixedSize(64, 64); logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.addWidget(logo)
        comp = QVBoxLayout(); comp.setSpacing(1)
        c = self._d.company
        name = QLabel(c.name); name.setProperty("p", "company")
        comp.addWidget(name)
        for text in (c.address, f"{c.phone}", f"{self._t.gettext('print.email')}: {c.email}",
                     f"{self._t.gettext('print.tax_id')}: {c.tax_id}"):
            lab = QLabel(text); lab.setProperty("p", "muted"); comp.addWidget(lab)
        left.addLayout(comp)
        row.addLayout(left)
        row.addStretch(1)

        # Invoice identity block.
        right = QVBoxLayout(); right.setSpacing(2)
        title = QLabel(self._t.gettext("print.title")); title.setProperty("p", "title")
        title.setAlignment(self._end_align())
        right.addWidget(title)
        ident = QGridLayout(); ident.setHorizontalSpacing(Spacing.MD); ident.setVerticalSpacing(1)
        pairs = [
            ("si.invoice_no", self._d.number),
            ("si.date", self._d.date),
            ("si.salesperson", self._d.salesperson),
            ("si.currency", self._d.currency),
        ]
        for i, (key, value) in enumerate(pairs):
            k = QLabel(self._t.gettext(key)); k.setProperty("p", "meta-label")
            v = QLabel(value); v.setProperty("p", "meta-value")
            v.setAlignment(self._end_align())
            ident.addWidget(k, i, 0)
            ident.addWidget(v, i, 1, self._end_align())
        right.addLayout(ident)
        row.addLayout(right)
        return row

    # ---- bill to + meta --------------------------------------------------

    def _bill_and_meta(self) -> QHBoxLayout:
        row = QHBoxLayout()
        col = QVBoxLayout(); col.setSpacing(2)
        col.addWidget(self._labelled("print.bill_to", "section"))
        d = self._d
        nm = QLabel(d.customer_name); nm.setProperty("p", "cust-name"); col.addWidget(nm)
        for text in (f"{self._t.gettext('si.phone')}: {d.customer_phone}",
                     f"{self._t.gettext('si.address')}: {d.customer_address}",
                     f"{self._t.gettext('si.customer_code')}: {d.customer_code}"):
            lab = QLabel(text); lab.setProperty("p", "muted"); col.addWidget(lab)
        row.addLayout(col)
        row.addStretch(1)
        return row

    # ---- items -----------------------------------------------------------

    def _items_table(self) -> QWidget:
        headers = ["si.col_row", "print.col_item", "si.col_qty", "si.col_unit",
                   "si.col_price", "si.col_discount", "si.col_total"]
        table = QTableWidget(len(self._d.lines), len(headers))
        table.setHorizontalHeaderLabels([self._t.gettext(k) for k in headers])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.verticalHeader().setDefaultSectionSize(30)

        header = table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Item
        header.setHighlightSections(False)
        widths = {0: 36, 2: 64, 3: 60, 4: 100, 5: 90, 6: 120}
        for col, w in widths.items():
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(col, w)

        numeric = {2, 4, 5, 6}
        for r, line in enumerate(self._d.lines):
            values = [str(r + 1), line.name, f"{line.qty:,.0f}", line.unit,
                      _money(line.price), _money(line.discount), _money(line.total)]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                align = (Qt.AlignmentFlag.AlignRight if col in numeric
                         else Qt.AlignmentFlag.AlignLeft)
                item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(r, col, item)

        table.setFixedHeight(36 + len(self._d.lines) * 30 + 4)
        return table

    # ---- summary ---------------------------------------------------------

    def _summary(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch(1)
        box = QVBoxLayout(); box.setSpacing(Spacing.XS)
        grid = QGridLayout(); grid.setHorizontalSpacing(Spacing.XXL); grid.setVerticalSpacing(2)
        d = self._d
        lines = [("si.subtotal", _money(d.subtotal), None),
                 ("si.discount", _money(d.discount_total), None)]
        if d.tax or d.additional:
            lines.append(("si.tax", _money(d.tax + d.additional), None))
        for i, (key, value, _p) in enumerate(lines):
            k = QLabel(self._t.gettext(key)); k.setProperty("p", "total-label")
            v = QLabel(value + f" {d.currency}"); v.setProperty("p", "total-value")
            v.setAlignment(self._end_align())
            grid.addWidget(k, i, 0); grid.addWidget(v, i, 1, self._end_align())
        box.addLayout(grid)

        # Grand total (brand band).
        grand = QFrame(); grand.setProperty("p", "grand")
        gl = QHBoxLayout(grand); gl.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        gk = QLabel(self._t.gettext("si.grand_total")); gk.setProperty("p", "grand-label")
        gv = QLabel(_money(d.grand_total) + f" {d.currency}"); gv.setProperty("p", "grand-value")
        gv.setAlignment(self._end_align())
        gl.addWidget(gk); gl.addStretch(1); gl.addWidget(gv)
        box.addWidget(grand)

        # Paid + remaining.
        pay = QGridLayout(); pay.setHorizontalSpacing(Spacing.XXL); pay.setVerticalSpacing(2)
        pk = QLabel(self._t.gettext("print.paid")); pk.setProperty("p", "total-label")
        pv = QLabel(_money(d.paid) + f" {d.currency}"); pv.setProperty("p", "paid")
        pv.setAlignment(self._end_align())
        rk = QLabel(self._t.gettext("si.remaining")); rk.setProperty("p", "total-label")
        rv = QLabel(_money(d.remaining) + f" {d.currency}")
        rv.setProperty("p", "due" if d.remaining > 0.001 else "paid")
        rv.setAlignment(self._end_align())
        pay.addWidget(pk, 0, 0); pay.addWidget(pv, 0, 1, self._end_align())
        pay.addWidget(rk, 1, 0); pay.addWidget(rv, 1, 1, self._end_align())
        box.addLayout(pay)

        box_w = QWidget(); box_w.setLayout(box); box_w.setFixedWidth(320)
        row.addWidget(box_w)
        return row

    # ---- footer ----------------------------------------------------------

    def _footer(self) -> QWidget:
        wrap = QWidget()
        col = QVBoxLayout(wrap); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(Spacing.MD)
        thin = QFrame(); thin.setProperty("p", "thin"); col.addWidget(thin)

        signs = QHBoxLayout(); signs.setSpacing(Spacing.XXL)
        for key in ("print.prepared_by", "print.customer_sign", "print.authorized_sign"):
            block = QVBoxLayout(); block.setSpacing(4)
            block.addSpacing(Spacing.LG)
            line = QFrame(); line.setProperty("p", "sign"); block.addWidget(line)
            lab = QLabel(self._t.gettext(key)); lab.setProperty("p", "muted")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            block.addWidget(lab)
            holder = QWidget(); holder.setLayout(block)
            signs.addWidget(holder, 1)
        col.addLayout(signs)

        notes = QLabel(f"{self._t.gettext('print.notes')}: {self._t.gettext('print.terms_text')}")
        notes.setProperty("p", "muted"); notes.setWordWrap(True); col.addWidget(notes)

        thanks = QLabel(self._t.gettext("print.thankyou")); thanks.setProperty("p", "thanks")
        thanks.setAlignment(Qt.AlignmentFlag.AlignCenter); col.addWidget(thanks)

        demo = QLabel(self._t.gettext("print.demo_note")); demo.setProperty("p", "muted")
        demo.setAlignment(Qt.AlignmentFlag.AlignCenter); col.addWidget(demo)
        return wrap

    # ---- helpers ---------------------------------------------------------

    def _labelled(self, key: str, prop: str) -> QLabel:
        lab = QLabel(self._t.gettext(key)); lab.setProperty("p", prop); return lab

    def _end_align(self):
        # "End" side: right in LTR, left in RTL — for figures/values.
        if self._t.direction == Direction.RTL:
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
