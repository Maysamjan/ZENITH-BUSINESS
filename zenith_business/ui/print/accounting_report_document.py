"""Printed financial statement (Stage 09) — the Stage 08 A4 sheet plus a totals row.

Stage 09 prints on the Stage 08 costing sheet: the same A4 composition, the same
customer business identity, the same Dari pinned to bundled Vazirmatn. One thing
it needs that a costing report never did — a **totals row that lines up under the
columns it totals**. An ageing report's whole purpose is "how much of what I am
owed is 90+ days old", and the label/value totals block beneath the table cannot
express a figure per column.

It is added by **subclassing**, not by editing the Stage 08 document: Stage 08 is
LOCKED, it renders exactly as it did, and nothing it passes changes. The extra
row is opt-in through :class:`AccountingReportPrintData.total_row`, so a statement
that has no such row (a trial balance, a P&L) prints byte-identically to before.

The row stays OUT of ``rows``. That separation is the Stage 08 lesson that cost a
round of review — folding totals into the table made a two-item valuation report
"4 item(s)" — so a totals row is rendered as a totals row and counted as nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QWidget

from zenith_business.core.money import format_money
from zenith_business.ui.print.costing_report_document import (
    CostingReportPrintData,
    CostingReportPrintDocument,
)


@dataclass(frozen=True)
class AccountingReportPrintData(CostingReportPrintData):
    """A costing sheet's payload, plus an optional columnar totals row."""

    #: Row-shaped totals (same keys as ``rows``) printed beneath the table in
    #: bold. ``None`` for statements whose totals are not per-column.
    total_row: dict | None = None


class AccountingReportPrintDocument(CostingReportPrintDocument):
    """The Stage 08 sheet, with a bold totals row under the table when given one."""

    #: Share of the page width the title may take before it wraps. Wide enough
    #: that a ledger title and its period wrap to two lines rather than five.
    _TITLE_WIDTH = 0.58

    def _build_header(self) -> QHBoxLayout:
        """The Stage 08 header, with a title that wraps instead of overflowing.

        Stage 08's titles are two or three words ("Inventory Valuation"); a
        statement's can be "General Ledger — 5000 Cost of Goods Sold · 2026-01-01
        — 2026-09-17". With no width limit and no wrapping that label simply
        overflowed to the left, printing OVER the business name — the header came
        out reading "Kabul Traders Ltd ods Sold". Bounding it and letting it wrap
        keeps both legible, and leaves the Stage 08 sheet untouched.
        """
        row = super()._build_header()
        for i in range(row.count()):
            item = row.itemAt(i)
            widget = item.widget()
            if isinstance(widget, QLabel) and widget.property("p") == "title":
                widget.setWordWrap(True)
                # The width is PINNED, not merely capped: a word-wrapping QLabel
                # reports a narrow sizeHint, so in a horizontal layout a maximum
                # alone still leaves it squeezed into five lines. The text is
                # right-aligned, so a short title looks no different.
                widget.setFixedWidth(int(self._p.w * self._TITLE_WIDTH))
                widget.setAlignment(Qt.AlignmentFlag.AlignRight
                                    | Qt.AlignmentFlag.AlignTop)
            elif item.layout() is not None:
                # A wrapped title makes the header row taller, and the address
                # block would otherwise space its lines out to match. Keep them
                # together at the top where they read as one identity.
                item.layout().addStretch(1)
        return row

    def _build_table(self) -> QWidget:
        table = super()._build_table()
        total_row = getattr(self._d, "total_row", None)
        if not total_row or not isinstance(table, QTableWidget):
            return table

        r = table.rowCount()
        table.insertRow(r)
        for c, (_h, key, align) in enumerate(self._d.columns):
            value = total_row.get(key)
            text = (format_money(value)
                    if key in self._d.money_keys and str(value or "").strip()
                    else ("" if value is None else str(value)))
            item = QTableWidgetItem(text)
            a = (Qt.AlignmentFlag.AlignRight if align == "r"
                 else Qt.AlignmentFlag.AlignLeft)
            item.setTextAlignment(a | Qt.AlignmentFlag.AlignVCenter)
            font = item.font(); font.setBold(True); item.setFont(font)
            table.setItem(r, c, item)

        # super() sized the table for its own row count, so it has to be re-measured.
        table.resizeRowsToContents()
        height = table.horizontalHeader().height() + 6
        for i in range(table.rowCount()):
            height += table.rowHeight(i)
        table.setFixedHeight(max(height, 60))
        return table
