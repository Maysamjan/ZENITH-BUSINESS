"""Stage 04 document list screens — Sales, Purchases and Returns.

A real, repository-backed management list (search, status filter, dominant table)
built on the LOCKED design system. Rows are the persisted documents; per-row
actions Print (all) and Return (invoices) route to the owning window. Amounts are
displayed via :func:`format_money` from the exact stored Decimal text.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Translator
from zenith_business.core.money import format_money
from zenith_business.ui.components import (
    Card,
    chip,
    ghost_button,
    page_title,
    primary_button,
)
from zenith_business.ui.design.tokens import ControlSize, FieldWidth, Spacing

_STATUS_CHIP = {"POSTED": ("s4.status_posted", "success"),
                "DRAFT": ("s4.status_draft", "warning"),
                "VOID": ("s4.status_void", "neutral"),
                "CANCELLED": ("s4.status_void", "neutral")}


class DocumentListPage(QWidget):
    """List of sales / purchases / returns with search, filter and row actions."""

    def __init__(
        self,
        context,
        translator: Translator,
        *,
        mode: str,  # 'sale' | 'purchase' | 'sales_return' | 'purchase_return'
        on_new: Callable[[], None] | None = None,
        on_print: Callable[[int], None] | None = None,
        on_return: Callable[[int], None] | None = None,
        on_void: Callable[[int], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._ctx = context
        self._t = translator
        self._mode = mode
        self._on_new = on_new
        self._on_print = on_print
        self._on_return = on_return
        self._on_void = on_void
        self._rows: list[dict] = []
        self._is_return = mode in ("sales_return", "purchase_return")

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.PAGE_MARGIN, Spacing.PAGE_MARGIN,
                                Spacing.PAGE_MARGIN, Spacing.PAGE_MARGIN)
        root.setSpacing(Spacing.SECTION_GAP)

        root.addLayout(self._build_header())
        root.addWidget(self._build_filter_bar())
        root.addWidget(self._build_table(), stretch=1)
        self.reload()

    # ---- title -----------------------------------------------------------

    def _title_key(self) -> str:
        return {"sale": "s4.sales_list_title", "purchase": "s4.purchases_list_title",
                "sales_return": "s4.return_sale_title",
                "purchase_return": "s4.return_purchase_title"}[self._mode]

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(Spacing.MD)
        col = QVBoxLayout(); col.setSpacing(Spacing.XXS)
        self._title = page_title(self._t.gettext(self._title_key()))
        col.addWidget(self._title)
        self._count = QLabel(""); self._count.setProperty("role", "muted")
        col.addWidget(self._count)
        row.addLayout(col)
        row.addStretch(1)
        if self._on_new is not None and not self._is_return:
            new_key = "s4.sale_new" if self._mode == "sale" else "s4.purchase_new"
            self._new_btn = primary_button(self._t.gettext(new_key))
            self._new_btn.clicked.connect(lambda: self._on_new())
            row.addWidget(self._new_btn, alignment=Qt.AlignmentFlag.AlignTop)
        else:
            self._new_btn = None
        return row

    def _build_filter_bar(self) -> QWidget:
        bar = Card(role="section")
        bar.body.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        row = QHBoxLayout(); row.setSpacing(Spacing.SM)
        self._search = QLineEdit()
        self._search.setPlaceholderText(self._t.gettext("md.search"))
        self._search.setClearButtonEnabled(True)
        self._search.setMinimumWidth(int(FieldWidth.LG))
        self._search.textChanged.connect(lambda _t: self.reload())
        row.addWidget(self._search)
        self._status_filter = QComboBox()
        self._status_filter.addItem(self._t.gettext("s4.filter_all"), None)
        if not self._is_return:
            self._status_filter.addItem(self._t.gettext("s4.status_posted"), "POSTED")
            self._status_filter.addItem(self._t.gettext("s4.status_void"), "VOID")
            self._status_filter.currentIndexChanged.connect(lambda _i: self.reload())
            row.addWidget(self._status_filter)
        row.addStretch(1)
        self._refresh_btn = ghost_button(self._t.gettext("md.refresh"))
        self._refresh_btn.clicked.connect(self.reload)
        row.addWidget(self._refresh_btn)
        bar.body.addLayout(row)
        return bar

    def _columns(self) -> list[tuple[str, str, str]]:
        """(header_key, row_key, align)."""
        if self._is_return:
            src_key = "sale_no" if self._mode == "sales_return" else "purchase_no"
            return [("s4.col_docno", "document_no", "l"),
                    ("s4.col_date", "return_date", "l"),
                    ("s4.col_source", src_key, "l"),
                    ("s4.col_party", "party_name", "l"),
                    ("s4.col_total", "grand_total", "r"),
                    ("s4.col_status", "status", "c")]
        date_key = "sale_date" if self._mode == "sale" else "purchase_date"
        return [("s4.col_docno", "document_no", "l"),
                ("s4.col_date", date_key, "l"),
                ("s4.col_party", "party_name", "l"),
                ("s4.col_warehouse", "warehouse_name", "l"),
                ("s4.col_total", "grand_total", "r"),
                ("s4.col_paid", "amount_paid", "r"),
                ("s4.col_remaining", "remaining_amount", "r"),
                ("s4.col_status", "status", "c")]

    def _build_table(self) -> QWidget:
        cols = self._columns()
        self._table = QTableWidget(0, len(cols) + 1)
        headers = [self._t.gettext(h) for h, _k, _a in cols] + [self._t.gettext("md.actions")]
        self._table.setHorizontalHeaderLabels(headers)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        hh = self._table.horizontalHeader()
        hh.setHighlightSections(False)
        # party column stretches; status holds a chip widget so it needs a fixed
        # width wide enough for the pill (ResizeToContents clips the widget).
        stretch_idx = next((i for i, (_h, k, _a) in enumerate(cols) if k == "party_name"), 0)
        status_idx = next((i for i, (_h, k, _a) in enumerate(cols) if k == "status"), -1)
        for i in range(len(cols)):
            if i == stretch_idx:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            elif i == status_idx:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self._table.setColumnWidth(i, 110)
            else:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(len(cols), QHeaderView.ResizeMode.Fixed)
        # Widen the actions column so Print + Return + Void never clip (defect #3/#5).
        n_actions = sum(x is not None for x in (self._on_print, self._on_return, self._on_void))
        self._table.setColumnWidth(len(cols), 130 if n_actions <= 1 else 90 * n_actions)
        self._table.verticalHeader().setDefaultSectionSize(ControlSize.TABLE_ROW_HEIGHT + 6)
        return self._table

    # ---- data ------------------------------------------------------------

    def reload(self) -> None:
        term = (self._search.text() or "").strip() or None if hasattr(self, "_search") else None
        status = self._status_filter.currentData() if hasattr(self, "_status_filter") else None
        if self._mode == "sale":
            self._rows = self._ctx.sales_documents.list(term=term, status=status)
        elif self._mode == "purchase":
            self._rows = self._ctx.purchase_documents.list(term=term, status=status)
        elif self._mode == "sales_return":
            self._rows = self._ctx.sales_returns_repo.list_recent()
        else:
            self._rows = self._ctx.purchase_returns_repo.list_recent()
        self._render()

    def _render(self) -> None:
        cols = self._columns()
        self._count.setText(self._t.gettext("md.count").replace("{n}", str(len(self._rows))))
        # Clear rows first so previously-set cell widgets (status chips, action
        # buttons) are destroyed rather than lingering at a stale position when
        # the list is re-rendered (e.g. reopened from the nav).
        self._table.setRowCount(0)
        self._table.setRowCount(len(self._rows))
        money_keys = {"grand_total", "amount_paid", "remaining_amount"}
        for r, data in enumerate(self._rows):
            for c, (_h, key, align) in enumerate(cols):
                if key == "status":
                    self._table.setCellWidget(r, c, self._status_cell(data.get("status", "")))
                    continue
                value = data.get(key)
                text = format_money(value) if key in money_keys else ("" if value is None else str(value))
                item = QTableWidgetItem(text)
                a = (Qt.AlignmentFlag.AlignRight if align == "r"
                     else Qt.AlignmentFlag.AlignCenter if align == "c"
                     else Qt.AlignmentFlag.AlignLeft)
                item.setTextAlignment(a | Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(r, c, item)
            self._table.setCellWidget(r, len(cols), self._action_cell(data))

    def _status_cell(self, status: str) -> QWidget:
        host = QWidget(); lay = QHBoxLayout(host)
        lay.setContentsMargins(Spacing.SM, 0, Spacing.SM, 0)
        key, kind = _STATUS_CHIP.get(status, ("s4.status_posted", "neutral"))
        lay.addWidget(chip(self._t.gettext(key), kind)); lay.addStretch(1)
        return host

    def _action_cell(self, data: dict) -> QWidget:
        host = QWidget(); lay = QHBoxLayout(host)
        lay.setContentsMargins(Spacing.SM, 0, Spacing.SM, 0); lay.setSpacing(Spacing.XS)
        if self._on_print is not None:
            b = ghost_button(self._t.gettext("s4.act_print"))
            b.clicked.connect(lambda _c=False, i=data["id"]: self._on_print(i))
            lay.addWidget(b)
        if (self._on_return is not None and not self._is_return
                and data.get("status") == "POSTED"):
            rb = ghost_button(self._t.gettext("s4.act_return"))
            rb.clicked.connect(lambda _c=False, i=data["id"]: self._on_return(i))
            lay.addWidget(rb)
        if (self._on_void is not None and not self._is_return
                and data.get("status") == "POSTED"):
            vb = ghost_button(self._t.gettext("s4.act_void"))
            vb.setProperty("variant", "danger")
            vb.clicked.connect(lambda _c=False, i=data["id"]: self._on_void(i))
            lay.addWidget(vb)
        lay.addStretch(1)
        return host

    # ---- i18n ------------------------------------------------------------

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext(self._title_key()))
        self._search.setPlaceholderText(translator.gettext("md.search"))
        self._refresh_btn.setText(translator.gettext("md.refresh"))
        # Rebuild the status-filter labels in the new language (keep the selection).
        if hasattr(self, "_status_filter") and not self._is_return:
            keep = self._status_filter.currentData()
            self._status_filter.blockSignals(True)
            self._status_filter.clear()
            for label_key, data in (("s4.filter_all", None), ("s4.status_posted", "POSTED"),
                                    ("s4.status_void", "VOID")):
                self._status_filter.addItem(translator.gettext(label_key), data)
            idx = self._status_filter.findData(keep)
            if idx >= 0:
                self._status_filter.setCurrentIndex(idx)
            self._status_filter.blockSignals(False)
        if self._new_btn is not None:
            from zenith_business.ui.components import escape_amp
            new_key = "s4.sale_new" if self._mode == "sale" else "s4.purchase_new"
            self._new_btn.setText(escape_amp(translator.gettext(new_key)))
        cols = self._columns()
        headers = [translator.gettext(h) for h, _k, _a in cols] + [translator.gettext("md.actions")]
        self._table.setHorizontalHeaderLabels(headers)
        self.reload()
