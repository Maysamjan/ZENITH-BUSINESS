"""Reusable management-screen framework (Stage 03 §13, §14, §27, §32).

``ManagementPage`` is the shared commercial-desktop layout every master-data
module uses: a header (title + live record count + primary New action), a
search/filter bar, and a dominant full-width table with contextual row actions.
``FormDialog`` is the shared sectioned create/edit dialog. Both are pure
presentation — they call services (passed in) and never touch SQL. They inherit
RTL/LTR from the parent window's layout direction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Translator
from zenith_business.ui.components import (
    Card,
    RowActions,
    chip,
    error_label,
    field_label,
    ghost_button,
    page_title,
    primary_button,
    secondary_button,
)
from zenith_business.ui.design.tokens import ControlSize, FieldWidth, Spacing


@dataclass
class Column:
    """A management-table column."""

    key: str
    title: str
    width: int | None = None
    stretch: bool = False
    align: str = "l"          # 'l' | 'r' | 'c'
    kind: str = "text"        # 'text' | 'money' | 'status'


class ManagementPage(QWidget):
    """Header + search/filter bar + dominant table + row actions."""

    def __init__(
        self,
        translator: Translator,
        *,
        title_key: str,
        subtitle_key: str | None,
        columns: list[Column],
        on_new: Callable[[], None] | None = None,
        on_edit: Callable[[dict], None] | None = None,
        on_toggle_active: Callable[[dict], None] | None = None,
        on_view: Callable[[dict], None] | None = None,
        view_label_key: str = "md.view",
        new_label_key: str = "md.new",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._t = translator
        self._columns = columns
        self._on_edit = on_edit
        self._on_toggle = on_toggle_active
        self._on_view = on_view
        self._view_label_key = view_label_key
        self._rows: list[dict] = []
        self._filter_text = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.PAGE_MARGIN, Spacing.PAGE_MARGIN,
                                Spacing.PAGE_MARGIN, Spacing.PAGE_MARGIN)
        root.setSpacing(Spacing.SECTION_GAP)

        # ---- header ----
        header = QHBoxLayout()
        header.setSpacing(Spacing.MD)
        title_col = QVBoxLayout()
        title_col.setSpacing(Spacing.XXS)
        self._title = page_title(self._t.gettext(title_key))
        self._title_key = title_key
        title_col.addWidget(self._title)
        self._count = QLabel("")
        self._count.setProperty("role", "muted")
        title_col.addWidget(self._count)
        header.addLayout(title_col)
        header.addStretch(1)
        if on_new is not None:
            self._new_btn = primary_button(self._t.gettext(new_label_key))
            self._new_label_key = new_label_key
            self._new_btn.clicked.connect(lambda: on_new())
            header.addWidget(self._new_btn, alignment=Qt.AlignmentFlag.AlignTop)
        else:
            self._new_btn = None
        root.addLayout(header)

        # ---- search / filter bar ----
        bar = Card(role="section")
        bar.body.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        bar_row = QHBoxLayout()
        bar_row.setSpacing(Spacing.SM)
        self._search = QLineEdit()
        self._search.setPlaceholderText(self._t.gettext("md.search"))
        self._search.setClearButtonEnabled(True)
        self._search.setMinimumWidth(int(FieldWidth.LG))
        self._search.textChanged.connect(self._on_search_changed)
        bar_row.addWidget(self._search)
        self._filters_host = QHBoxLayout()
        self._filters_host.setSpacing(Spacing.SM)
        bar_row.addLayout(self._filters_host)
        bar_row.addStretch(1)
        self._refresh_btn = ghost_button(self._t.gettext("md.refresh"))
        bar_row.addWidget(self._refresh_btn)
        bar.body.addLayout(bar_row)
        root.addWidget(bar)

        # ---- table ----
        self._table = QTableWidget(0, len(columns) + 1)  # +1 for actions
        headers = [self._t.gettext(c.title) for c in columns] + [self._t.gettext("md.actions")]
        self._table.setHorizontalHeaderLabels(headers)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        hh = self._table.horizontalHeader()
        for i, col in enumerate(columns):
            if col.stretch:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            elif col.width:
                self._table.setColumnWidth(i, col.width)
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
            else:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        # Keep the stretch (name/party) column legible on narrow windows: give
        # every section a floor so the fixed action column can't starve it.
        hh.setMinimumSectionSize(90)
        hh.setSectionResizeMode(len(columns), QHeaderView.ResizeMode.Fixed)
        # Action column width adapts to how many actions there are. With 3+
        # actions the extras collapse into a ⋯ menu, so one inline + kebab fits
        # in ~150px instead of three full buttons crowding the row.
        n_actions = sum(x is not None for x in (on_view, on_edit, on_toggle_active))
        act_w = 150 if n_actions > 2 else max(116, 84 * max(n_actions, 1) + 20)
        self._table.setColumnWidth(len(columns), act_w)
        self._table.verticalHeader().setDefaultSectionSize(ControlSize.TABLE_ROW_HEIGHT + 6)
        self._table.doubleClicked.connect(self._on_row_double_clicked)
        root.addWidget(self._table, stretch=1)

    # ---- public API -----------------------------------------------------

    def add_filter(self, combo: QComboBox) -> None:
        self._filters_host.addWidget(combo)

    def connect_refresh(self, handler: Callable[[], None]) -> None:
        self._refresh_btn.clicked.connect(lambda: handler())

    def set_rows(self, rows: list[dict]) -> None:
        self._rows = rows
        self._render()

    def _on_search_changed(self, text: str) -> None:
        self._filter_text = (text or "").strip().lower()
        self._render()

    def _visible_rows(self) -> list[dict]:
        if not self._filter_text:
            return self._rows
        out = []
        for r in self._rows:
            hay = " ".join(str(r.get(c.key, "")) for c in self._columns).lower()
            if self._filter_text in hay:
                out.append(r)
        return out

    def _render(self) -> None:
        rows = self._visible_rows()
        self._count.setText(self._t.gettext("md.count").replace("{n}", str(len(rows))))
        self._table.setRowCount(len(rows))
        for r, data in enumerate(rows):
            for c, col in enumerate(self._columns):
                value = data.get(col.key)
                if col.kind == "status":
                    active = bool(value)
                    cell = self._status_cell(active)
                    self._table.setCellWidget(r, c, cell)
                    continue
                text = "" if value is None else str(value)
                item = QTableWidgetItem(text)
                if col.align == "r":
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                elif col.align == "c":
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(r, c, item)
            self._table.setCellWidget(r, len(self._columns), self._action_cell(data))

    def _status_cell(self, active: bool) -> QWidget:
        host = QWidget()
        lay = QHBoxLayout(host)
        lay.setContentsMargins(Spacing.SM, 0, Spacing.SM, 0)
        lay.addWidget(chip(self._t.gettext("md.active" if active else "md.inactive"),
                           "success" if active else "neutral"))
        lay.addStretch(1)
        return host

    def _action_cell(self, data: dict) -> QWidget:
        # Build the ordered action list (highest priority first), then render as
        # inline buttons (≤2) or one inline + a ⋯ overflow menu (3+) so the
        # column never clips at 1366×768 (§G/§15).
        actions: list[tuple[str, Callable[[], None], str | None]] = []
        if self._on_view is not None:
            actions.append((self._t.gettext(self._view_label_key),
                            lambda d=data: self._on_view(d), "accent"))
        if self._on_edit is not None:
            actions.append((self._t.gettext("md.edit"),
                            lambda d=data: self._on_edit(d), None))
        if self._on_toggle is not None:
            active = bool(data.get("is_active", 1))
            actions.append((self._t.gettext("md.deactivate" if active else "md.activate"),
                            lambda d=data: self._on_toggle(d), None))

        row = RowActions()
        if len(actions) <= 2:
            for label, handler, variant in actions:
                row.add_button(label, handler, variant=variant)
        else:
            first_label, first_handler, first_variant = actions[0]
            row.add_button(first_label, first_handler, variant=first_variant)
            for label, handler, _variant in actions[1:]:
                row.add_menu_action(label, handler)
        return row

    def _on_row_double_clicked(self, index) -> None:
        rows = self._visible_rows()
        if self._on_edit is not None and 0 <= index.row() < len(rows):
            self._on_edit(rows[index.row()])

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext(self._title_key))
        self._search.setPlaceholderText(translator.gettext("md.search"))
        self._refresh_btn.setText(translator.gettext("md.refresh"))
        if self._new_btn is not None:
            from zenith_business.ui.components import escape_amp
            self._new_btn.setText(escape_amp(translator.gettext(self._new_label_key)))
        headers = [translator.gettext(c.title) for c in self._columns] + \
            [translator.gettext("md.actions")]
        self._table.setHorizontalHeaderLabels(headers)
        self._render()


class FormDialog(QDialog):
    """Sectioned create/edit dialog: a fixed header, a **scrollable body**, and a
    **pinned Save/Cancel footer**, height-clamped to the available screen (§14, §I).

    The public API (``add_section`` / ``add_field`` / ``set_submit`` /
    ``set_error`` / ``clear_error`` and the ``_body`` layout used by a few
    callers) is unchanged; only the internal composition gained a
    :class:`QScrollArea` and a pinned footer so Save/Cancel can never be pushed
    off-screen on small displays (1366×768). Enter still submits via the default
    button.
    """

    def __init__(self, translator: Translator, title: str,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._t = translator
        self.setWindowTitle(title)
        self.setMinimumWidth(560)
        if parent is not None:
            self.setLayoutDirection(parent.layoutDirection())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- fixed header (title + error region) ----
        header = QWidget()
        header.setProperty("role", "dialog-header")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(Spacing.XL, Spacing.LG, Spacing.XL, Spacing.SM)
        hl.setSpacing(Spacing.XS)
        hl.addWidget(page_title(title))
        self._error = error_label("")
        self._error.setVisible(False)
        hl.addWidget(self._error)
        outer.addWidget(header)

        # ---- scrollable body (grows here; scrolls when tall) ----
        # NB: no bare "background: transparent" widget stylesheet here — that
        # would cascade onto child inputs/buttons and strip their app-QSS fills.
        # The body simply inherits the dialog's background (BACKGROUND).
        inner = QWidget()
        self._body = QVBoxLayout(inner)
        self._body.setContentsMargins(Spacing.XL, Spacing.MD, Spacing.XL, Spacing.LG)
        self._body.setSpacing(Spacing.MD)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(inner)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll, 1)
        self._scroll = scroll

        # ---- pinned footer (Save/Cancel — never scrolls away) ----
        footer = QWidget()
        footer.setProperty("role", "dialog-footer")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(Spacing.XL, Spacing.SM, Spacing.XL, Spacing.SM)
        fl.setSpacing(Spacing.SM)
        fl.addStretch(1)
        self._save = primary_button(self._t.gettext("action.save"))
        self._cancel = secondary_button(self._t.gettext("action.cancel"))
        fl.addWidget(self._cancel)
        fl.addWidget(self._save)
        self._save.setDefault(True)
        self._save.setAutoDefault(True)
        self._save.clicked.connect(self._on_save)
        self._cancel.clicked.connect(self.reject)
        outer.addWidget(footer)

        self._on_submit: Callable[[], None] | None = None

    # ---- keep Save/Cancel on-screen at any resolution -------------------

    def showEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        self._clamp_to_screen()

    def _clamp_to_screen(self) -> None:
        """Never exceed the available screen; re-centre within the work area."""
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        max_h = int(avail.height() * 0.92)
        max_w = int(avail.width() * 0.96)
        self.setMaximumHeight(max_h)
        if self.height() > max_h:
            self.resize(min(self.width(), max_w), max_h)
        frame = self.frameGeometry()
        frame.moveCenter(avail.center())
        if frame.top() < avail.top():
            frame.moveTop(avail.top())
        if frame.left() < avail.left():
            frame.moveLeft(avail.left())
        self.move(frame.topLeft())

    def add_section(self, title: str) -> QGridLayout:
        from zenith_business.ui.components import section_title
        self._body.addWidget(section_title(title))
        grid = QGridLayout()
        grid.setHorizontalSpacing(Spacing.FIELD_HGAP)
        grid.setVerticalSpacing(Spacing.FIELD_VGAP)
        self._body.addLayout(grid)
        return grid

    def add_field(self, grid: QGridLayout, row: int, col: int, label: str,
                  widget: QWidget, *, width: FieldWidth | None = None) -> QWidget:
        cell = QVBoxLayout()
        cell.setSpacing(Spacing.XXS)
        cell.addWidget(field_label(label))
        if width is not None:
            widget.setMinimumWidth(int(width))
        cell.addWidget(widget)
        holder = QWidget()
        holder.setLayout(cell)
        grid.addWidget(holder, row, col)
        return widget

    def set_submit(self, handler: Callable[[], None]) -> None:
        self._on_submit = handler

    def _on_save(self) -> None:
        self.clear_error()
        if self._on_submit is not None:
            self._on_submit()

    def set_error(self, message: str) -> None:
        self._error.setText(message)
        self._error.setVisible(True)

    def clear_error(self) -> None:
        self._error.setVisible(False)
