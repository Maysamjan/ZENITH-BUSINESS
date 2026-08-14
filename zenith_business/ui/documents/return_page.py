"""Stage 04 return entry — Sales Returns and Purchase Returns.

A real from-original return workspace: load a posted source invoice by its
document number (or open it directly from a list), see each line's still-
returnable quantity (sold/purchased − already returned), enter the quantity to
return, and post. The atomic Stage 04 service applies the over-return guard, the
signed inventory movement, the reversing ledger entry and the party balance — all
in one transaction. Quantities are Decimal end to end.
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.exceptions import ZenithError
from zenith_business.core.i18n import Translator
from zenith_business.core.money import D, format_money
from zenith_business.services.purchase_documents import PurchaseReturnLine
from zenith_business.services.sales_documents import ReturnLine
from zenith_business.ui.components import (
    Card,
    apply_shadow,
    escape_amp,
    field_label,
    horizontal_divider,
    muted,
    page_title,
    primary_button,
    secondary_button,
)
from zenith_business.ui.design.tokens import ControlSize, FieldWidth, Spacing

R_NO, R_CODE, R_NAME, R_UNIT, R_SOLD, R_RETURNABLE, R_RETURN = range(7)


class ReturnEntryPage(QWidget):
    """Real from-original Sales / Purchase return entry."""

    def __init__(
        self,
        context,
        translator: Translator,
        *,
        mode: str,  # 'sales_return' | 'purchase_return'
        on_print: Callable[[int], None] | None = None,
        on_close: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._ctx = context
        self._t = translator
        self._mode = mode
        self._on_print = on_print
        self._on_close = on_close
        self._source_id: int | None = None
        self._lines: list[dict] = []
        self._return_edits: list[QLineEdit] = []
        self._last_saved_id: int | None = None

        self.setProperty("role", "workspace")
        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        root.setSpacing(Spacing.SM)
        root.addLayout(self._build_titlebar())
        root.addWidget(self._build_source_card())
        root.addWidget(self._build_grid_card(), stretch=1)
        root.addWidget(self._build_action_bar())

    # ---- title -----------------------------------------------------------

    def _title_key(self) -> str:
        return "s4.return_sale_title" if self._mode == "sales_return" else "s4.return_purchase_title"

    def _build_titlebar(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(Spacing.MD)
        self._title = page_title(self._t.gettext(self._title_key()))
        row.addWidget(self._title); row.addStretch(1)
        self._status_msg = muted("")
        row.addWidget(self._status_msg)
        return row

    def _build_source_card(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "navy"); apply_shadow(card)
        card.body.setSpacing(Spacing.SM)
        row = QHBoxLayout(); row.setSpacing(Spacing.SM)
        cell = QVBoxLayout(); cell.setSpacing(Spacing.XXS)
        self._src_label = field_label(self._t.gettext("s4.source_doc"))
        cell.addWidget(self._src_label)
        self._src_edit = QLineEdit()
        self._src_edit.setPlaceholderText(self._t.gettext("s4.source_ph"))
        self._src_edit.setMinimumWidth(int(FieldWidth.MD))
        self._src_edit.returnPressed.connect(self._load_source)
        cell.addWidget(self._src_edit)
        holder = QWidget(); holder.setLayout(cell); holder.setStyleSheet("background: transparent;")
        row.addWidget(holder)
        self._load_btn = secondary_button(self._t.gettext("s4.load"))
        self._load_btn.clicked.connect(self._load_source)
        row.addWidget(self._load_btn, alignment=Qt.AlignmentFlag.AlignBottom)

        reason_cell = QVBoxLayout(); reason_cell.setSpacing(Spacing.XXS)
        self._reason_label = field_label(self._t.gettext("s4.reason"))
        reason_cell.addWidget(self._reason_label)
        self._reason_edit = QLineEdit(); self._reason_edit.setMinimumWidth(int(FieldWidth.LG))
        reason_cell.addWidget(self._reason_edit)
        rholder = QWidget(); rholder.setLayout(reason_cell); rholder.setStyleSheet("background: transparent;")
        row.addWidget(rholder)
        row.addStretch(1)
        card.body.addLayout(row)
        card.body.addWidget(horizontal_divider())
        self._summary = muted("")
        card.body.addWidget(self._summary)
        return card

    def _build_grid_card(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "brand"); apply_shadow(card)
        headers = ["si.col_row", "si.col_item_code", "si.col_item_name", "si.col_unit",
                   "si.col_qty", "s4.col_returnable", "s4.col_return_qty"]
        self._headers = headers
        self._table = QTableWidget(0, len(headers))
        self._table.setHorizontalHeaderLabels([self._t.gettext(k) for k in headers])
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        hh = self._table.horizontalHeader(); hh.setHighlightSections(False)
        hh.setSectionResizeMode(R_NAME, QHeaderView.ResizeMode.Stretch)
        widths = {R_NO: 40, R_CODE: 110, R_UNIT: 70, R_SOLD: 90, R_RETURNABLE: 110, R_RETURN: 130}
        for col, w in widths.items():
            self._table.setColumnWidth(col, w)
        self._table.verticalHeader().setDefaultSectionSize(ControlSize.TABLE_ROW_HEIGHT + 4)
        card.body.addWidget(self._table)
        return card

    def _build_action_bar(self) -> QWidget:
        from PyQt6.QtWidgets import QFrame
        bar = QFrame(); bar.setProperty("role", "actionbar")
        apply_shadow(bar, blur=18, y=3, alpha=30)
        row = QHBoxLayout(bar)
        row.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        row.setSpacing(Spacing.SM)
        self._btn_post = primary_button(self._t.gettext("s4.act_post"))
        self._btn_post.clicked.connect(lambda: self._post(print_after=False))
        self._btn_post_print = secondary_button(self._t.gettext("s4.act_post_print"))
        self._btn_post_print.clicked.connect(lambda: self._post(print_after=True))
        row.addWidget(self._btn_post); row.addWidget(self._btn_post_print)
        self._error = QLabel(""); self._error.setProperty("role", "error"); self._error.setVisible(False)
        row.addWidget(self._error)
        row.addStretch(1)
        self._btn_close = secondary_button(self._t.gettext("s4.act_close"))
        if self._on_close is not None:
            self._btn_close.clicked.connect(lambda: self._on_close())
        row.addWidget(self._btn_close)
        return bar

    # ---- loading a source ------------------------------------------------

    def open_source(self, doc_id: int) -> None:
        """Open a specific source document by id (from a list 'Return' action)."""
        self.clear_error()
        if self._mode == "sales_return":
            doc = self._ctx.sales_documents.get(doc_id)
        else:
            doc = self._ctx.purchase_documents.get(doc_id)
        if doc is None:
            self._show_error(self._t.gettext("s4.msg_source_not_found"))
            return
        self._src_edit.setText(doc["document_no"])
        self._populate(doc)

    def _load_source(self) -> None:
        self.clear_error()
        term = (self._src_edit.text() or "").strip()
        if not term:
            self._show_error(self._t.gettext("s4.msg_no_source"))
            return
        if self._mode == "sales_return":
            matches = self._ctx.sales_documents.list(term=term, status="POSTED")
        else:
            matches = self._ctx.purchase_documents.list(term=term, status="POSTED")
        doc = next((d for d in matches if d["document_no"].lower() == term.lower()), None)
        if doc is None:
            self._show_error(self._t.gettext("s4.msg_source_not_found"))
            self._clear_table()
            return
        # list rows carry id + document_no; fetch full record for party etc.
        full = (self._ctx.sales_documents.get(doc["id"]) if self._mode == "sales_return"
                else self._ctx.purchase_documents.get(doc["id"]))
        self._populate(full or doc)

    def _populate(self, doc: dict) -> None:
        self._source_id = doc["id"]
        if self._mode == "sales_return":
            lines = self._ctx.sales_documents.lines(doc["id"])
            returnable = self._ctx.sales_documents.returnable_quantities(doc["id"])
            line_key = "id"
        else:
            lines = self._ctx.purchase_documents.lines(doc["id"])
            returnable = self._ctx.purchase_documents.returnable_quantities(doc["id"])
            line_key = "id"
        party = self._ctx.parties_repo.get(doc.get("party_id")) if doc.get("party_id") else None
        self._summary.setText(self._t.gettext("s4.source_summary")
                              .replace("{no}", doc["document_no"])
                              .replace("{party}", (party or {}).get("name", "—")))
        unit_by_id = {u["id"]: u for u in self._ctx.units_repo.list_all()}
        self._lines = []
        for ln in lines:
            item = self._ctx.items_repo.get(ln["item_id"]) or {}
            unit = unit_by_id.get(ln["unit_id"], {})
            self._lines.append({
                "line_id": ln[line_key], "code": item.get("item_code", ""),
                "name": item.get("name", ""),
                "unit": unit.get("symbol") or unit.get("name_en") or "",
                "sold": ln["quantity"], "returnable": returnable.get(ln[line_key], "0"),
            })
        self._render_lines()

    def _render_lines(self) -> None:
        self._return_edits = []
        self._table.setRowCount(0)  # destroy prior per-row edit widgets cleanly
        self._table.setRowCount(len(self._lines))
        for r, ln in enumerate(self._lines):
            cells = {R_NO: str(r + 1), R_CODE: ln["code"], R_NAME: ln["name"],
                     R_UNIT: ln["unit"], R_SOLD: format_money(ln["sold"]),
                     R_RETURNABLE: format_money(ln["returnable"])}
            numeric = {R_SOLD, R_RETURNABLE}
            for col, text in cells.items():
                item = QTableWidgetItem(text)
                align = (Qt.AlignmentFlag.AlignRight if col in numeric
                         else Qt.AlignmentFlag.AlignLeft)
                item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(r, col, item)
            edit = QLineEdit()
            edit.setPlaceholderText("0")
            edit.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            edit.setEnabled(D(ln["returnable"]) > 0)
            self._table.setCellWidget(r, R_RETURN, edit)
            self._return_edits.append(edit)

    def _clear_table(self) -> None:
        self._lines = []; self._return_edits = []
        self._source_id = None
        self._table.setRowCount(0)
        self._summary.setText("")

    # ---- posting ---------------------------------------------------------

    def _collect_return_lines(self):
        out = []
        for ln, edit in zip(self._lines, self._return_edits):
            text = (edit.text() or "").strip()
            if not text:
                continue
            try:
                qty = D(text)
            except Exception:
                qty = D(0)
            if qty > 0:
                out.append((ln["line_id"], text))
        return out

    def _post(self, *, print_after: bool) -> None:
        self.clear_error()
        if self._source_id is None:
            self._show_error(self._t.gettext("s4.msg_no_source"))
            return
        picked = self._collect_return_lines()
        if not picked:
            self._show_error(self._t.gettext("s4.msg_no_return_lines"))
            return
        reason = (self._reason_edit.text() or "").strip() or None
        try:
            if self._mode == "sales_return":
                lines = [ReturnLine(sale_line_id=lid, quantity=q) for lid, q in picked]
                posted = self._ctx.sales_documents.post_return(
                    sale_id=self._source_id, lines=lines, reason=reason)
            else:
                lines = [PurchaseReturnLine(purchase_line_id=lid, quantity=q) for lid, q in picked]
                posted = self._ctx.purchase_documents.post_return(
                    purchase_id=self._source_id, lines=lines, reason=reason)
        except ZenithError as exc:
            self._show_error(getattr(exc, "user_message", None) or str(exc))
            return
        self._last_saved_id = posted.id
        self._status_msg.setText(
            self._t.gettext("s4.msg_returned").replace("{no}", posted.document_no))
        self._clear_table()
        self._src_edit.clear(); self._reason_edit.clear()
        if print_after and self._on_print is not None:
            self._on_print(posted.id)

    # ---- errors / drivers ------------------------------------------------

    def _show_error(self, message: str) -> None:
        self._error.setText(message); self._error.setVisible(True)

    def clear_error(self) -> None:
        self._error.setVisible(False)

    def set_return_qty(self, row: int, qty: str) -> None:
        if 0 <= row < len(self._return_edits):
            self._return_edits[row].setText(qty)

    @property
    def last_saved_id(self) -> int | None:
        return self._last_saved_id

    def reload(self) -> None:
        # nothing cached across shows; a fresh open loads its own source
        pass

    # ---- i18n ------------------------------------------------------------

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext(self._title_key()))
        self._src_label.setText(translator.gettext("s4.source_doc"))
        self._src_edit.setPlaceholderText(translator.gettext("s4.source_ph"))
        self._reason_label.setText(translator.gettext("s4.reason"))
        self._load_btn.setText(escape_amp(translator.gettext("s4.load")))
        self._btn_post.setText(escape_amp(translator.gettext("s4.act_post")))
        self._btn_post_print.setText(escape_amp(translator.gettext("s4.act_post_print")))
        self._btn_close.setText(escape_amp(translator.gettext("s4.act_close")))
        self._table.setHorizontalHeaderLabels([translator.gettext(k) for k in self._headers])
