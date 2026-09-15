"""Printed costing report (Stage 08) — A4, the customer's own identity.

A separate sheet from the Stage 06 inventory report, for two reasons that the
shared sheet could not serve without changing LOCKED behaviour:

* **Totals are not items.** The Stage 06 sheet counts the rows it is given, so
  folding "Total inventory value" into the table made a two-item valuation
  report its own contents as "4 item(s)". Here the totals are a block of their
  own, below the table, and the item count counts items.
* **Dari is pinned to the bundled font.** The shared font stack lists system
  faces after Vazirmatn; on a machine that has Segoe UI or Tahoma, Qt may
  substitute one of them for Persian text and the sheet comes out in a different
  face from the rest of the application. For Dari this sheet asks for Vazirmatn
  and nothing else, so it renders identically on every customer machine. English
  keeps the existing stack unchanged.

Everything else follows the established print standard: the header carries the
CUSTOMER's business identity (logo / name / address / phone / email / tax id)
from the shared source, never the Zenith Soft developer identity, and the sheet
is **A4 only** because a costing table is wide.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap
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

from zenith_business.core.fonts import FONT_FAMILY
from zenith_business.core.i18n import Direction, Translator
from zenith_business.core.money import format_money
from zenith_business.ui.design.tokens import Color, Radius, Typography
from zenith_business.ui.mock.demo_invoice import CompanyInfo
from zenith_business.ui.print.invoice_document import PAPERS, PaperSize


@dataclass(frozen=True)
class CostingReportPrintData:
    """What the sheet prints.

    ``company`` is the full :class:`CompanyInfo` rather than a reduced copy, so
    the tax id the owner configured can reach the page without a second identity
    shape to keep in step.
    """

    company: CompanyInfo
    title: str
    columns: list[tuple[str, str, str]]     # (header text, row key, align)
    rows: list[dict]                        # ITEMS only — never totals
    money_keys: frozenset
    totals: list[tuple[str, str]] = field(default_factory=list)  # (label, value)
    #: Whether an "N item(s)" line belongs at the foot. A valuation lists stock,
    #: so counting it is useful; Gross Profit lists calculation steps, and
    #: calling "Net sales" an item is simply wrong.
    show_item_count: bool = True


def _stylesheet(scale: float, rtl: bool) -> str:
    c = Color
    sec = "#3C4756"
    # Dari asks for the bundled face alone; English keeps the shared stack.
    family = f'"{FONT_FAMILY}"' if rtl else Typography.FAMILY

    def s(pt: float) -> str:
        return f"{max(7.0, pt * scale):.1f}pt"

    return f"""
    QWidget#Page {{ background: {c.PRINT_BG}; }}
    QWidget#Page QLabel {{ background: transparent; color: {c.PRINT_INK};
        font-family: {family}; font-size: {s(9.5)}; }}
    QWidget#Page QLabel[p="company"] {{ font-size: {s(16)}; font-weight: 800; }}
    QWidget#Page QLabel[p="muted"] {{ color: {sec}; font-size: {s(9.2)}; font-weight: 500; }}
    QWidget#Page QLabel[p="title"] {{ font-size: {s(18)}; font-weight: 800;
        color: {c.PRINT_ACCENT}; letter-spacing: 1px; }}
    QWidget#Page QLabel[p="logo"] {{ background: {c.PRINT_ACCENT}; color: #FFFFFF;
        font-size: {s(22)}; font-weight: 800; border-radius: {Radius.MD}px; }}
    QWidget#Page QLabel[p="totlabel"] {{ font-size: {s(10)}; font-weight: 700; }}
    QWidget#Page QLabel[p="totvalue"] {{ font-size: {s(10)}; font-weight: 800;
        color: {c.PRINT_ACCENT}; }}
    QWidget#Page QLabel[p="pagefoot"] {{ color: {sec}; font-size: {s(8.6)}; font-weight: 500; }}
    QWidget#Page QFrame[p="rule"] {{ background: {c.PRINT_RULE}; max-height: 1px;
        min-height: 1px; border: none; }}
    QWidget#Page QTableWidget {{ background: {c.PRINT_BG}; border: none;
        gridline-color: transparent; font-family: {family}; font-size: {s(9.2)};
        color: {c.PRINT_INK}; }}
    QWidget#Page QHeaderView::section {{ background: {c.PRINT_ACCENT}; color: #FFFFFF;
        border: none; padding: {max(3, int(6 * scale))}px; font-family: {family};
        font-size: {s(9.0)}; font-weight: 700; }}
    QWidget#Page QTableWidget::item {{ padding: {max(2, int(5 * scale))}px;
        border-bottom: 1px solid {c.PRINT_RULE}; }}
    """


class CostingReportPrintDocument(QWidget):
    """A single grow-with-content A4 sheet using the customer's identity."""

    def __init__(self, data: CostingReportPrintData, translator: Translator,
                 paper: PaperSize = PAPERS["A4"], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._d = data
        self._t = translator
        self._p = paper
        self._rtl = translator.direction == Direction.RTL
        self.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft if self._rtl else Qt.LayoutDirection.LeftToRight)
        self.setStyleSheet(_stylesheet(paper.scale, self._rtl))
        self.setFixedWidth(paper.w)
        if self._rtl:
            # Belt and braces: the widget font is set as well as the stylesheet,
            # so no child can inherit a system face through a path the sheet
            # does not cover.
            self.setFont(QFont(FONT_FAMILY))

        page = QWidget(); page.setObjectName("Page"); page.setFixedWidth(paper.w)
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)
        m = paper.margin
        col = QVBoxLayout(page); col.setContentsMargins(m, m, m, m); col.setSpacing(14)
        col.addLayout(self._build_header())
        rule = QFrame(); rule.setProperty("p", "rule"); col.addWidget(rule)
        col.addWidget(self._build_table(), stretch=1)
        totals = self._build_totals()
        if totals is not None:
            col.addWidget(totals)
        # Counts ITEMS. The totals live outside the table precisely so this
        # number means what it says — and a report whose rows are not items
        # omits the line rather than miscounting them as stock.
        if self._d.show_item_count:
            foot = QLabel(self._t.gettext("inv.items_count")
                          .replace("{n}", str(len(self._d.rows))))
            foot.setProperty("p", "pagefoot")
            col.addWidget(foot)

    # ---- header ----------------------------------------------------------

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
        tax = (co.tax_id or "").strip()
        details = [co.address, co.phone, co.email]
        if tax:
            details.append(f"{self._t.gettext('print.tax_id')}: {tax}")
        for text in details:
            if text:
                lab = QLabel(text); lab.setProperty("p", "muted"); idcol.addWidget(lab)
        row.addLayout(idcol)
        row.addStretch(1)

        title = QLabel(self._d.title); title.setProperty("p", "title")
        title.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(title, alignment=Qt.AlignmentFlag.AlignTop)
        return row

    # ---- body ------------------------------------------------------------

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
        stretch_key = next((k for _h, k, _a in cols if k in ("item_name", "label")), None)
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

    def _build_totals(self) -> QWidget | None:
        """The report's own totals, below the table rather than inside it."""
        if not self._d.totals:
            return None
        host = QWidget()
        col = QVBoxLayout(host); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(4)
        for label, value in self._d.totals:
            line = QHBoxLayout(); line.setSpacing(10)
            lab = QLabel(label); lab.setProperty("p", "totlabel")
            val = QLabel(str(value)); val.setProperty("p", "totvalue")
            line.addStretch(1); line.addWidget(lab); line.addWidget(val)
            col.addLayout(line)
        return host
