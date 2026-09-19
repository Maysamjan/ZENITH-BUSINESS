"""Professional printed money vouchers — Receipt / Payment / Expense (Stage 05).

Composed as real business vouchers (not screenshots of the app form), reusing the
LOCKED Stage 01 print design language: the same paper sizes, palette, typography,
company-identity header, accent party bar, strong amount panel, amount-in-words
(English + Dari) and signature blocks as the invoice engine. A voucher is a single
amount on one page, so it composes as a complete document with balanced whitespace
(no huge empty gaps) at A4 and A5, in genuine RTL for Dari.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Direction, Translator
from zenith_business.core.identity import IDENTITY
from zenith_business.core.numbers import amount_in_words
from zenith_business.ui.mock.demo_invoice import CompanyInfo
from zenith_business.ui.print.invoice_document import A4, PaperSize, _money, _stylesheet


@dataclass(frozen=True)
class VoucherData:
    company: CompanyInfo
    title_key: str            # s5.print.receipt_title / payment_title / expense_title
    party_label_key: str      # s5.v_received_from / v_paid_to / v_category
    counter_sign_key: str     # s5.v_received_by / v_paid_by / v_paid_by
    number: str
    date: str
    currency: str
    amount: float
    party_name: str
    party_code: str = ""
    party_phone: str = ""
    account_name: str = ""
    method_label: str = ""
    reference: str = ""
    being: str = ""           # notes / description / payee
    prepared_by: str = ""
    detail_rows: list[tuple[str, str]] = field(default_factory=list)  # (label_key, value)


class VoucherPrintDocument(QWidget):
    """A single-page money voucher composed in the locked print design language."""

    def __init__(self, data: VoucherData, translator: Translator,
                 paper: PaperSize = A4, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._d = data
        self._t = translator
        self._p = paper
        self._rtl = translator.direction == Direction.RTL
        self.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft if self._rtl else Qt.LayoutDirection.LeftToRight)
        self.setStyleSheet(_stylesheet(paper.scale))
        self.setFixedWidth(paper.w)
        stack = QVBoxLayout(self)
        stack.setContentsMargins(0, 0, 0, 0)
        stack.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        stack.addWidget(self._page())

    # ---- alignment helpers ----------------------------------------------

    def _end(self):
        return (Qt.AlignmentFlag.AlignLeft if self._rtl else Qt.AlignmentFlag.AlignRight) \
            | Qt.AlignmentFlag.AlignVCenter

    def _start(self):
        return (Qt.AlignmentFlag.AlignRight if self._rtl else Qt.AlignmentFlag.AlignLeft) \
            | Qt.AlignmentFlag.AlignVCenter

    def _sp(self, base: float) -> int:
        return max(2, int(base * self._p.scale))

    def _logo_widget(self, size: int) -> QLabel:
        """Company logo (defect #6): stored image scaled with aspect ratio kept, or
        the brand letter-mark when no valid logo is configured."""
        lbl = QLabel(); lbl.setFixedSize(size, size)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        path = getattr(self._d.company, "logo_path", "") or ""
        if path:
            from PyQt6.QtGui import QPixmap
            pix = QPixmap(path)
            if not pix.isNull():
                lbl.setPixmap(pix.scaled(
                    size, size, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                lbl.setProperty("p", "logo-img")
                return lbl
        lbl.setText(IDENTITY.product[:1]); lbl.setProperty("p", "logo")
        return lbl

    # ---- page ------------------------------------------------------------

    def _page(self) -> QWidget:
        page = QFrame(); page.setObjectName("Page")
        page.setFixedSize(self._p.w, self._p.h)
        col = QVBoxLayout(page)
        m = self._p.margin
        col.setContentsMargins(m, m, m, m)
        col.setSpacing(self._sp(14 if not self._p.compact else 10))

        col.addWidget(self._header())
        col.addWidget(self._party_bar())
        col.addSpacing(self._sp(6))
        col.addWidget(self._details())
        col.addSpacing(self._sp(10))
        col.addWidget(self._amount_block())
        # Signatures anchor near the bottom (standard voucher composition); a
        # single stretch keeps short vouchers from centering into a mid-page void.
        col.addStretch(1)
        col.addWidget(self._signatures())
        col.addSpacing(self._sp(10))

        foot = QHBoxLayout()
        msg = QLabel(self._t.gettext("print.thankyou")); msg.setProperty("p", "muted")
        foot.addWidget(msg); foot.addStretch(1)
        col.addLayout(foot)
        return page

    def _header(self) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(16)
        left = QHBoxLayout(); left.setSpacing(12)
        size = 64 if not self._p.compact else 44
        logo = self._logo_widget(size)
        left.addWidget(logo, alignment=Qt.AlignmentFlag.AlignTop)
        comp = QVBoxLayout(); comp.setSpacing(2)
        nm = QLabel(self._d.company.name); nm.setProperty("p", "company"); nm.setWordWrap(True)
        comp.addWidget(nm)
        for text in (self._d.company.address, self._d.company.phone,
                     f"{self._t.gettext('print.tax_id')}: {self._d.company.tax_id}"):
            if text and text.strip(":").strip():
                lbl = QLabel(text); lbl.setProperty("p", "muted"); comp.addWidget(lbl)
        left.addLayout(comp)
        row.addLayout(left, 3)
        row.addStretch(1)
        row.addWidget(self._ident_panel(), 2)
        return wrap

    def _ident_panel(self) -> QWidget:
        panel = QFrame(); panel.setProperty("p", "ident")
        panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        v = QVBoxLayout(panel); v.setContentsMargins(14, 10, 14, 10); v.setSpacing(4)
        title = QLabel(self._t.gettext(self._d.title_key)); title.setProperty("p", "title")
        title.setAlignment(self._start()); v.addWidget(title)
        line = QFrame(); line.setProperty("p", "thin"); v.addWidget(line)
        grid = QGridLayout(); grid.setHorizontalSpacing(10); grid.setVerticalSpacing(3)
        grid.setColumnStretch(1, 1)
        pairs = [("si.invoice_no", self._d.number), ("si.date", self._d.date),
                 ("si.currency", self._d.currency)]
        for i, (key, val) in enumerate(pairs):
            k = QLabel(self._t.gettext(key)); k.setProperty("p", "meta-label")
            vv = QLabel(val); vv.setProperty("p", "meta-value" if i else "invno")
            vv.setAlignment(self._end())
            grid.addWidget(k, i, 0, self._start()); grid.addWidget(vv, i, 1, self._end())
        v.addLayout(grid)
        return panel

    def _party_bar(self) -> QWidget:
        bar = QFrame(); bar.setProperty("p", "custbar")
        g = QGridLayout(bar); g.setContentsMargins(12, 8, 12, 8)
        g.setHorizontalSpacing(16); g.setVerticalSpacing(1)
        eb = QLabel(self._t.gettext(self._d.party_label_key)); eb.setProperty("p", "eyebrow")
        nm = QLabel(self._d.party_name or "—"); nm.setProperty("p", "cust-name"); nm.setWordWrap(True)
        g.addWidget(eb, 0, 0); g.addWidget(nm, 1, 0)
        meta = QVBoxLayout(); meta.setSpacing(1)
        for text in ((f"{self._t.gettext('si.phone')}: {self._d.party_phone}"
                      if self._d.party_phone else None),
                     (f"{self._t.gettext('si.customer_code')}: {self._d.party_code}"
                      if self._d.party_code else None)):
            if text:
                lbl = QLabel(text); lbl.setProperty("p", "muted"); meta.addWidget(lbl)
        holder = QWidget(); holder.setLayout(meta)
        g.addWidget(holder, 0, 1, 2, 1, self._end())
        g.setColumnStretch(0, 1)
        return bar

    def _details(self) -> QWidget:
        panel = QFrame(); panel.setProperty("p", "summary")
        v = QVBoxLayout(panel); v.setContentsMargins(14, 10, 14, 10); v.setSpacing(self._sp(5))
        grid = QGridLayout(); grid.setHorizontalSpacing(14); grid.setVerticalSpacing(4)
        grid.setColumnStretch(1, 1)
        rows = [("s5.v_account", self._d.account_name),
                ("s5.v_method", self._d.method_label)]
        rows += list(self._d.detail_rows)
        if self._d.reference:
            rows.append(("s5.v_reference", self._d.reference))
        if self._d.being:
            rows.append(("s5.v_being", self._d.being))
        for r, (key, val) in enumerate(rows):
            k = QLabel(self._t.gettext(key)); k.setProperty("p", "tl")
            vv = QLabel(val or "—"); vv.setProperty("p", "tv"); vv.setWordWrap(True)
            vv.setAlignment(self._end())
            grid.addWidget(k, r, 0, self._start()); grid.addWidget(vv, r, 1, self._end())
        v.addLayout(grid)
        return panel

    def _amount_block(self) -> QWidget:
        wrap = QWidget()
        row = QHBoxLayout(wrap); row.setContentsMargins(0, 0, 0, 0); row.setSpacing(14)
        # amount-in-words (fills width, adds rhythm)
        lang = "fa_AF" if self._rtl else "en"
        words = amount_in_words(self._d.amount, self._d.currency, lang)
        wbar = QFrame(); wbar.setProperty("p", "wordsbar")
        wv = QVBoxLayout(wbar); wv.setContentsMargins(10, 8, 10, 8); wv.setSpacing(1)
        cap = QLabel(self._t.gettext("print.amount_words")); cap.setProperty("p", "words-cap")
        txt = QLabel(words); txt.setProperty("p", "words"); txt.setWordWrap(True)
        wv.addWidget(cap); wv.addWidget(txt)
        row.addWidget(wbar, 3)
        # strong amount panel
        grand = QFrame(); grand.setProperty("p", "grand")
        gv = QVBoxLayout(grand); gv.setContentsMargins(14, 8, 14, 10); gv.setSpacing(1)
        gk = QLabel(self._t.gettext("s5.v_amount")); gk.setProperty("p", "grand-label")
        gk.setAlignment(self._start())
        gvv = QLabel(f"{_money(self._d.amount)} {self._d.currency}")
        gvv.setProperty("p", "grand-value"); gvv.setAlignment(self._end())
        gv.addWidget(gk); gv.addWidget(gvv)
        grand.setMinimumWidth(int((300 if not self._p.compact else 240)))
        row.addWidget(grand, 2)
        return wrap

    def _signatures(self) -> QWidget:
        wrap = QWidget()
        v = QVBoxLayout(wrap); v.setContentsMargins(0, 0, 0, 0); v.setSpacing(self._sp(6))
        keys = [self._d.counter_sign_key, "s5.v_authorized"]
        if not self._p.compact:
            keys = [self._d.counter_sign_key, "s5.v_counterparty", "s5.v_authorized"]
        row = QHBoxLayout(); row.setSpacing(self._sp(26))
        for key in keys:
            block = QVBoxLayout(); block.setSpacing(4); block.addSpacing(self._sp(18))
            line = QFrame(); line.setProperty("p", "signline"); block.addWidget(line)
            lab = QLabel(self._t.gettext(key)); lab.setProperty("p", "sign")
            lab.setAlignment(Qt.AlignmentFlag.AlignCenter); block.addWidget(lab)
            holder = QWidget(); holder.setLayout(block); row.addWidget(holder, 1)
        v.addLayout(row)
        return wrap
