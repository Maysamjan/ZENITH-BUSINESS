"""Stage 06 inventory screens — Inventory, Adjustment, Transfer, Movement history.

Every number these screens show is the signed sum of the ``inventory_movements``
ledger read through :class:`InventoryService`; none of them stores or edits a
stock figure directly. Stock only ever changes by recording a movement, so what
the operator sees here is exactly what a sale is validated against.

Same LOCKED design system, nav, Vazirmatn and EN/Dari RTL as every other screen.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.exceptions import ZenithError
from zenith_business.core.i18n import Translator
from zenith_business.core.money import D, format_money
from zenith_business.ui.components import (
    Card,
    LabeledField,
    apply_shadow,
    chip,
    escape_amp,
    eyebrow,
    page_title,
    primary_button,
    secondary_button,
    standard_icon,
)
from zenith_business.ui.design.tokens import ControlSize, FieldWidth, Spacing
from zenith_business.ui.widgets.search_selector import SearchRow, SearchSelector

#: Movement types offered in the history filter, in ledger order.
MOVEMENT_TYPES = ("OPENING", "PURCHASE", "SALE", "SALE_RETURN", "PURCHASE_RETURN",
                  "ADJUSTMENT_IN", "ADJUSTMENT_OUT", "TRANSFER_IN", "TRANSFER_OUT")


def _qty(value) -> str:
    """Quantities read like the rest of the app's numbers."""
    return format_money(value) if str(value or "").strip() else ""


def stock_status_key(current, minimum) -> str:
    """``inv.status_*`` key for a stock level — out, low, or in stock."""
    cur, low = D(current or 0), D(minimum or 0)
    if cur <= 0:
        return "inv.status_out"
    return "inv.status_low" if cur <= low else "inv.status_ok"


class _StockPageBase(QWidget):
    """Shared chrome: title, transparent wrapper helper, error/status line."""

    def __init__(self, context, translator: Translator, *,
                 on_close: Callable[[], None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = context
        self._t = translator
        self._on_close = on_close
        self.setProperty("role", "workspace")

    def _wrap(self, layout, name: str) -> QWidget:
        """Transparent container, scoped by objectName.

        A bare ``background: transparent`` widget stylesheet cascades onto child
        controls and strips their fills, so the rule is always id-scoped.
        """
        w = QWidget(); w.setLayout(layout); w.setObjectName(name)
        w.setStyleSheet(f"#{name} {{ background: transparent; }}")
        return w

    def _titlebar(self, key: str) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(Spacing.MD)
        self._title = page_title(self._t.gettext(key))
        row.addWidget(self._title); row.addStretch(1)
        return row

    def _build_action_bar(self, *, primary_key: str | None = None,
                          on_primary: Callable[[], None] | None = None) -> QWidget:
        bar = QFrame(); bar.setProperty("role", "actionbar")
        apply_shadow(bar, blur=18, y=3, alpha=30)
        row = QHBoxLayout(bar)
        row.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.SM)
        self._status = QLabel(""); self._status.setProperty("role", "secondary")
        self._error = QLabel(""); self._error.setProperty("role", "error")
        self._error.setVisible(False)
        row.addWidget(self._status); row.addWidget(self._error); row.addStretch(1)
        self._primary_btn = None
        if primary_key is not None:
            self._primary_btn = primary_button(self._t.gettext(primary_key))
            self._primary_btn.setIcon(standard_icon("save"))
            if on_primary is not None:
                self._primary_btn.clicked.connect(lambda: on_primary())
            row.addWidget(self._primary_btn)
        self._close_btn = secondary_button(self._t.gettext("s4.act_close"))
        self._close_btn.setIcon(standard_icon("close"))
        if self._on_close is not None:
            self._close_btn.clicked.connect(lambda: self._on_close())
        row.addWidget(self._close_btn)
        return bar

    def _show_error(self, message: str) -> None:
        self._error.setText(message); self._error.setVisible(True)
        self._status.setText("")

    def clear_error(self) -> None:
        self._error.setVisible(False)

    def _set_status(self, message: str) -> None:
        self.clear_error(); self._status.setText(message)

    def _table_of(self, columns: list[tuple[str, str, str]], *, stretch: str) -> QTableWidget:
        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels([self._t.gettext(h) for h, _k, _a in columns])
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setMinimumHeight(160)
        hh = table.horizontalHeader(); hh.setHighlightSections(False)
        for i, (_h, key, _a) in enumerate(columns):
            if key == stretch:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            elif key == "status":
                # The status cell is a chip WIDGET, and ResizeToContents measures
                # only item text — it would size this column to zero and clip the
                # chip. Give it a width that fits the longest label in either
                # language.
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                table.setColumnWidth(i, 140)
            else:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setDefaultSectionSize(ControlSize.TABLE_ROW_HEIGHT + 4)
        return table

    def _fill(self, table: QTableWidget, columns, rows, *,
              money_keys: set[str], status_key: str | None = None) -> None:
        table.setRowCount(0)
        table.setRowCount(len(rows))
        for r, data in enumerate(rows):
            for c, (_h, key, align) in enumerate(columns):
                if status_key is not None and key == status_key:
                    table.setCellWidget(r, c, self._status_chip(data))
                    continue
                value = data.get(key)
                text = _qty(value) if key in money_keys else ("" if value is None else str(value))
                item = QTableWidgetItem(text)
                a = (Qt.AlignmentFlag.AlignRight if align == "r"
                     else Qt.AlignmentFlag.AlignCenter if align == "c"
                     else Qt.AlignmentFlag.AlignLeft)
                item.setTextAlignment(a | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(r, c, item)

    def _status_chip(self, row: dict) -> QWidget:
        key = stock_status_key(row.get("current", row.get("quantity")),
                               row.get("minimum", row.get("reorder_level")))
        kind = {"inv.status_ok": "success", "inv.status_low": "warning",
                "inv.status_out": "danger"}[key]
        holder = QWidget(); lay = QHBoxLayout(holder)
        lay.setContentsMargins(Spacing.XS, 0, Spacing.XS, 0)
        lay.addWidget(chip(self._t.gettext(key), kind)); lay.addStretch(1)
        return holder

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._close_btn.setText(escape_amp(translator.gettext("s4.act_close")))


# ---------------------------------------------------------------- Inventory

class InventoryStockPage(_StockPageBase):
    """Live stock per item: opening, current, warehouses and low-stock state."""

    COLUMNS = [("inv.col_item_code", "item_code", "l"),
               ("inv.col_item_name", "item_name", "l"),
               ("inv.col_unit", "unit", "l"),
               ("inv.col_opening", "opening", "r"),
               ("inv.col_current", "current", "r"),
               ("inv.col_minimum", "minimum", "r"),
               ("inv.col_warehouse", "warehouses", "l"),
               ("inv.col_status", "status", "c")]
    MONEY = {"opening", "current", "minimum"}

    def __init__(self, context, translator, *, on_close=None, parent=None) -> None:
        super().__init__(context, translator, on_close=on_close, parent=parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.PAGE_MARGIN, Spacing.SM,
                                Spacing.PAGE_MARGIN, Spacing.SM)
        root.setSpacing(Spacing.SM)
        root.addLayout(self._titlebar("inv.stock_title"))
        root.addWidget(self._build_filter())
        self._table = self._table_of(self.COLUMNS, stretch="item_name")
        root.addWidget(self._table, stretch=1)
        root.addWidget(self._build_action_bar())
        self.reload()

    def _build_filter(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "navy"); apply_shadow(card)
        card.body.setContentsMargins(Spacing.CARD_PAD_H, Spacing.SM,
                                     Spacing.CARD_PAD_H, Spacing.SM)
        row = QHBoxLayout(); row.setSpacing(Spacing.MD)
        self._search = QLineEdit()
        self._search.setPlaceholderText(self._t.gettext("md.search"))
        self._search.textChanged.connect(lambda _t: self._render())
        self._search_field = LabeledField(self._t.gettext("md.search"), self._search,
                                          width=FieldWidth.LG, compact=True)
        self._low_only = QComboBox()
        self._low_only.addItem(self._t.gettext("inv.filter_all_items"), False)
        self._low_only.addItem(self._t.gettext("inv.status_low"), True)
        self._low_only.currentIndexChanged.connect(lambda _i: self._render())
        self._low_field = LabeledField(self._t.gettext("inv.col_status"), self._low_only,
                                       width=FieldWidth.MD, compact=True)
        row.addWidget(self._search_field); row.addWidget(self._low_field); row.addStretch(1)
        card.body.addWidget(self._wrap(row, "InvStockFilter"))
        return card

    def reload(self) -> None:
        self._rows = self._ctx.inventory.stock_overview()
        self._render()

    def _render(self) -> None:
        term = (self._search.text() or "").strip().lower()
        rows = self._rows
        if self._low_only.currentData():
            rows = [r for r in rows if r["low"]]
        if term:
            rows = [r for r in rows
                    if term in (r["item_code"] or "").lower()
                    or term in (r["item_name"] or "").lower()]
        self._fill(self._table, self.COLUMNS, rows, money_keys=self.MONEY,
                   status_key="status")
        self._set_status(self._t.gettext("inv.items_count").replace("{n}", str(len(rows))))

    def retranslate(self, translator: Translator) -> None:
        super().retranslate(translator)
        self._title.setText(translator.gettext("inv.stock_title"))
        self._search_field.set_label(translator.gettext("md.search"))
        self._low_field.set_label(translator.gettext("inv.col_status"))
        self._table.setHorizontalHeaderLabels(
            [translator.gettext(h) for h, _k, _a in self.COLUMNS])
        self.reload()


# --------------------------------------------------------- Stock Adjustment

class StockAdjustmentPage(_StockPageBase):
    """Increase or decrease stock with a mandatory reason, always as a movement."""

    def __init__(self, context, translator, *, on_close=None, parent=None) -> None:
        super().__init__(context, translator, on_close=on_close, parent=parent)
        self._item_id = None
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.PAGE_MARGIN, Spacing.SM,
                                Spacing.PAGE_MARGIN, Spacing.SM)
        root.setSpacing(Spacing.SM)
        root.addLayout(self._titlebar("inv.adjust_title"))
        root.addWidget(self._build_form())
        root.addStretch(1)
        root.addWidget(self._build_action_bar(primary_key="inv.act_apply",
                                              on_primary=self.apply))

    def _build_form(self) -> QWidget:
        t = self._t
        card = Card(role="section"); card.setProperty("accent", "brand"); apply_shadow(card)
        card.body.setContentsMargins(Spacing.CARD_PAD_H, Spacing.MD,
                                     Spacing.CARD_PAD_H, Spacing.MD)
        col = QVBoxLayout(); col.setSpacing(Spacing.MD)

        top = QHBoxLayout(); top.setSpacing(Spacing.MD)
        self._selector = SearchSelector(self._ctx.item_search,
                                        placeholder=t.gettext("s4.item_search_ph"),
                                        display_index=1, panel_width=460)
        self._selector.rowSelected.connect(self._on_item)
        self._item_field = LabeledField(t.gettext("inv.f_item"), self._selector,
                                        width=FieldWidth.LG)
        self._wh_combo = QComboBox()
        self._wh_combo.currentIndexChanged.connect(lambda _i: self._refresh_current())
        self._wh_field = LabeledField(t.gettext("inv.f_warehouse"), self._wh_combo,
                                      width=FieldWidth.MD)
        top.addWidget(self._item_field); top.addWidget(self._wh_field); top.addStretch(1)
        self._current_lbl = eyebrow("")
        top.addWidget(self._current_lbl)
        col.addLayout(top)

        mid = QHBoxLayout(); mid.setSpacing(Spacing.MD)
        self._dir_in = QRadioButton(t.gettext("inv.dir_in"))
        self._dir_out = QRadioButton(t.gettext("inv.dir_out"))
        self._dir_group = QButtonGroup(self); self._dir_group.setExclusive(True)
        self._dir_group.addButton(self._dir_in); self._dir_group.addButton(self._dir_out)
        self._dir_in.setChecked(True)
        for b in (self._dir_in, self._dir_out):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dir_label = QLabel(t.gettext("inv.f_direction"))
        self._dir_label.setProperty("role", "field-label")
        dirbox = QVBoxLayout(); dirbox.setSpacing(Spacing.XXS)
        dirbox.addWidget(self._dir_label)
        drow = QHBoxLayout(); drow.setSpacing(Spacing.MD)
        drow.addWidget(self._dir_in); drow.addWidget(self._dir_out); drow.addStretch(1)
        dirbox.addLayout(drow)
        mid.addWidget(self._wrap(dirbox, "InvAdjDir"))
        self._qty_edit = QLineEdit()
        self._qty_field = LabeledField(t.gettext("inv.f_quantity"), self._qty_edit,
                                       width=FieldWidth.SM)
        mid.addWidget(self._qty_field); mid.addStretch(1)
        col.addLayout(mid)

        self._reason_edit = QLineEdit()
        self._reason_edit.setPlaceholderText(t.gettext("inv.f_reason_ph"))
        self._reason_field = LabeledField(t.gettext("inv.f_reason"), self._reason_edit,
                                          width=FieldWidth.LG)
        col.addWidget(self._reason_field)

        card.body.addWidget(self._wrap(col, "InvAdjustForm"))
        self.reload()
        return card

    def _on_item(self, row: SearchRow) -> None:
        self._item_id = row.payload.get("item_id")
        self._refresh_current()

    def _refresh_current(self) -> None:
        if self._item_id is None or self._wh_combo.currentData() is None:
            self._current_lbl.setText("")
            return
        qty = self._ctx.inventory.on_hand(self._item_id, self._wh_combo.currentData())
        self._current_lbl.setText(
            self._t.gettext("inv.current_stock_is").replace("{qty}", format_money(qty)))

    def reload(self) -> None:
        current = self._wh_combo.currentData()
        self._wh_combo.clear()
        for w in self._ctx.warehouses_repo.list_active():
            self._wh_combo.addItem(w["name"], w["id"])
        i = self._wh_combo.findData(current)
        if i >= 0:
            self._wh_combo.setCurrentIndex(i)
        self._refresh_current()

    def apply(self) -> None:
        self.clear_error()
        if self._item_id is None:
            self._show_error(self._t.gettext("inv.msg_pick_item")); return
        if not (self._reason_edit.text() or "").strip():
            self._show_error(self._t.gettext("inv.msg_need_reason")); return
        try:
            qty = D(self._qty_edit.text() or "0")
        except Exception:
            qty = D(0)
        if qty <= 0:
            self._show_error(self._t.gettext("inv.msg_bad_qty")); return
        delta = qty if self._dir_in.isChecked() else -qty
        try:
            self._ctx.inventory.adjust(
                item_id=self._item_id, warehouse_id=self._wh_combo.currentData(),
                delta=str(delta), reason=self._reason_edit.text())
        except ZenithError as exc:
            self._show_error(getattr(exc, "user_message", None) or str(exc)); return
        new_qty = self._ctx.inventory.on_hand(self._item_id, self._wh_combo.currentData())
        self._set_status(self._t.gettext("inv.msg_adjusted")
                         .replace("{qty}", format_money(new_qty)))
        self._qty_edit.clear(); self._reason_edit.clear()
        self._refresh_current()

    def retranslate(self, translator: Translator) -> None:
        super().retranslate(translator)
        self._title.setText(translator.gettext("inv.adjust_title"))
        self._item_field.set_label(translator.gettext("inv.f_item"))
        self._wh_field.set_label(translator.gettext("inv.f_warehouse"))
        self._qty_field.set_label(translator.gettext("inv.f_quantity"))
        self._reason_field.set_label(translator.gettext("inv.f_reason"))
        self._reason_edit.setPlaceholderText(translator.gettext("inv.f_reason_ph"))
        self._dir_label.setText(translator.gettext("inv.f_direction"))
        self._dir_in.setText(translator.gettext("inv.dir_in"))
        self._dir_out.setText(translator.gettext("inv.dir_out"))
        if self._primary_btn is not None:
            self._primary_btn.setText(escape_amp(translator.gettext("inv.act_apply")))
        self._refresh_current()


# ------------------------------------------------------- Warehouse Transfer

class WarehouseTransferPage(_StockPageBase):
    """Move stock between warehouses as one atomic OUT+IN pair."""

    def __init__(self, context, translator, *, on_close=None, parent=None) -> None:
        super().__init__(context, translator, on_close=on_close, parent=parent)
        self._item_id = None
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.PAGE_MARGIN, Spacing.SM,
                                Spacing.PAGE_MARGIN, Spacing.SM)
        root.setSpacing(Spacing.SM)
        root.addLayout(self._titlebar("inv.transfer_title"))
        root.addWidget(self._build_form())
        root.addStretch(1)
        root.addWidget(self._build_action_bar(primary_key="inv.act_transfer",
                                              on_primary=self.transfer))

    def _build_form(self) -> QWidget:
        t = self._t
        card = Card(role="section"); card.setProperty("accent", "teal"); apply_shadow(card)
        card.body.setContentsMargins(Spacing.CARD_PAD_H, Spacing.MD,
                                     Spacing.CARD_PAD_H, Spacing.MD)
        col = QVBoxLayout(); col.setSpacing(Spacing.MD)

        top = QHBoxLayout(); top.setSpacing(Spacing.MD)
        self._selector = SearchSelector(self._ctx.item_search,
                                        placeholder=t.gettext("s4.item_search_ph"),
                                        display_index=1, panel_width=460)
        self._selector.rowSelected.connect(self._on_item)
        self._item_field = LabeledField(t.gettext("inv.f_item"), self._selector,
                                        width=FieldWidth.LG)
        top.addWidget(self._item_field); top.addStretch(1)
        self._avail_lbl = eyebrow("")
        top.addWidget(self._avail_lbl)
        col.addLayout(top)

        mid = QHBoxLayout(); mid.setSpacing(Spacing.MD)
        self._from_combo = QComboBox()
        self._from_combo.currentIndexChanged.connect(lambda _i: self._refresh_available())
        self._to_combo = QComboBox()
        self._from_field = LabeledField(t.gettext("inv.f_from"), self._from_combo,
                                        width=FieldWidth.MD)
        self._to_field = LabeledField(t.gettext("inv.f_to"), self._to_combo,
                                      width=FieldWidth.MD)
        self._qty_edit = QLineEdit()
        self._qty_field = LabeledField(t.gettext("inv.f_quantity"), self._qty_edit,
                                       width=FieldWidth.SM)
        for w in (self._from_field, self._to_field, self._qty_field):
            mid.addWidget(w)
        mid.addStretch(1)
        col.addLayout(mid)

        self._note_edit = QLineEdit()
        self._note_field = LabeledField(t.gettext("inv.f_note"), self._note_edit,
                                        width=FieldWidth.LG)
        col.addWidget(self._note_field)

        card.body.addWidget(self._wrap(col, "InvTransferForm"))
        self.reload()
        return card

    def _on_item(self, row: SearchRow) -> None:
        self._item_id = row.payload.get("item_id")
        self._refresh_available()

    def _refresh_available(self) -> None:
        if self._item_id is None or self._from_combo.currentData() is None:
            self._avail_lbl.setText("")
            return
        qty = self._ctx.inventory.on_hand(self._item_id, self._from_combo.currentData())
        self._avail_lbl.setText(
            self._t.gettext("inv.available_here").replace("{qty}", format_money(qty)))

    def reload(self) -> None:
        src, dst = self._from_combo.currentData(), self._to_combo.currentData()
        for combo in (self._from_combo, self._to_combo):
            combo.clear()
            for w in self._ctx.warehouses_repo.list_active():
                combo.addItem(w["name"], w["id"])
        for combo, keep in ((self._from_combo, src), (self._to_combo, dst)):
            i = combo.findData(keep)
            if i >= 0:
                combo.setCurrentIndex(i)
        if (self._to_combo.count() > 1
                and self._to_combo.currentIndex() == self._from_combo.currentIndex()):
            self._to_combo.setCurrentIndex(1)
        self._refresh_available()

    def transfer(self) -> None:
        self.clear_error()
        if self._item_id is None:
            self._show_error(self._t.gettext("inv.msg_pick_item")); return
        src, dst = self._from_combo.currentData(), self._to_combo.currentData()
        if src == dst:
            self._show_error(self._t.gettext("inv.msg_same_wh")); return
        try:
            qty = D(self._qty_edit.text() or "0")
        except Exception:
            qty = D(0)
        if qty <= 0:
            self._show_error(self._t.gettext("inv.msg_bad_qty")); return
        try:
            self._ctx.inventory.transfer(
                item_id=self._item_id, from_warehouse_id=src, to_warehouse_id=dst,
                quantity_moved=str(qty), notes=self._note_edit.text())
        except ZenithError as exc:
            self._show_error(getattr(exc, "user_message", None) or str(exc)); return
        self._set_status(self._t.gettext("inv.msg_transferred")
                         .replace("{qty}", format_money(qty))
                         .replace("{from_wh}", self._from_combo.currentText())
                         .replace("{from_qty}", format_money(
                             self._ctx.inventory.on_hand(self._item_id, src)))
                         .replace("{to_wh}", self._to_combo.currentText())
                         .replace("{to_qty}", format_money(
                             self._ctx.inventory.on_hand(self._item_id, dst))))
        self._qty_edit.clear(); self._note_edit.clear()
        self._refresh_available()

    def retranslate(self, translator: Translator) -> None:
        super().retranslate(translator)
        self._title.setText(translator.gettext("inv.transfer_title"))
        self._item_field.set_label(translator.gettext("inv.f_item"))
        self._from_field.set_label(translator.gettext("inv.f_from"))
        self._to_field.set_label(translator.gettext("inv.f_to"))
        self._qty_field.set_label(translator.gettext("inv.f_quantity"))
        self._note_field.set_label(translator.gettext("inv.f_note"))
        if self._primary_btn is not None:
            self._primary_btn.setText(escape_amp(translator.gettext("inv.act_transfer")))
        self._refresh_available()


# --------------------------------------------------- Stock Movement history

class StockMovementPage(_StockPageBase):
    """Every stock change, with its document, user and reason."""

    COLUMNS = [("inv.col_date", "movement_date", "l"),
               ("inv.col_item_code", "item_code", "l"),
               ("inv.col_item_name", "item_name", "l"),
               ("inv.col_warehouse", "warehouse_name", "l"),
               ("inv.col_type", "type_label", "l"),
               ("inv.col_in", "qty_in", "r"),
               ("inv.col_out", "qty_out", "r"),
               ("inv.col_document", "document_no", "l"),
               ("inv.col_user", "user_name", "l"),
               ("inv.col_note", "notes", "l")]
    MONEY = {"qty_in", "qty_out"}

    def __init__(self, context, translator, *, on_close=None, parent=None) -> None:
        super().__init__(context, translator, on_close=on_close, parent=parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.PAGE_MARGIN, Spacing.SM,
                                Spacing.PAGE_MARGIN, Spacing.SM)
        root.setSpacing(Spacing.SM)
        root.addLayout(self._titlebar("inv.movements_title"))
        root.addWidget(self._build_filter())
        self._table = self._table_of(self.COLUMNS, stretch="item_name")
        root.addWidget(self._table, stretch=1)
        root.addWidget(self._build_action_bar())
        self.reload()

    def _build_filter(self) -> QWidget:
        t = self._t
        card = Card(role="section"); card.setProperty("accent", "navy"); apply_shadow(card)
        card.body.setContentsMargins(Spacing.CARD_PAD_H, Spacing.SM,
                                     Spacing.CARD_PAD_H, Spacing.SM)
        row = QHBoxLayout(); row.setSpacing(Spacing.MD)
        self._item_combo = QComboBox()
        self._wh_combo = QComboBox()
        self._type_combo = QComboBox()
        for c in (self._item_combo, self._wh_combo, self._type_combo):
            c.currentIndexChanged.connect(lambda _i: self.reload())
        self._item_field = LabeledField(t.gettext("inv.f_item"), self._item_combo,
                                        width=FieldWidth.MD, compact=True)
        self._wh_field = LabeledField(t.gettext("inv.f_warehouse"), self._wh_combo,
                                      width=FieldWidth.MD, compact=True)
        self._type_field = LabeledField(t.gettext("inv.col_type"), self._type_combo,
                                        width=FieldWidth.MD, compact=True)
        for w in (self._item_field, self._wh_field, self._type_field):
            row.addWidget(w)
        row.addStretch(1)
        card.body.addWidget(self._wrap(row, "InvMoveFilter"))
        self._populate_filters()
        return card

    def _populate_filters(self) -> None:
        t = self._t
        blocked = [self._item_combo, self._wh_combo, self._type_combo]
        for c in blocked:
            c.blockSignals(True)
        keep = (self._item_combo.currentData(), self._wh_combo.currentData(),
                self._type_combo.currentData())
        self._item_combo.clear()
        self._item_combo.addItem(t.gettext("inv.filter_all_items"), None)
        for it in self._ctx.items.list():
            self._item_combo.addItem(f"{it['item_code']} — {it['name']}", it["id"])
        self._wh_combo.clear()
        self._wh_combo.addItem(t.gettext("inv.filter_all_wh"), None)
        for w in self._ctx.warehouses_repo.list_active():
            self._wh_combo.addItem(w["name"], w["id"])
        self._type_combo.clear()
        self._type_combo.addItem(t.gettext("inv.filter_all_types"), None)
        for mt in MOVEMENT_TYPES:
            self._type_combo.addItem(t.gettext(f"inv.mt_{mt}"), mt)
        for combo, value in zip(blocked, keep):
            i = combo.findData(value)
            if i >= 0:
                combo.setCurrentIndex(i)
        for c in blocked:
            c.blockSignals(False)

    def reload(self) -> None:
        rows = self._ctx.inventory.movement_history(
            item_id=self._item_combo.currentData(),
            warehouse_id=self._wh_combo.currentData(),
            movement_type=self._type_combo.currentData())
        for r in rows:
            r["type_label"] = self._t.gettext(f"inv.mt_{r['movement_type']}")
        self._fill(self._table, self.COLUMNS, rows, money_keys=self.MONEY)
        self._set_status(self._t.gettext("inv.empty") if not rows
                         else self._t.gettext("inv.items_count")
                         .replace("{n}", str(len(rows))))

    def retranslate(self, translator: Translator) -> None:
        super().retranslate(translator)
        self._title.setText(translator.gettext("inv.movements_title"))
        self._item_field.set_label(translator.gettext("inv.f_item"))
        self._wh_field.set_label(translator.gettext("inv.f_warehouse"))
        self._type_field.set_label(translator.gettext("inv.col_type"))
        self._table.setHorizontalHeaderLabels(
            [translator.gettext(h) for h, _k, _a in self.COLUMNS])
        self._populate_filters()
        self.reload()
