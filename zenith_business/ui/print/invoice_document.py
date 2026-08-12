"""Professionally composed, reflowing printed Sales Invoice (Prompt 01G).

Designed as a customer-facing business document, not just paginated output:
    * A4 and A5 have **genuinely different compositions** (§2) — A4 is spacious
      with a boxed invoice-identity panel and 3 signature columns; A5 is a
      compact composition with an inline identity and 2 signature columns.
    * Collision-proof totals: label and value live in separate grid columns, so
      values from 950 to 12,750,000.00 never overlap or clip (§5).
    * Balanced pagination with widow/orphan control (§6): rows are distributed
      as evenly as possible; the final page keeps a meaningful number of rows
      plus the closing financial section.
    * Short invoices compose as a complete document (§3): totals, amount-in-words,
      notes/terms and signatures give visual rhythm without fake stretching.
    * Amount in words from the real grand total, English + Dari (§10); genuine
      RTL for Dari (§12).

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
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Direction, Translator
from zenith_business.core.identity import IDENTITY
from zenith_business.core.numbers import amount_in_words
from zenith_business.ui.design.tokens import Color, Radius, Typography
from zenith_business.ui.mock.demo_invoice import InvoiceData


def _money(v: float) -> str:
    return f"{v:,.2f}"


@dataclass(frozen=True)
class PaperSize:
    key: str
    w: int
    h: int
    margin: int
    scale: float
    row_h: int
    cap: int        # rows on a non-final page
    reserve: int    # rows of height the closing section needs on the last page
    compact: bool   # A5 uses the compact composition


A4 = PaperSize("A4", 794, 1123, 44, 1.0, 30, 26, 9, False)
A5 = PaperSize("A5", 559, 794, 26, 0.82, 24, 14, 6, True)

PAPERS = {"A4": A4, "A5": A5}


def paginate(n: int, cap: int, reserve: int) -> list[tuple[int, int, bool]]:
    """Distribute ``n`` rows across pages as evenly as possible (§6).

    The last page holds the closing financial section, so it takes at most
    ``cap - reserve`` rows; remaining rows are balanced across pages to avoid a
    nearly-empty final page.
    """
    last_cap = max(1, cap - reserve)
    if n <= last_cap:
        return [(0, n, True)]
    pages_needed = 1
    while (pages_needed - 1) * cap + last_cap < n:
        pages_needed += 1
    base, extra = divmod(n, pages_needed)
    counts = [base + (1 if i < extra else 0) for i in range(pages_needed)]
    # Widow/orphan control: keep the final page within last_cap by shifting
    # rows onto earlier pages that still have room.
    while counts[-1] > last_cap:
        counts[-1] -= 1
        for i in range(pages_needed - 1):
            if counts[i] < cap:
                counts[i] += 1
                break
    slices: list[tuple[int, int, bool]] = []
    start = 0
    for idx, c in enumerate(counts):
        slices.append((start, start + c, idx == pages_needed - 1))
        start += c
    return slices


def _stylesheet(scale: float) -> str:
    c = Color
    # Print-only secondary ink: darker than the on-screen muted gray for better
    # contrast on an ordinary office printer (legibility, not heaviness).
    sec = "#3C4756"

    def s(pt: float) -> str:
        return f"{max(7.0, pt * scale):.1f}pt"

    return f"""
    QWidget#Page {{ background: {c.PRINT_BG}; }}
    QWidget#Page QLabel {{ background: transparent; color: {c.PRINT_INK};
        font-family: {Typography.FAMILY}; font-size: {s(9.5)}; }}
    QWidget#Page QLabel[p="company"] {{ font-size: {s(15)}; font-weight: 700; color: {c.PRINT_INK}; }}
    QWidget#Page QLabel[p="muted"] {{ color: {sec}; font-size: {s(9.2)}; font-weight: 500; }}
    QWidget#Page QLabel[p="title"] {{ font-size: {s(19)}; font-weight: 800; color: {c.PRINT_ACCENT}; letter-spacing: 2px; }}
    QWidget#Page QLabel[p="invno"] {{ font-size: {s(11)}; font-weight: 700; color: {c.PRINT_INK}; }}
    QWidget#Page QLabel[p="run-title"] {{ font-size: {s(11)}; font-weight: 700; color: {c.PRINT_ACCENT}; }}
    QWidget#Page QLabel[p="meta-label"] {{ color: {sec}; font-size: {s(9.0)}; font-weight: 500; }}
    QWidget#Page QLabel[p="meta-value"] {{ color: {c.PRINT_INK}; font-size: {s(9.3)}; font-weight: 700; }}
    QWidget#Page QLabel[p="eyebrow"] {{ color: {c.PRINT_ACCENT}; font-size: {s(8.6)}; font-weight: 700; letter-spacing: 1px; }}
    QWidget#Page QLabel[p="cust-name"] {{ font-size: {s(12.5)}; font-weight: 700; color: {c.PRINT_INK}; }}
    QWidget#Page QLabel[p="tl"] {{ color: {sec}; font-size: {s(9.7)}; font-weight: 500; }}
    QWidget#Page QLabel[p="tv"] {{ color: {c.PRINT_INK}; font-size: {s(9.7)}; font-weight: 700; }}
    QWidget#Page QLabel[p="paid"] {{ color: {c.POSITIVE}; font-size: {s(9.7)}; font-weight: 700; }}
    QWidget#Page QLabel[p="due"] {{ color: {c.NEGATIVE}; font-size: {s(9.7)}; font-weight: 700; }}
    QWidget#Page QLabel[p="words"] {{ color: {c.PRINT_INK}; font-size: {s(10)}; font-weight: 500; }}
    QWidget#Page QLabel[p="words-cap"] {{ color: {c.PRINT_ACCENT}; font-size: {s(8.6)}; font-weight: 700; letter-spacing: 1px; }}
    QWidget#Page QLabel[p="thanks"] {{ color: {c.PRINT_ACCENT}; font-size: {s(11)}; font-weight: 700; }}
    QWidget#Page QLabel[p="pagenum"] {{ color: {sec}; font-size: {s(9.0)}; font-weight: 500; }}
    QWidget#Page QLabel[p="logo"] {{ background: {c.PRINT_ACCENT}; color: #FFFFFF; font-size: {s(22)}; font-weight: 800; border-radius: {Radius.MD}px; }}
    QWidget#Page QLabel[p="grand-label"] {{ color: #FFFFFF; font-size: {s(11.5)}; font-weight: 700; }}
    QWidget#Page QLabel[p="grand-value"] {{ color: #FFFFFF; font-size: {s(14)}; font-weight: 800; }}
    QWidget#Page QLabel[p="notes-label"] {{ color: {c.PRINT_ACCENT}; font-size: {s(8.6)}; font-weight: 700; letter-spacing: 1px; }}
    QWidget#Page QLabel[p="notes"] {{ color: {sec}; font-size: {s(9.2)}; font-weight: 500; }}
    QWidget#Page QLabel[p="sign"] {{ color: {c.PRINT_INK}; font-size: {s(9.4)}; font-weight: 600; }}

    QWidget#Page QFrame[p="titlebar"] {{ background: {c.PRINT_ACCENT}; border: none; }}
    QWidget#Page QFrame[p="ident"] {{ background: {c.PRINT_ACCENT_SOFT}; border: 1px solid {c.PRINT_RULE}; border-radius: {Radius.MD}px; }}
    QWidget#Page QFrame[p="custbar"] {{ background: {c.PRINT_ACCENT_SOFT}; border-left: 3px solid {c.PRINT_ACCENT}; }}
    QWidget#Page QFrame[p="summary"] {{ background: {c.PRINT_BG}; border: 1px solid {c.PRINT_RULE}; border-radius: {Radius.MD}px; }}
    QWidget#Page QFrame[p="grand"] {{ background: {c.PRINT_ACCENT}; border: none; }}
    QWidget#Page QFrame[p="wordsbar"] {{ background: {c.PRINT_ACCENT_SOFT}; border-left: 3px solid {c.PRINT_ACCENT}; border-radius: {Radius.SM}px; }}
    QWidget#Page QFrame[p="thin"] {{ background: {c.PRINT_RULE}; max-height: 1px; min-height: 1px; border: none; }}
    QWidget#Page QFrame[p="signline"] {{ background: {c.PRINT_MUTED}; max-height: 1px; min-height: 1px; }}

    QWidget#Page QTableWidget {{ background: {c.PRINT_BG}; border: none; gridline-color: transparent;
        font-size: {s(9.3)}; color: {c.PRINT_INK}; }}
    QWidget#Page QTableWidget::item {{ border-bottom: 1px solid {c.PRINT_RULE}; padding: 2px 6px; }}
    QWidget#Page QHeaderView::section {{ background: {c.PRINT_ACCENT}; color: #FFFFFF;
        border: none; padding: 5px 6px; font-weight: 700; font-size: {s(9)}; }}
    """


class InvoicePrintDocument(QWidget):
    """Stacked paper pages with a professional, reflowing composition."""

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
        self._p = paper
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

        pages = paginate(len(data.lines), paper.cap, paper.reserve)
        for idx, (start, end, is_last) in enumerate(pages):
            stack.addWidget(self._page(start, end, is_last, idx + 1, len(pages)))

    # ---- page assembly ---------------------------------------------------

    def _sp(self, base: float) -> int:
        return max(2, int(base * self._p.scale))

    def _page(self, start: int, end: int, is_last: bool, no: int, total: int) -> QWidget:
        page = QFrame(); page.setObjectName("Page")
        page.setFixedSize(self._p.w, self._p.h)
        col = QVBoxLayout(page)
        m = self._p.margin
        col.setContentsMargins(m, m, m, m)
        col.setSpacing(self._sp(12 if not self._p.compact else 8))

        if no == 1:
            col.addWidget(self._header())
            col.addWidget(self._customer())
        else:
            col.addWidget(self._running_header())

        col.addWidget(self._table(start, end))

        if is_last:
            # Balance the closing block vertically in the leftover space so short
            # invoices read as a complete, composed document (§3) — symmetric
            # whitespace above and below, not everything crammed at the top.
            col.addStretch(1)
            col.addWidget(self._closing_section())
            col.addSpacing(self._sp(18))
            col.addWidget(self._signatures())
            col.addStretch(1)
        else:
            col.addStretch(1)

        foot = QHBoxLayout()
        msg = QLabel(self._t.gettext("print.thankyou")) if is_last else QLabel(self._d.company.name)
        msg.setProperty("p", "muted")
        pn = QLabel(f"{no} / {total}"); pn.setProperty("p", "pagenum")
        foot.addWidget(msg); foot.addStretch(1); foot.addWidget(pn)
        col.addLayout(foot)
        return page

    # ---- header (A4 spacious vs A5 compact) ------------------------------

    def _identity_lines(self) -> list[str]:
        c = self._d.company
        return [c.address, c.phone,
                f"{self._t.gettext('print.email')}: {c.email}",
                f"{self._t.gettext('print.tax_id')}: {c.tax_id}"]

    def _header(self) -> QWidget:
        if self._p.compact:
            return self._header_compact()
        return self._header_spacious()

    def _header_spacious(self) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(16)
        # Company identity block.
        left = QHBoxLayout(); left.setSpacing(12)
        logo = QLabel(IDENTITY.product[:1]); logo.setProperty("p", "logo")
        logo.setFixedSize(64, 64); logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.addWidget(logo, alignment=Qt.AlignmentFlag.AlignTop)
        comp = QVBoxLayout(); comp.setSpacing(2)
        nm = QLabel(self._d.company.name); nm.setProperty("p", "company"); nm.setWordWrap(True)
        comp.addWidget(nm)
        for text in self._identity_lines():
            l = QLabel(text); l.setProperty("p", "muted"); comp.addWidget(l)
        left.addLayout(comp)
        row.addLayout(left, 3)
        row.addStretch(1)
        # Boxed invoice-identity panel.
        row.addWidget(self._ident_panel(), 2)
        return wrap

    def _ident_panel(self) -> QWidget:
        panel = QFrame(); panel.setProperty("p", "ident")
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        v = QVBoxLayout(panel); v.setContentsMargins(14, 10, 14, 10); v.setSpacing(4)
        title = QLabel(self._t.gettext("print.title")); title.setProperty("p", "title")
        title.setAlignment(self._start())
        v.addWidget(title)
        line = QFrame(); line.setProperty("p", "thin"); v.addWidget(line)
        grid = QGridLayout(); grid.setHorizontalSpacing(10); grid.setVerticalSpacing(3)
        grid.setColumnStretch(1, 1)
        for i, (key, val) in enumerate([
            ("si.invoice_no", self._d.number), ("si.date", self._d.date),
            ("si.salesperson", self._d.salesperson), ("si.currency", self._d.currency),
        ]):
            k = QLabel(self._t.gettext(key)); k.setProperty("p", "meta-label")
            vv = QLabel(val); vv.setProperty("p", "meta-value" if i else "invno")
            vv.setAlignment(self._end())
            grid.addWidget(k, i, 0, self._start())
            grid.addWidget(vv, i, 1, self._end())
        v.addLayout(grid)
        return panel

    def _header_compact(self) -> QWidget:
        wrap = QWidget()
        top = QVBoxLayout(wrap); top.setContentsMargins(0, 0, 0, 0); top.setSpacing(3)
        row = QHBoxLayout(); row.setSpacing(8)
        logo = QLabel(IDENTITY.product[:1]); logo.setProperty("p", "logo")
        logo.setFixedSize(40, 40); logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(logo, alignment=Qt.AlignmentFlag.AlignVCenter)
        nm = QLabel(self._d.company.name); nm.setProperty("p", "company"); nm.setWordWrap(True)
        row.addWidget(nm, 1, Qt.AlignmentFlag.AlignVCenter)
        ident = QVBoxLayout(); ident.setSpacing(0)
        title = QLabel(self._t.gettext("print.title")); title.setProperty("p", "title")
        title.setAlignment(self._end())
        no = QLabel(f"{self._d.number} · {self._d.date}"); no.setProperty("p", "meta-value")
        no.setAlignment(self._end())
        ident.addWidget(title); ident.addWidget(no)
        row.addLayout(ident)
        top.addLayout(row)
        contact = QLabel(" · ".join([self._d.company.address, self._d.company.phone,
                                     self._d.company.tax_id]))
        contact.setProperty("p", "muted"); top.addWidget(contact)
        rule = QFrame(); rule.setProperty("p", "thin"); top.addWidget(rule)
        return wrap

    def _running_header(self) -> QWidget:
        wrap = QWidget()
        v = QVBoxLayout(wrap); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(3)
        row = QHBoxLayout()
        nm = QLabel(self._d.company.name); nm.setProperty("p", "run-title")
        info = QLabel(f"{self._t.gettext('print.title')} · {self._d.number}")
        info.setProperty("p", "meta-value")
        row.addWidget(nm); row.addStretch(1); row.addWidget(info)
        v.addLayout(row)
        rule = QFrame(); rule.setProperty("p", "thin"); v.addWidget(rule)
        return wrap

    # ---- customer --------------------------------------------------------

    def _customer(self) -> QWidget:
        d = self._d
        bar = QFrame(); bar.setProperty("p", "custbar")
        if self._p.compact:
            h = QHBoxLayout(bar); h.setContentsMargins(10, 6, 10, 6); h.setSpacing(10)
            eb = QLabel(self._t.gettext("print.bill_to")); eb.setProperty("p", "eyebrow")
            nm = QLabel(d.customer_name); nm.setProperty("p", "cust-name")
            info = QLabel(f"{d.customer_phone} · {d.customer_code}"); info.setProperty("p", "muted")
            h.addWidget(eb); h.addWidget(nm); h.addStretch(1); h.addWidget(info)
        else:
            g = QGridLayout(bar); g.setContentsMargins(12, 8, 12, 8); g.setHorizontalSpacing(16); g.setVerticalSpacing(1)
            eb = QLabel(self._t.gettext("print.bill_to")); eb.setProperty("p", "eyebrow")
            nm = QLabel(d.customer_name); nm.setProperty("p", "cust-name"); nm.setWordWrap(True)
            g.addWidget(eb, 0, 0); g.addWidget(nm, 1, 0)
            meta = QVBoxLayout(); meta.setSpacing(1)
            for text in (f"{self._t.gettext('si.phone')}: {d.customer_phone}",
                         f"{self._t.gettext('si.address')}: {d.customer_address}",
                         f"{self._t.gettext('si.customer_code')}: {d.customer_code}"):
                l = QLabel(text); l.setProperty("p", "muted"); meta.addWidget(l)
            holder = QWidget(); holder.setLayout(meta)
            g.addWidget(holder, 0, 1, 2, 1, self._end())
            g.setColumnStretch(0, 1)
        return bar

    # ---- items table -----------------------------------------------------

    def _table(self, start: int, end: int) -> QWidget:
        headers = ["si.col_row", "print.col_item", "si.col_qty", "si.col_unit",
                   "si.col_price", "si.col_discount", "si.col_total"]
        rows = self._d.lines[start:end]
        table = QTableWidget(len(rows), len(headers))
        table.setHorizontalHeaderLabels([self._t.gettext(k) for k in headers])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setShowGrid(False)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.verticalHeader().setDefaultSectionSize(self._p.row_h)

        header = table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setHighlightSections(False)
        sc = self._p.scale
        # Numeric columns are sized to hold large values without truncation (§5).
        widths = ({0: 34, 2: 62, 3: 58, 4: 104, 5: 92, 6: 128} if not self._p.compact
                  else {0: 26, 2: 54, 3: 42, 4: 82, 5: 82, 6: 114})
        for cidx, w in widths.items():
            header.setSectionResizeMode(cidx, QHeaderView.ResizeMode.Fixed)
            table.setColumnWidth(cidx, w)

        numeric = {2, 4, 5, 6}
        for r, line in enumerate(rows):
            values = [str(start + r + 1), line.name, f"{line.qty:,.0f}", line.unit,
                      _money(line.price), _money(line.discount), _money(line.total)]
            for cidx, text in enumerate(values):
                item = QTableWidgetItem(text)
                align = Qt.AlignmentFlag.AlignRight if cidx in numeric else Qt.AlignmentFlag.AlignLeft
                item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(r, cidx, item)
        header_h = int(32 * sc)
        table.setFixedHeight(header_h + len(rows) * self._p.row_h + 6)
        return table

    # ---- closing financial section (collision-proof) --------------------

    def _closing_section(self) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(14)
        # Left: amount in words + notes (fills the width, adds rhythm).
        left = QVBoxLayout(); left.setSpacing(self._sp(8))
        left.addWidget(self._amount_words())
        left.addWidget(self._notes())
        left.addStretch(1)
        row.addLayout(left, 3)
        # Right: coherent financial summary panel.
        row.addWidget(self._summary(), 2)
        return wrap

    def _summary(self) -> QWidget:
        d = self._d
        panel = QFrame(); panel.setProperty("p", "summary")
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        panel.setMinimumWidth(int((320 if not self._p.compact else 250) * 1))
        v = QVBoxLayout(panel); v.setContentsMargins(14, 10, 14, 10); v.setSpacing(self._sp(5))

        grid = QGridLayout(); grid.setHorizontalSpacing(12); grid.setVerticalSpacing(3)
        grid.setColumnStretch(1, 1)
        pairs = [("si.subtotal", _money(d.subtotal)), ("si.discount", _money(d.discount_total))]
        if d.tax or d.additional:
            pairs.append(("si.tax", _money(d.tax + d.additional)))
        r = 0
        for key, val in pairs:
            k = QLabel(self._t.gettext(key)); k.setProperty("p", "tl")
            vv = QLabel(f"{val} {d.currency}"); vv.setProperty("p", "tv"); vv.setAlignment(self._end())
            grid.addWidget(k, r, 0, self._start()); grid.addWidget(vv, r, 1, self._end())
            r += 1
        v.addLayout(grid)

        thin = QFrame(); thin.setProperty("p", "thin"); v.addWidget(thin)

        # Grand total — label stacked above value so ANY magnitude fits without
        # collision or clipping (§5), e.g. 950 … 12,750,000.00.
        grand = QFrame(); grand.setProperty("p", "grand")
        gv_box = QVBoxLayout(grand); gv_box.setContentsMargins(12, 6, 12, 8); gv_box.setSpacing(1)
        gk = QLabel(self._t.gettext("si.grand_total")); gk.setProperty("p", "grand-label")
        gk.setAlignment(self._start())
        gv = QLabel(f"{_money(d.grand_total)} {d.currency}"); gv.setProperty("p", "grand-value")
        gv.setAlignment(self._end())
        gv_box.addWidget(gk); gv_box.addWidget(gv)
        v.addWidget(grand)

        pay = QGridLayout(); pay.setHorizontalSpacing(12); pay.setVerticalSpacing(3)
        pay.setColumnStretch(1, 1)
        pk = QLabel(self._t.gettext("print.paid")); pk.setProperty("p", "tl")
        pv = QLabel(f"{_money(d.paid)} {d.currency}"); pv.setProperty("p", "paid"); pv.setAlignment(self._end())
        rk = QLabel(self._t.gettext("si.remaining")); rk.setProperty("p", "tl")
        rv = QLabel(f"{_money(d.remaining)} {d.currency}")
        rv.setProperty("p", "due" if d.remaining > 0.001 else "paid"); rv.setAlignment(self._end())
        pay.addWidget(pk, 0, 0, self._start()); pay.addWidget(pv, 0, 1, self._end())
        pay.addWidget(rk, 1, 0, self._start()); pay.addWidget(rv, 1, 1, self._end())
        v.addLayout(pay)
        return panel

    def _amount_words(self) -> QWidget:
        lang = "fa_AF" if self._rtl else "en"
        words = amount_in_words(self._d.grand_total, self._d.currency, lang)
        bar = QFrame(); bar.setProperty("p", "wordsbar")
        v = QVBoxLayout(bar); v.setContentsMargins(10, 6, 10, 6); v.setSpacing(1)
        cap = QLabel(self._t.gettext("print.amount_words")); cap.setProperty("p", "words-cap")
        txt = QLabel(words); txt.setProperty("p", "words"); txt.setWordWrap(True)
        v.addWidget(cap); v.addWidget(txt)
        return bar

    def _notes(self) -> QWidget:
        bar = QWidget()
        v = QVBoxLayout(bar); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(1)
        cap = QLabel(self._t.gettext("print.notes")); cap.setProperty("p", "notes-label")
        txt = QLabel(self._t.gettext("print.terms_text")); txt.setProperty("p", "notes"); txt.setWordWrap(True)
        v.addWidget(cap); v.addWidget(txt)
        return bar

    # ---- signatures ------------------------------------------------------

    def _signatures(self) -> QWidget:
        wrap = QWidget()
        v = QVBoxLayout(wrap); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(self._sp(6))
        keys = (["print.prepared_by", "print.customer_sign", "print.authorized_sign"]
                if not self._p.compact else ["print.customer_sign", "print.authorized_sign"])
        row = QHBoxLayout(); row.setSpacing(self._sp(26))
        for key in keys:
            block = QVBoxLayout(); block.setSpacing(4); block.addSpacing(self._sp(18))
            line = QFrame(); line.setProperty("p", "signline"); block.addWidget(line)
            lab = QLabel(self._t.gettext(key)); lab.setProperty("p", "sign")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter); block.addWidget(lab)
            holder = QWidget(); holder.setLayout(block); row.addWidget(holder, 1)
        v.addLayout(row)
        return wrap

    # ---- alignment helpers (direction-aware) -----------------------------

    def _end(self):
        return (Qt.AlignmentFlag.AlignLeft if self._rtl else Qt.AlignmentFlag.AlignRight) | Qt.AlignmentFlag.AlignVCenter

    def _start(self):
        return (Qt.AlignmentFlag.AlignRight if self._rtl else Qt.AlignmentFlag.AlignLeft) | Qt.AlignmentFlag.AlignVCenter


class A4InvoiceDocument(InvoicePrintDocument):
    """Backward-compatible A4 document."""

    WIDTH = A4.w
    HEIGHT = A4.h

    def __init__(self, data: InvoiceData, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(data, translator, A4, parent)
