"""Printed Sales Report document (Stage 05 final).

A customer-facing accounting report on the SAME print standard as the invoice and
voucher documents (A4/A5 paper, English/Dari, genuine RTL). The header carries
the CUSTOMER's own business identity (logo / name / address / phone) taken from
Company settings — never the Zenith Soft developer identity — because this is the
owner's report about their own sales.

Rendered as a single grow-with-content sheet and grabbed to a pixmap by the
preview workspace, exactly like the money voucher.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
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
from zenith_business.core.money import format_money
from zenith_business.ui.design.tokens import Color, Radius, Typography
from zenith_business.ui.print.invoice_document import PAPERS, PaperSize


@dataclass(frozen=True)
class ReportCompany:
    name: str
    address: str
    phone: str
    email: str
    logo_path: str


@dataclass(frozen=True)
class SalesReportPrintData:
    company: ReportCompany
    date_from: str
    date_to: str
    summary: dict
    rows: list[dict]     # detail rows (document_no/date/party/walkin/gross/paid/credit/returned/net)


def _stylesheet(scale: float) -> str:
    c = Color
    sec = "#3C4756"

    def s(pt: float) -> str:
        return f"{max(7.0, pt * scale):.1f}pt"

    return f"""
    QWidget#Page {{ background: {c.PRINT_BG}; }}
    QWidget#Page QLabel {{ background: transparent; color: {c.PRINT_INK};
        font-family: {Typography.FAMILY}; font-size: {s(9.5)}; }}
    QWidget#Page QLabel[p="company"] {{ font-size: {s(16)}; font-weight: 800; color: {c.PRINT_INK}; }}
    QWidget#Page QLabel[p="muted"] {{ color: {sec}; font-size: {s(9.2)}; font-weight: 500; }}
    QWidget#Page QLabel[p="title"] {{ font-size: {s(19)}; font-weight: 800; color: {c.PRINT_ACCENT}; letter-spacing: 2px; }}
    QWidget#Page QLabel[p="period"] {{ color: {c.PRINT_INK}; font-size: {s(10.5)}; font-weight: 700; }}
    QWidget#Page QLabel[p="logo"] {{ background: {c.PRINT_ACCENT}; color: #FFFFFF; font-size: {s(22)}; font-weight: 800; border-radius: {Radius.MD}px; }}
    QWidget#Page QLabel[p="mlabel"] {{ color: {sec}; font-size: {s(8.6)}; font-weight: 700; letter-spacing: 1px; }}
    QWidget#Page QLabel[p="mvalue"] {{ color: {c.PRINT_INK}; font-size: {s(13)}; font-weight: 800; }}
    QWidget#Page QLabel[p="mvalue-pos"] {{ color: {c.POSITIVE}; font-size: {s(13)}; font-weight: 800; }}
    QWidget#Page QLabel[p="mvalue-neg"] {{ color: {c.NEGATIVE}; font-size: {s(13)}; font-weight: 800; }}
    QWidget#Page QLabel[p="pagefoot"] {{ color: {sec}; font-size: {s(8.6)}; font-weight: 500; }}

    QWidget#Page QFrame[p="rule"] {{ background: {c.PRINT_RULE}; max-height: 1px; min-height: 1px; border: none; }}
    QWidget#Page QFrame[p="metric"] {{ background: {c.PRINT_ACCENT_SOFT};
        border: 1px solid {c.PRINT_RULE}; border-radius: {Radius.MD}px; }}

    QWidget#Page QTableWidget {{ background: {c.PRINT_BG}; border: none; gridline-color: transparent;
        font-size: {s(9.3)}; color: {c.PRINT_INK}; }}
    QWidget#Page QTableWidget::item {{ border-bottom: 1px solid {c.PRINT_RULE}; padding: 3px 6px; }}
    QWidget#Page QHeaderView::section {{ background: {c.PRINT_ACCENT}; color: #FFFFFF;
        border: none; padding: 5px 6px; font-weight: 700; font-size: {s(9)}; }}
    """


class SalesReportPrintDocument(QWidget):
    """A single grow-with-content report sheet using the customer's identity."""

    def __init__(self, data: SalesReportPrintData, translator: Translator,
                 paper: PaperSize = PAPERS["A4"], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._d = data
        self._t = translator
        self._p = paper
        self._rtl = translator.direction == Direction.RTL
        self.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft if self._rtl else Qt.LayoutDirection.LeftToRight)
        self.setStyleSheet(_stylesheet(paper.scale))
        self.setFixedWidth(paper.w)
        self.setObjectName("Root")

        page = QWidget(); page.setObjectName("Page")
        page.setFixedWidth(paper.w)
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

        m = paper.margin
        col = QVBoxLayout(page); col.setContentsMargins(m, m, m, m); col.setSpacing(14)
        col.addLayout(self._build_header())
        col.addWidget(self._rule())
        col.addWidget(self._build_metrics())
        col.addWidget(self._build_table(), stretch=1)
        col.addWidget(self._build_footer())

    # ---- pieces ----------------------------------------------------------

    def _rule(self) -> QFrame:
        f = QFrame(); f.setProperty("p", "rule"); return f

    def _build_header(self) -> QHBoxLayout:
        t, co = self._t, self._d.company
        row = QHBoxLayout(); row.setSpacing(14)
        # Logo: real image if present, else letter-mark.
        logo = QLabel(); logo.setProperty("p", "logo")
        logo.setFixedSize(58, 58); logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        path = (co.logo_path or "").strip()
        if path and Path(path).is_file():
            pix = QPixmap(path)
            if not pix.isNull():
                logo.setPixmap(pix.scaled(58, 58, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation))
                logo.setStyleSheet("background: transparent;")
        if logo.pixmap() is None or logo.pixmap().isNull():
            logo.setText((co.name or "Z")[:1].upper())
        row.addWidget(logo, alignment=Qt.AlignmentFlag.AlignTop)

        idcol = QVBoxLayout(); idcol.setSpacing(2)
        name = QLabel(co.name or "—"); name.setProperty("p", "company")
        idcol.addWidget(name)
        for text in (co.address, co.phone, co.email):
            if text:
                lab = QLabel(text); lab.setProperty("p", "muted")
                idcol.addWidget(lab)
        row.addLayout(idcol)
        row.addStretch(1)

        titlecol = QVBoxLayout(); titlecol.setSpacing(2)
        title = QLabel(t.gettext("rep.print_title")); title.setProperty("p", "title")
        title.setAlignment(Qt.AlignmentFlag.AlignRight)
        period = QLabel(t.gettext("rep.print_period").format(
            df=self._d.date_from, dt=self._d.date_to))
        period.setProperty("p", "period"); period.setAlignment(Qt.AlignmentFlag.AlignRight)
        titlecol.addWidget(title); titlecol.addWidget(period)
        row.addLayout(titlecol)
        return row

    def _metric(self, key: str, value: str, kind: str = "") -> QWidget:
        box = QFrame(); box.setProperty("p", "metric")
        v = QVBoxLayout(box); v.setContentsMargins(10, 8, 10, 8); v.setSpacing(3)
        lab = QLabel(self._t.gettext(key)); lab.setProperty("p", "mlabel")
        val = QLabel(format_money(value))
        val.setProperty("p", "mvalue-pos" if kind == "pos" else
                        ("mvalue-neg" if kind == "neg" else "mvalue"))
        v.addWidget(lab); v.addWidget(val)
        return box

    def _build_metrics(self) -> QWidget:
        s = self._d.summary
        wrap = QWidget(); grid = QHBoxLayout(wrap)
        grid.setContentsMargins(0, 0, 0, 0); grid.setSpacing(10)
        grid.addWidget(self._metric("rep.m_gross", s["gross"]), 1)
        grid.addWidget(self._metric("rep.m_paid", s["paid"], "pos"), 1)
        grid.addWidget(self._metric("rep.m_credit", s["credit"]), 1)
        grid.addWidget(self._metric("rep.m_returns", s["returns"], "neg"), 1)
        grid.addWidget(self._metric("rep.m_net", s["net"]), 1)
        return wrap

    def _columns(self) -> list[tuple[str, str, str]]:
        return [("rep.col_date", "date", "l"), ("rep.col_docno", "document_no", "l"),
                ("rep.col_customer", "party", "l"), ("rep.col_type", "type", "l"),
                ("rep.col_gross", "gross", "r"), ("rep.col_paid", "paid", "r"),
                ("rep.col_credit", "credit", "r"), ("rep.col_returned", "returned", "r"),
                ("rep.col_net", "net", "r")]

    def _build_table(self) -> QWidget:
        cols = self._columns()
        rows = self._d.rows
        table = QTableWidget(len(rows) + 1, len(cols))   # +1 for totals row
        table.setHorizontalHeaderLabels([self._t.gettext(h) for h, _k, _a in cols])
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        hh = table.horizontalHeader(); hh.setHighlightSections(False)
        for i, (_h, key, _a) in enumerate(cols):
            hh.setSectionResizeMode(
                i, QHeaderView.ResizeMode.Stretch if key == "party"
                else QHeaderView.ResizeMode.ResizeToContents)
        money = {"gross", "paid", "credit", "returned", "net"}
        from decimal import Decimal
        tot = {k: Decimal("0") for k in money}
        for r, data in enumerate(rows):
            for c, (_h, key, align) in enumerate(cols):
                if key == "type":
                    text = self._t.gettext("rep.row_walkin" if data.get("walkin")
                                           else "rep.row_registered")
                else:
                    value = data.get(key)
                    text = format_money(value) if key in money else ("" if value is None
                                                                     else str(value))
                    if key in money:
                        try:
                            tot[key] += Decimal(str(value))
                        except Exception:
                            pass
                self._cell(table, r, c, text, align)
        # totals row
        tr = len(rows)
        self._cell(table, tr, 0, self._t.gettext("rep.total"), "l", bold=True)
        for c, (_h, key, align) in enumerate(cols):
            if key in money:
                self._cell(table, tr, c, format_money(tot[key]), "r", bold=True)
        # size the table to its content so the whole sheet grows naturally
        table.resizeRowsToContents()
        height = table.horizontalHeader().height() + 6
        for r in range(table.rowCount()):
            height += table.rowHeight(r)
        table.setFixedHeight(height)
        table.setMinimumHeight(height)
        return table

    def _cell(self, table: QTableWidget, r: int, c: int, text: str, align: str,
              *, bold: bool = False) -> None:
        item = QTableWidgetItem(text)
        a = Qt.AlignmentFlag.AlignRight if align == "r" else Qt.AlignmentFlag.AlignLeft
        item.setTextAlignment(a | Qt.AlignmentFlag.AlignVCenter)
        if bold:
            font = item.font(); font.setBold(True); item.setFont(font)
        table.setItem(r, c, item)

    def _build_footer(self) -> QWidget:
        s = self._d.summary
        foot = QLabel(self._t.gettext("rep.summary_line").format(
            count=s["invoices"], df=self._d.date_from, dt=self._d.date_to))
        foot.setProperty("p", "pagefoot")
        return foot
