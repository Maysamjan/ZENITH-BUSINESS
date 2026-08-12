"""Reusable search-as-you-type selector (Prompt 01D §1, §4, §5, §12).

A single, data-source-agnostic autocomplete control that every future module
reuses instead of long traditional combo boxes: items, customers, suppliers,
accounts, warehouses, salespersons, units, categories, ...

Architecture
------------
The widget knows nothing about the database. It talks to a :class:`SearchProvider`
(a Protocol) that returns rich rows for a typed query. Stage 02+ implements real
providers backed by repositories/services without changing this UI.

Results render in an in-window overlay panel (a child of the top-level window,
not a native popup) so the design is consistent across platforms and testable /
capturable headlessly.

Keyboard model (Prompt 01D §3)
------------------------------
    Down  : open results / move highlight down
    Up    : move highlight up
    Enter : accept highlighted row  (emits ``rowSelected``)
    Esc   : close results
    type  : filter as you type
Click a row to accept it with the mouse.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zenith_business.ui.design.tokens import Color, ControlSize, Radius, Spacing


@dataclass(frozen=True)
class SearchColumn:
    """A column shown in the results panel."""

    title: str
    align: str = "l"          # 'l' or 'r'
    stretch: bool = False     # this column absorbs extra width
    width: int | None = None  # fixed width when not stretching


@dataclass
class SearchRow:
    """A single result row.

    ``values`` are display strings (one per column). ``payload`` carries the
    structured data a caller needs after selection (code, unit, price, stock,
    balance, ...) so no information already known to the system is re-typed.
    """

    values: list[str]
    payload: dict = field(default_factory=dict)


@runtime_checkable
class SearchProvider(Protocol):
    """Contract implemented by data sources (mock now, repositories later)."""

    def columns(self) -> list[SearchColumn]: ...
    def search(self, text: str, limit: int = 8) -> list[SearchRow]: ...


class _ResultsPanel(QFrame):
    """In-window overlay listing search results."""

    def __init__(self, columns: list[SearchColumn], parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("SearchPanel")
        self.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(0)

        self._columns = columns
        self.table = QTableWidget(0, len(columns))
        self.table.setHorizontalHeaderLabels([c.title for c in columns])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(ControlSize.TABLE_ROW_HEIGHT)

        header = self.table.horizontalHeader()
        header.setHighlightSections(False)
        for i, col in enumerate(columns):
            if col.stretch:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self.table.setColumnWidth(i, col.width or 90)
        layout.addWidget(self.table)

    def set_rows(self, rows: list[SearchRow]) -> None:
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, value in enumerate(row.values):
                item = QTableWidgetItem(value)
                align = (Qt.AlignmentFlag.AlignRight if self._columns[c].align == "r"
                         else Qt.AlignmentFlag.AlignLeft)
                item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(r, c, item)
        if rows:
            self.table.selectRow(0)

    def content_height(self) -> int:
        rows = self.table.rowCount()
        return (ControlSize.TABLE_HEADER_HEIGHT
                + rows * ControlSize.TABLE_ROW_HEIGHT + 4)


class SearchSelector(QWidget):
    """A line edit with a rich, provider-driven autocomplete panel."""

    #: Emitted with the selected :class:`SearchRow`.
    rowSelected = pyqtSignal(object)
    #: Emitted when Enter is pressed with no open results (flow: move on).
    submitted = pyqtSignal()

    def __init__(
        self,
        provider: SearchProvider,
        *,
        placeholder: str = "",
        display_index: int = 0,
        panel_width: int = 460,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._provider = provider
        self._display_index = display_index
        self._panel_width = panel_width
        self._rows: list[SearchRow] = []
        self._panel: _ResultsPanel | None = None

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self._glyph = QLabel("⌕")  # ⌕ magnifier
        self._glyph.setProperty("role", "search-glyph")
        self._glyph.setFixedWidth(20)
        self._glyph.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._edit = QLineEdit()
        self._edit.setPlaceholderText(placeholder)
        self._edit.setProperty("role", "search-edit")
        self._edit.textEdited.connect(self._on_text_edited)
        self._edit.installEventFilter(self)

        row.addWidget(self._glyph)
        row.addWidget(self._edit, 1)

    # ---- public API ------------------------------------------------------

    @property
    def line_edit(self) -> QLineEdit:
        return self._edit

    def text(self) -> str:
        return self._edit.text()

    def set_text(self, text: str) -> None:
        self._edit.setText(text)

    def clear(self) -> None:
        self._edit.clear()
        self._hide_panel()

    def focus(self) -> None:
        self._edit.setFocus()

    def open_with(self, text: str) -> None:
        """Programmatically type ``text`` and open the results (for demos/tests)."""
        self._edit.setText(text)
        self._on_text_edited(text)

    def current_rows(self) -> list[SearchRow]:
        return list(self._rows)

    def is_panel_open(self) -> bool:
        return self._panel is not None and self._panel.isVisible()

    # ---- behavior --------------------------------------------------------

    def _on_text_edited(self, text: str) -> None:
        text = text.strip()
        if not text:
            self._hide_panel()
            return
        self._rows = self._provider.search(text)
        if not self._rows:
            self._hide_panel()
            return
        self._ensure_panel()
        assert self._panel is not None
        self._panel.set_rows(self._rows)
        self._position_panel()
        self._panel.show()
        self._panel.raise_()

    def _ensure_panel(self) -> None:
        if self._panel is None:
            self._panel = _ResultsPanel(self._provider.columns(), self.window())
            self._panel.table.cellClicked.connect(lambda r, _c: self._accept_index(r))

    def _position_panel(self) -> None:
        assert self._panel is not None
        window = self.window()
        top_left = self._edit.mapTo(window, self._edit.rect().bottomLeft())
        width = max(self._panel_width, self._edit.width() + self._glyph.width())
        # In RTL, right-align the panel to the field's right edge.
        if self.layoutDirection() == Qt.LayoutDirection.RightToLeft:
            right = self._edit.mapTo(window, self._edit.rect().bottomRight())
            x = max(0, right.x() - width)
        else:
            x = max(0, top_left.x() - self._glyph.width())
        y = top_left.y() + 2
        height = self._panel.content_height()
        # Keep the panel inside the window vertically.
        if y + height > window.height():
            top = self._edit.mapTo(window, self._edit.rect().topLeft())
            y = max(0, top.y() - height - 2)
        self._panel.setGeometry(x, y, width, height)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 (Qt signature)
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent

        if obj is self._edit and event.type() == QEvent.Type.KeyPress:
            assert isinstance(event, QKeyEvent)
            key = event.key()
            if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                if not self.is_panel_open():
                    self._on_text_edited(self._edit.text())
                else:
                    self._move(1 if key == Qt.Key.Key_Down else -1)
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self.is_panel_open():
                    self._accept_index(self._current_index())
                else:
                    self.submitted.emit()
                return True
            if key == Qt.Key.Key_Escape and self.is_panel_open():
                self._hide_panel()
                return True
        return super().eventFilter(obj, event)

    def _current_index(self) -> int:
        if self._panel is None:
            return -1
        return self._panel.table.currentRow()

    def _move(self, delta: int) -> None:
        if self._panel is None:
            return
        count = self._panel.table.rowCount()
        if count == 0:
            return
        new = (self._current_index() + delta) % count
        self._panel.table.selectRow(new)

    def _accept_index(self, index: int) -> None:
        if index < 0 or index >= len(self._rows):
            return
        row = self._rows[index]
        display = (row.values[self._display_index]
                   if self._display_index < len(row.values) else row.values[0])
        self._edit.setText(display)
        self._hide_panel()
        self.rowSelected.emit(row)

    def _hide_panel(self) -> None:
        if self._panel is not None:
            self._panel.hide()


def selector_styles() -> str:
    """QSS for selector chrome (merged into the global stylesheet)."""
    c = Color
    return f"""
    QLabel[role="search-glyph"] {{
        color: {c.TEXT_MUTED};
        background: {c.SURFACE};
        border: 1px solid {c.BORDER};
        border-right: none;
        border-top-left-radius: {Radius.SM}px;
        border-bottom-left-radius: {Radius.SM}px;
        min-height: {ControlSize.INPUT_HEIGHT}px;
    }}
    QLineEdit[role="search-edit"] {{
        border-top-left-radius: 0px;
        border-bottom-left-radius: 0px;
    }}
    QFrame#SearchPanel {{
        background: {c.SURFACE};
        border: 1px solid {c.BORDER_STRONG};
        border-radius: {Radius.SM}px;
    }}
    QFrame#SearchPanel QTableWidget {{
        border: none;
        background: {c.SURFACE};
        selection-background-color: {c.SEARCH_SELECTION_BG};
        selection-color: {c.TEXT_PRIMARY};
    }}
    QFrame#SearchPanel QTableWidget::item:selected {{
        background: {c.SEARCH_SELECTION_BG};
        color: {c.PRIMARY_PRESSED};
    }}
    QFrame#SearchPanel QHeaderView::section {{
        background: {c.PRIMARY_SOFT};
        color: {c.PRIMARY_PRESSED};
        border: none; border-bottom: 1px solid {c.BORDER};
        font-weight: 600;
    }}
    """
