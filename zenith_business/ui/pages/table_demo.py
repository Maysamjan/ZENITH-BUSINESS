"""Data table demonstration (Prompt 01B §19).

Establishes the reusable table visual standard: styled header, selected row,
readable alternating rows, numeric right-alignment, sensible column sizing,
horizontal + vertical scrolling. Placeholder rows only — NO business data and
NO database tables.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Translator
from zenith_business.ui.components import PageHeader, muted
from zenith_business.ui.design.tokens import ControlSize, Spacing

# Generic, obviously-fake illustration rows (not business data).
_SAMPLE = [
    ("A-001", "Alpha", "A", "1404/01/15", 12, 1250.00, "table.status_active"),
    ("A-002", "Bravo", "B", "1404/02/03", 4, 380.50, "table.status_pending"),
    ("A-003", "Charlie", "A", "1404/02/21", 40, 9600.00, "table.status_active"),
    ("A-004", "Delta", "C", "1404/03/09", 7, 210.75, "table.status_active"),
    ("A-005", "Echo", "B", "1404/03/28", 25, 5125.25, "table.status_pending"),
    ("A-006", "Foxtrot", "A", "1404/04/11", 3, 99.00, "table.status_active"),
]


class TableDemoPage(QWidget):
    """Table design demonstration page."""

    _NUMERIC_COLS = (4, 5)  # Qty, Amount

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._t = translator

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            Spacing.PAGE_MARGIN, Spacing.PAGE_MARGIN,
            Spacing.PAGE_MARGIN, Spacing.PAGE_MARGIN,
        )
        layout.setSpacing(Spacing.SECTION_GAP)

        self._header = PageHeader(
            self._t.gettext("tabledemo.title"),
            self._t.gettext("tabledemo.subtitle"),
        )
        layout.addWidget(self._header)

        self._table = self._build_table()
        layout.addWidget(self._table, stretch=1)

        self._footer = muted(self._t.gettext("table.footer"))
        layout.addWidget(self._footer)

    def _column_keys(self) -> list[str]:
        return [
            "table.col_code", "table.col_name", "table.col_category",
            "table.col_date", "table.col_qty", "table.col_amount",
            "table.col_status",
        ]

    def _build_table(self) -> QTableWidget:
        keys = self._column_keys()
        table = QTableWidget(len(_SAMPLE), len(keys))
        table.setHorizontalHeaderLabels([self._t.gettext(k) for k in keys])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setDefaultSectionSize(ControlSize.TABLE_ROW_HEIGHT)
        table.setShowGrid(True)

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Name grows
        header.setHighlightSections(False)

        self._populate(table)
        # Preselect a row so the selected-state styling is visible.
        table.selectRow(2)
        return table

    def _populate(self, table: QTableWidget) -> None:
        for r, (code, name, cat, date, qty, amount, status_key) in enumerate(_SAMPLE):
            values = [
                code, name, cat, date, f"{qty:,}", f"{amount:,.2f}",
                self._t.gettext(status_key),
            ]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col in self._NUMERIC_COLS:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                else:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                    )
                table.setItem(r, col, item)

    @property
    def table(self) -> QTableWidget:
        return self._table

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        keys = self._column_keys()
        self._table.setHorizontalHeaderLabels([translator.gettext(k) for k in keys])
        self._footer.setText(translator.gettext("table.footer"))
        # Refresh status column text for the active language.
        for r, row in enumerate(_SAMPLE):
            self._table.item(r, 6).setText(translator.gettext(row[6]))
