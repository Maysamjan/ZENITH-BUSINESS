"""License History — what was issued, to whom (Vendor Manager §9).

Search by anything a vendor would actually remember: a shop name, a phone
number, a city, a licence number, a machine id. Select a row to see the whole
record and copy the key again without reissuing — reissuing for a customer who
simply lost the message would burn a serial number and leave two live keys where
one was meant.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

COLUMNS = ("Created", "License ID", "Type", "Customer", "Machine ID",
           "Expires", "City")


class HistoryPage(QWidget):
    """Every licence this Manager has issued, searchable."""

    def __init__(self, *, load: Callable[[str], list],
                 on_reexport: Callable[[object], None],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._load = load
        self._on_reexport = on_reexport
        self._rows: list = []

        col = QVBoxLayout(self)
        col.setContentsMargins(16, 16, 16, 16)
        col.setSpacing(10)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Search by customer, phone, city, license ID or machine ID…")
        self.search.textChanged.connect(self.reload)
        top.addWidget(self.search, 1)
        self.refresh = QPushButton("Refresh")
        self.refresh.clicked.connect(self.reload)
        top.addWidget(self.refresh)
        col.addLayout(top)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        for index in range(len(COLUMNS)):
            header.setSectionResizeMode(
                index, QHeaderView.ResizeMode.Stretch if index == 3
                else QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._show_detail)
        col.addWidget(self.table, 1)

        self.detail = QPlainTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setFixedHeight(120)
        self.detail.setPlaceholderText("Select a license to see its details.")
        col.addWidget(self.detail)

        row = QHBoxLayout()
        self.copy_button = QPushButton("📋  Copy Product Key")
        self.copy_button.clicked.connect(self._copy)
        self.export_button = QPushButton("💾  Re-export .zlic")
        self.export_button.clicked.connect(self._reexport)
        for button in (self.copy_button, self.export_button):
            button.setEnabled(False)
            row.addWidget(button)
        row.addStretch(1)
        self.count = QLabel("")
        self.count.setProperty("role", "hint")
        row.addWidget(self.count)
        col.addLayout(row)

    # ---- data ------------------------------------------------------------

    def reload(self) -> None:
        self._rows = self._load(self.search.text())
        self.table.setRowCount(0)
        self.table.setRowCount(len(self._rows))
        for index, record in enumerate(self._rows):
            values = (
                (record.created_at or "")[:19].replace("T", " "),
                record.license_id, record.license_type, record.issued_to or "—",
                record.machine_short, record.expires_at or "never",
                record.city or "",
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft
                                      | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(index, column, item)
        self.count.setText(f"{len(self._rows)} license(s)")
        self.detail.clear()
        for button in (self.copy_button, self.export_button):
            button.setEnabled(False)

    def selected(self):
        rows = self.table.selectionModel().selectedRows() if \
            self.table.selectionModel() else []
        if not rows:
            return None
        index = rows[0].row()
        return self._rows[index] if 0 <= index < len(self._rows) else None

    def _show_detail(self) -> None:
        record = self.selected()
        if record is None:
            self.detail.clear()
            return
        lines = [
            f"License ID   : {record.license_id}",
            f"Product      : {record.product_id}",
            f"Type         : {record.license_type}"
            + (f"  ({record.demo_days} days)" if record.demo_days else ""),
            f"Customer     : {record.issued_to or '—'}",
            f"Phone / City : {record.phone or '—'} / {record.city or '—'}",
            f"Machine ID   : {record.machine_short}",
            f"Fingerprint  : {record.machine_fingerprint}",
            f"Issued       : {record.issued_at}    Expires: "
            f"{record.expires_at or 'never'}",
            f"Notes        : {record.notes or '—'}",
            f".zlic        : {record.zlic_path or 'not exported'}",
            "",
            record.product_key,
        ]
        self.detail.setPlainText("\n".join(lines))
        for button in (self.copy_button, self.export_button):
            button.setEnabled(True)

    def _copy(self) -> None:
        from PyQt6.QtWidgets import QApplication

        record = self.selected()
        if record is None:
            return
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(record.product_key)
        self.count.setText(f"Copied {record.license_id}")

    def _reexport(self) -> None:
        record = self.selected()
        if record is not None:
            self._on_reexport(record)
