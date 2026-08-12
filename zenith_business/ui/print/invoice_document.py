"""Paginated printed Sales Invoice engine (Prompt 01F §6-§10).

A genuine content-reflowing print layout — not a fixed screenshot:
    * A4 and A5 paper sizes, each with its own typography/spacing/density (§6).
    * The document reflows to the number of items (§7): short invoices compose
      compactly (no half-page gap); long invoices continue onto more pages with
      repeated document + table headers, page numbers, and totals kept on the
      final page (§7, §8).
    * Amount in words from the actual grand total, English + Dari (§10).
    * Ink-friendly (white page, restrained navy accents; clear in grayscale).
    * Real RTL for Dari (§12).

Driven by the shared demo transaction so screen and print match (§11).
"""

from __future__ import annotations

from dataclasses import dataclass

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
from zenith_business.core.numbers import amount_in_words
from zenith_business.ui.design.tokens import Color, Radius
from zenith_business.ui.mock.demo_invoice import InvoiceData


def _money(v: float) -> str:
    return f"{v:,.2f}"


@dataclass(frozen=True)
class PaperSize:
    """A print paper preset with its own density (§6)."""

    key: str
    w: int
    h: int
    margin: int
    scale: float        # font scale relative to A4
    row_h: int
    rows_per_page: int  # capacity of a non-final page
    last_reserve: int   # rows of space the totals/footer consume on the last page


A4 = PaperSize("A4", 794, 1123, 40, 1.0, 30, 24, 10)
A5 = PaperSize("A5", 559, 794, 26, 0.84, 25, 12, 6)

PAPERS = {"A4": A4, "A5": A5}


def paginate(n: int, cap: int, reserve: int) -> list[tuple[int, int, bool]]:
    """Return (start, end, is_last) slices so totals/footer fit on the last page."""
    last_cap = max(1, cap - reserve)
    if n <= last_cap:
        return [(0, n, True)]
    pages: list[tuple[int, int, bool]] = []
    i = 0
    while True:
        remaining = n - i
        if remaining <= last_cap:
            pages.append((i, n, True))
            break
        take = min(cap, remaining - 1)  # leave >=1 row for the final page
        pages.append((i, i + take, False))
        i += take
    return pages


def _stylesheet(scale: float) -> str:
    c = Color

    def s(pt: float) -> str:
        return f"{max(7.5, pt * scale):.1f}pt"

    return f"""
    QWidget#Page {{ background: {c.PRINT_BG}; }}
    QWidget#Page QLabel {{ background: transparent; color: {c.PRINT_INK};
        font-family: "Segoe UI","Tahoma","Noto Naskh Arabic",sans-serif; font-size: {s(9.5)}; }}
    QWidget#Page QLabel[p="company"] {{ font-size: {s(14)}; font-weight: 700; color: {c.PRINT_ACCENT}; }}
    QWidget#Page QLabel[p="muted"] {{ color: {c.PRINT_MUTED}; font-size: {s(9)}; }}
    QWidget#Page QLabel[p="title"] {{ font-size: {s(21)}; font-weight: 700; color: {c.PRINT_ACCENT}; letter-spacing: 1px; }}
    QWidget#Page QLabel[p="run-title"] {{ font-size: {s(12)}; font-weight: 700; color: {c.PRINT_ACCENT}; }}
    QWidget#Page QLabel[p="meta-label"] {{ color: {c.PRINT_MUTED}; font-size: {s(9)}; }}
    QWidget#Page QLabel[p="meta-value"] {{ color: {c.PRINT_INK}; font-size: {s(9.5)}; font-weight: 500; }}
    QWidget#Page QLabel[p="section"] {{ color: {c.PRINT_ACCENT}; font-size: {s(10)}; font-weight: 600; }}
    QWidget#Page QLabel[p="cust-name"] {{ font-size: {s(12)}; font-weight: 600; }}
    QWidget#Page QLabel[p="total-label"] {{ color: {c.PRINT_MUTED}; font-size: {s(10)}; }}
    QWidget#Page QLabel[p="total-value"] {{ color: {c.PRINT_INK}; font-size: {s(10)}; font-weight: 500; }}
    QWidget#Page QLabel[p="paid"] {{ color: {c.POSITIVE}; font-weight: 600; }}
    QWidget#Page QLabel[p="due"] {{ color: {c.NEGATIVE}; font-weight: 700; }}
    QWidget#Page QLabel[p="words"] {{ color: {c.PRINT_INK}; font-size: {s(9.5)}; font-style: italic; }}
    QWidget#Page QLabel[p="thanks"] {{ color: {c.PRINT_ACCENT}; font-size: {s(11)}; font-weight: 600; }}
    QWidget#Page QLabel[p="pagenum"] {{ color: {c.PRINT_MUTED}; font-size: {s(8.5)}; }}
    QWidget#Page QLabel[p="logo"] {{ background: {c.PRINT_ACCENT}; color: #FFFFFF; font-size: {s(20)}; font-weight: 700; border-radius: {Radius.MD}px; }}
    QWidget#Page QFrame[p="rule"] {{ background: {c.PRINT_ACCENT}; max-height: 3px; min-height: 3px; border: none; }}
    QWidget#Page QFrame[p="thin"] {{ background: {c.PRINT_RULE}; max-height: 1px; min-height: 1px; border: none; }}
    QWidget#Page QFrame[p="grand"] {{ background: {c.PRINT_ACCENT}; border-radius: {Radius.MD}px; }}
    QWidget#Page QLabel[p="grand-label"] {{ color: #FFFFFF; font-size: {s(12)}; font-weight: 600; }}
    QWidget#Page QLabel[p="grand-value"] {{ color: #FFFFFF; font-size: {s(15)}; font-weight: 700; }}
    QWidget#Page QFrame[p="sign"] {{ background: {c.PRINT_RULE}; max-height: 1px; min-height: 1px; }}
    QWidget#Page QTableWidget {{ background: {c.PRINT_BG}; border: 1px solid {c.PRINT_RULE}; gridline-color: {c.PRINT_RULE}; font-size: {s(9.5)}; color: {c.PRINT_INK}; }}
    QWidget#Page QHeaderView::section {{ background: {c.PRINT_ACCENT_SOFT}; color: {c.PRINT_ACCENT}; border: none; border-bottom: 1px solid {c.PRINT_RULE}; padding: 4px 6px; font-weight: 600; font-size: {s(9)}; }}
    """


class InvoicePrintDocument(QWidget):
    """A stack of paper pages that reflows to the invoice's item count."""

    def __init__(
        self,
        data: InvoiceData,
        translator: Translator,
        paper: PaperSize = A4,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._d = data
        self._t = translator
        self._paper = paper
        self._rtl = translator.direction == Direction.RTL
        self.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft if self._rtl else Qt.LayoutDirection.LeftToRight
        )
        self.setStyleSheet(_stylesheet(paper.scale))
        self.setFixedWidth(paper.w)

        stack = QVBoxLayout(self)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setSpacing(18)
        stack.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        pages = paginate(len(data.lines), paper.rows_per_page, paper.last_reserve)
        total = len(pages)
        for idx, (start, end, is_last) in enumerate(pages):
            stack.addWidget(self._build_page(start, end, is_last, idx + 1, total))

    # ---- page ------------------------------------------------------------

    def _build_page(self, start: int, end: int, is_last: bool, page_no: int, total: int) -> QWidget:
        page = QFrame()
        page.setObjectName("Page")
        page.setFixedSize(self._paper.w, self._paper.h)
        col = QVBoxLayout(page)
        m = self._paper.margin
        col.setContentsMargins(m, m, m, m)
        col.setSpacing(int(12 * self._paper.scale))

        if page_no == 1:
            col.addLayout(self._full_header())
            rule = QFrame(); rule.setProperty("p", "rule"); col.addWidget(rule)
            col.addLayout(self._bill_to())
        else:
            col.addLayout(self._running_header(page_no, total))
            rule = QFrame(); rule.setProperty("p", "rule"); col.addWidget(rule)

        col.addWidget(self._items_table(start, end))

        if is_last:
            # Compact composition (§7): items → totals → words → footer stacked,
            # with the remaining whitespace at the very bottom of the page — no
            # absurd half-page gap for short invoices.
            col.addSpacing(int(8 * self._paper.scale))
            col.addLayout(self._summary())
            col.addSpacing(int(6 * self._paper.scale))
            col.addWidget(self._amount_words())
            col.addSpacing(int(12 * self._paper.scale))
            col.addWidget(self._footer())
            col.addStretch(1)
        else:
            col.addStretch(1)

        pn = QLabel(f"{page_no} / {total}"); pn.setProperty("p", "pagenum")
        pn.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(pn)
        return page

    # ---- headers ---------------------------------------------------------

    def _full_header(self):
        row = QHBoxLayout(); row.setSpacing(16)
        left = QHBoxLayout(); left.setSpacing(10)
        size = int(60 * self._paper.scale)
        logo = QLabel(IDENTITY.product[:1]); logo.setProperty("p", "logo")
        logo.setFixedSize(size, size); logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.addWidget(logo)
        comp = QVBoxLayout(); comp.setSpacing(1)
        c = self._d.company
        nm = QLabel(c.name); nm.setProperty("p", "company"); comp.addWidget(nm)
        for text in (c.address, c.phone,
                     f"{self._t.gettext('print.email')}: {c.email}",
                     f"{self._t.gettext('print.tax_id')}: {c.tax_id}"):
            l = QLabel(text); l.setProperty("p", "muted"); comp.addWidget(l)
        left.addLayout(comp)
        row.addLayout(left)
        row.addStretch(1)

        right = QVBoxLayout(); right.setSpacing(2)
        title = QLabel(self._t.gettext("print.title")); title.setProperty("p", "title")
        title.setAlignment(self._end())
        right.addWidget(title)
        ident = QGridLayout(); ident.setHorizontalSpacing(12); ident.setVerticalSpacing(1)
        for i, (key, val) in enumerate([
            ("si.invoice_no", self._d.number), ("si.date", self._d.date),
            ("si.salesperson", self._d.salesperson), ("si.currency", self._d.currency),
        ]):
            k = QLabel(self._t.gettext(key)); k.setProperty("p", "meta-label")
            v = QLabel(val); v.setProperty("p", "meta-value"); v.setAlignment(self._end())
            ident.addWidget(k, i, 0); ident.addWidget(v, i, 1, self._end())
        right.addLayout(ident)
        row.addLayout(right)
        return row

    def _running_header(self, page_no: int, total: int):
        row = QHBoxLayout()
        nm = QLabel(self._d.company.name); nm.setProperty("p", "run-title")
        row.addWidget(nm); row.addStretch(1)
        info = QLabel(f"{self._t.gettext('print.title')} · {self._d.number}")
        info.setProperty("p", "meta-value")
        row.addWidget(info)
        return row

    def _bill_to(self):
        row = QHBoxLayout()
        col = QVBoxLayout(); col.setSpacing(1)
        s = QLabel(self._t.gettext("print.bill_to")); s.setProperty("p", "section")
        col.addWidget(s)
        d = self._d
        nm = QLabel(d.customer_name); nm.setProperty("p", "cust-name"); col.addWidget(nm)
        for text in (f"{self._t.gettext('si.phone')}: {d.customer_phone}",
                     f"{self._t.gettext('si.address')}: {d.customer_address}",
                     f"{self._t.gettext('si.customer_code')}: {d.customer_code}"):
            l = QLabel(text); l.setProperty("p", "muted"); col.addWidget(l)
        row.addLayout(col); row.addStretch(1)
        return row

    # ---- items -----------------------------------------------------------

    def _items_table(self, start: int, end: int) -> QWidget:
        headers = ["si.col_row", "print.col_item", "si.col_qty", "si.col_unit",
                   "si.col_price", "si.col_discount", "si.col_total"]
        rows = self._d.lines[start:end]
        table = QTableWidget(len(rows), len(headers))
        table.setHorizontalHeaderLabels([self._t.gettext(k) for k in headers])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.verticalHeader().setDefaultSectionSize(self._paper.row_h)

        header = table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setHighlightSections(False)
        sc = self._paper.scale
        widths = {0: int(34 * sc), 2: int(60 * sc), 3: int(56 * sc),
                  4: int(96 * sc), 5: int(84 * sc), 6: int(112 * sc)}
        for col, w in widths.items():
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(col, w)

        numeric = {2, 4, 5, 6}
        for r, line in enumerate(rows):
            values = [str(start + r + 1), line.name, f"{line.qty:,.0f}", line.unit,
                      _money(line.price), _money(line.discount), _money(line.total)]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                align = Qt.AlignmentFlag.AlignRight if col in numeric else Qt.AlignmentFlag.AlignLeft
                item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(r, col, item)
        header_h = int(34 * sc)
        table.setFixedHeight(header_h + len(rows) * self._paper.row_h + 8)
        return table

    # ---- summary + words + footer ---------------------------------------

    def _summary(self):
        row = QHBoxLayout(); row.addStretch(1)
        box = QVBoxLayout(); box.setSpacing(int(6 * self._paper.scale))
        grid = QGridLayout(); grid.setHorizontalSpacing(int(28 * self._paper.scale)); grid.setVerticalSpacing(2)
        d = self._d
        pairs = [("si.subtotal", _money(d.subtotal)), ("si.discount", _money(d.discount_total))]
        if d.tax or d.additional:
            pairs.append(("si.tax", _money(d.tax + d.additional)))
        for i, (key, val) in enumerate(pairs):
            k = QLabel(self._t.gettext(key)); k.setProperty("p", "total-label")
            v = QLabel(f"{val} {d.currency}"); v.setProperty("p", "total-value"); v.setAlignment(self._end())
            grid.addWidget(k, i, 0); grid.addWidget(v, i, 1, self._end())
        box.addLayout(grid)

        grand = QFrame(); grand.setProperty("p", "grand")
        gl = QHBoxLayout(grand); gl.setContentsMargins(12, 6, 12, 6)
        gk = QLabel(self._t.gettext("si.grand_total")); gk.setProperty("p", "grand-label")
        gv = QLabel(f"{_money(d.grand_total)} {d.currency}"); gv.setProperty("p", "grand-value"); gv.setAlignment(self._end())
        gl.addWidget(gk); gl.addStretch(1); gl.addWidget(gv)
        box.addWidget(grand)

        pay = QGridLayout(); pay.setHorizontalSpacing(int(28 * self._paper.scale)); pay.setVerticalSpacing(2)
        pk = QLabel(self._t.gettext("print.paid")); pk.setProperty("p", "total-label")
        pv = QLabel(f"{_money(d.paid)} {d.currency}"); pv.setProperty("p", "paid"); pv.setAlignment(self._end())
        rk = QLabel(self._t.gettext("si.remaining")); rk.setProperty("p", "total-label")
        rv = QLabel(f"{_money(d.remaining)} {d.currency}")
        rv.setProperty("p", "due" if d.remaining > 0.001 else "paid"); rv.setAlignment(self._end())
        pay.addWidget(pk, 0, 0); pay.addWidget(pv, 0, 1, self._end())
        pay.addWidget(rk, 1, 0); pay.addWidget(rv, 1, 1, self._end())
        box.addLayout(pay)

        holder = QWidget(); holder.setLayout(box); holder.setFixedWidth(int(360 * self._paper.scale))
        row.addWidget(holder)
        return row

    def _amount_words(self) -> QWidget:
        lang = "fa_AF" if self._rtl else "en"
        words = amount_in_words(self._d.grand_total, self._d.currency, lang)
        lbl = QLabel(f"★ {words}"); lbl.setProperty("p", "words"); lbl.setWordWrap(True)
        return lbl

    def _footer(self) -> QWidget:
        wrap = QWidget()
        col = QVBoxLayout(wrap); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(int(10 * self._paper.scale))
        thin = QFrame(); thin.setProperty("p", "thin"); col.addWidget(thin)
        signs = QHBoxLayout(); signs.setSpacing(int(28 * self._paper.scale))
        for key in ("print.prepared_by", "print.customer_sign", "print.authorized_sign"):
            block = QVBoxLayout(); block.setSpacing(3); block.addSpacing(int(16 * self._paper.scale))
            line = QFrame(); line.setProperty("p", "sign"); block.addWidget(line)
            lab = QLabel(self._t.gettext(key)); lab.setProperty("p", "muted")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter); block.addWidget(lab)
            holder = QWidget(); holder.setLayout(block); signs.addWidget(holder, 1)
        col.addLayout(signs)
        notes = QLabel(f"{self._t.gettext('print.notes')}: {self._t.gettext('print.terms_text')}")
        notes.setProperty("p", "muted"); notes.setWordWrap(True); col.addWidget(notes)
        thanks = QLabel(self._t.gettext("print.thankyou")); thanks.setProperty("p", "thanks")
        thanks.setAlignment(Qt.AlignmentFlag.AlignCenter); col.addWidget(thanks)
        return wrap

    def _end(self):
        return (Qt.AlignmentFlag.AlignLeft if self._rtl else Qt.AlignmentFlag.AlignRight) | Qt.AlignmentFlag.AlignVCenter


class A4InvoiceDocument(InvoicePrintDocument):
    """Backward-compatible single-format A4 document."""

    WIDTH = A4.w
    HEIGHT = A4.h

    def __init__(self, data: InvoiceData, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(data, translator, A4, parent)
