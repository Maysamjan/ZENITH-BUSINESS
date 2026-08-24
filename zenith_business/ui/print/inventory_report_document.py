"""Printed inventory report (Stage 06).

Same print standard as the Sales Report: the header carries the CUSTOMER's own
business identity (logo / name / address / phone) from Company settings — never
the Zenith Soft developer identity — and the sheet is **A4 only**, because an
inventory table is wide and A5 would cost readability.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QFrame,
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
from zenith_business.ui.print.sales_report_document import ReportCompany


@dataclass(frozen=True)
class InventoryReportPrintData:
    company: ReportCompany
    title: str
    columns: list[tuple[str, str, str]]   # (header text, row key, align)
    rows: list[dict]
    money_keys: frozenset


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
    QWidget#Page QLabel[p="title"] {{ font-size: {s(18)}; font-weight: 800; color: {c.PRINT_ACCENT}; letter-spacing: 1px; }}
    QWidget#Page QLabel[p="logo"] {{ background: {c.PRINT_ACCENT}; color: #FFFFFF; font-size: {s(22)}; font-weight: 800; border-radius: {Radius.MD}px; }}
    QWidget#Page QLabel[p="pagefoot"] {{ color: {sec}; font-size: {s(8.6)}; font-weight: 500; }}
    QWidget#Page QFrame[p="rule"] {{ background: {c.PRINT_RULE}; max-height: 1px; min-height: 1px; border: none; }}
    QWidget#Page QTableWidget {{ background: {c.PRINT_BG}; border: none; gridline-color: transparent;
        font-size: {s(9.3)}; color: {c.PRINT_INK}; }}
    QWidget#Page QTableWidget::item {{ border-bottom: 1px solid {c.PRINT_RULE}; padding: 3px 6px; }}
    QWidget#Page QHeaderView::section {{ background: {c.PRINT_ACCENT}; color: #FFFFFF;
        border: none; padding: 5px 6px; font-weight: 700; font-size: {s(9)}; }}
    """


class InventoryReportPrintDocument(QWidget):
    """A single grow-with-content A4 sheet using the customer's identity."""

    def __init__(self, data: InventoryReportPrintData, translator: Translator,
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

        page = QWidget(); page.setObjectName("Page"); page.setFixedWidth(paper.w)
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        m = paper.margin
        col = QVBoxLayout(page); col.setContentsMargins(m, m, m, m); col.setSpacing(14)
        col.addLayout(self._build_header())
        rule = QFrame(); rule.setProperty("p", "rule"); col.addWidget(rule)
        col.addWidget(self._build_table(), stretch=1)
        foot = QLabel(self._t.gettext("inv.items_count")
                      .replace("{n}", str(len(self._d.rows))))
        foot.setProperty("p", "pagefoot")
        col.addWidget(foot)

    def _build_header(self) -> QHBoxLayout:
        co = self._d.company
        row = QHBoxLayout(); row.setSpacing(14)
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
                lab = QLabel(text); lab.setProperty("p", "muted"); idcol.addWidget(lab)
        row.addLayout(idcol)
        row.addStretch(1)

        title = QLabel(self._d.title); title.setProperty("p", "title")
        title.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(title, alignment=Qt.AlignmentFlag.AlignTop)
        return row

    def _build_table(self) -> QWidget:
        cols, rows = self._d.columns, self._d.rows
        table = QTableWidget(len(rows), len(cols))
        table.setHorizontalHeaderLabels([h for h, _k, _a in cols])
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        # A4 fits these columns, so the printed sheet never scrolls sideways.
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        hh = table.horizontalHeader(); hh.setHighlightSections(False)
        stretch_key = next((k for _h, k, _a in cols if k in ("item_name", "notes")), None)
        for i, (_h, key, _a) in enumerate(cols):
            hh.setSectionResizeMode(
                i, QHeaderView.ResizeMode.Stretch if key == stretch_key
                else QHeaderView.ResizeMode.ResizeToContents)
        for r, data in enumerate(rows):
            for c, (_h, key, align) in enumerate(cols):
                value = data.get(key)
                text = (format_money(value)
                        if key in self._d.money_keys and str(value or "").strip()
                        else ("" if value is None else str(value)))
                item = QTableWidgetItem(text)
                a = (Qt.AlignmentFlag.AlignRight if align == "r"
                     else Qt.AlignmentFlag.AlignLeft)
                item.setTextAlignment(a | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(r, c, item)
        table.resizeRowsToContents()
        height = table.horizontalHeader().height() + 6
        for r in range(table.rowCount()):
            height += table.rowHeight(r)
        table.setFixedHeight(max(height, 60))
        return table
