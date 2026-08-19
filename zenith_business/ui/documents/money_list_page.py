"""Stage 05 money-document list screens — Receipts, Payments, Expenses.

Same management-list architecture and visual language as the Stage 03/04 lists
(title + count, search Card, status filter, themed table, per-row Print). Amounts
are displayed via :func:`format_money` from the exact stored Decimal text.
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

from zenith_business.core.money import format_money
from zenith_business.ui.components import Card, chip, ghost_button, page_title, primary_button
from zenith_business.ui.design.tokens import ControlSize, FieldWidth, Spacing

_STATUS_CHIP = {"POSTED": ("s4.status_posted", "success"),
                "DRAFT": ("s4.status_draft", "warning"),
                "VOID": ("s4.status_void", "neutral")}
_METHOD_KEYS = {"CASH": "s5.m_cash", "BANK": "s5.m_bank", "TRANSFER": "s5.m_transfer",
                "CHEQUE": "s5.m_cheque", "OTHER": "s5.m_other"}


class MoneyListPage(QWidget):
    """List of receipts / payments / expenses with search, filter and Print."""

    def __init__(self, context, translator, *, mode: str,
                 on_new: Callable[[], None] | None = None,
                 on_print: Callable[[int], None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = context
        self._t = translator
        self._mode = mode  # 'receipt' | 'payment' | 'expense'
        self._on_new = on_new
        self._on_print = on_print
        self._on_view_account = None  # contextual ledger access (round 2)
        self._rows: list[dict] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.PAGE_MARGIN, Spacing.PAGE_MARGIN,
                                Spacing.PAGE_MARGIN, Spacing.PAGE_MARGIN)
        root.setSpacing(Spacing.SECTION_GAP)
        root.addLayout(self._build_header())
        root.addWidget(self._build_filter_bar())
        root.addWidget(self._build_table(), stretch=1)
        self.reload()

    def _title_key(self) -> str:
        return {"receipt": "s5.receipts_title", "payment": "s5.payments_title",
                "expense": "s5.expenses_title"}[self._mode]

    def _new_key(self) -> str:
        return {"receipt": "s5.receipt_title", "payment": "s5.payment_title",
                "expense": "s5.expense_title"}[self._mode]

    def _build_header(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(Spacing.MD)
        col = QVBoxLayout(); col.setSpacing(Spacing.XXS)
        self._title = page_title(self._t.gettext(self._title_key()))
        col.addWidget(self._title)
        self._count = QLabel(""); self._count.setProperty("role", "muted")
        col.addWidget(self._count)
        row.addLayout(col); row.addStretch(1)
        if self._on_new is not None:
            self._new_btn = primary_button(self._t.gettext(self._new_key()))
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
        self._fund_filter = QComboBox()
        self._fund_filter.addItem(self._t.gettext("s5.all_funds"), None)
        for f in self._ctx.funds_repo.list_funds():
            self._fund_filter.addItem(f["name"], f["id"])
        self._fund_filter.currentIndexChanged.connect(lambda _i: self.reload())
        row.addWidget(self._fund_filter)
        row.addStretch(1)
        self._refresh_btn = ghost_button(self._t.gettext("md.refresh"))
        self._refresh_btn.clicked.connect(self.reload)
        row.addWidget(self._refresh_btn)
        bar.body.addLayout(row)
        return bar

    def _columns(self) -> list[tuple[str, str, str]]:
        date_key = {"receipt": "receipt_date", "payment": "payment_date",
                    "expense": "expense_date"}[self._mode]
        if self._mode == "expense":
            return [("s4.col_docno", "document_no", "l"), ("s4.col_date", date_key, "l"),
                    ("s5.col_category", "category_name", "l"), ("s5.col_payee", "payee", "l"),
                    ("s5.col_account", "account_name", "l"), ("s5.col_amount", "amount", "r"),
                    ("s5.col_method", "payment_method", "c"), ("s4.col_status", "status", "c")]
        return [("s4.col_docno", "document_no", "l"), ("s4.col_date", date_key, "l"),
                ("s4.col_party", "party_name", "l"), ("s5.col_account", "account_name", "l"),
                ("s5.col_amount", "amount", "r"), ("s5.col_method", "payment_method", "c"),
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
        hh = self._table.horizontalHeader(); hh.setHighlightSections(False)
        stretch_key = "party_name" if self._mode != "expense" else "payee"
        stretch_idx = next((i for i, (_h, k, _a) in enumerate(cols) if k == stretch_key), 2)
        status_idx = next((i for i, (_h, k, _a) in enumerate(cols) if k == "status"), -1)
        method_idx = next((i for i, (_h, k, _a) in enumerate(cols) if k == "payment_method"), -1)
        for i in range(len(cols)):
            if i == stretch_idx:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            elif i == status_idx:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self._table.setColumnWidth(i, 110)
            elif i == method_idx:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self._table.setColumnWidth(i, 110)
            else:
                hh.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(len(cols), QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(len(cols), 110)
        self._table.verticalHeader().setDefaultSectionSize(ControlSize.TABLE_ROW_HEIGHT + 6)
        return self._table

    # ---- data ------------------------------------------------------------

    def reload(self) -> None:
        term = (self._search.text() or "").strip() or None if hasattr(self, "_search") else None
        account_id = self._fund_filter.currentData() if hasattr(self, "_fund_filter") else None
        svc = {"receipt": self._ctx.receipts, "payment": self._ctx.payments,
               "expense": self._ctx.expenses}[self._mode]
        self._rows = svc.list(term=term, account_id=account_id)
        self._render()

    def _render(self) -> None:
        cols = self._columns()
        self._count.setText(self._t.gettext("md.count").replace("{n}", str(len(self._rows))))
        self._table.setRowCount(0)
        self._table.setRowCount(len(self._rows))
        for r, data in enumerate(self._rows):
            for c, (_h, key, align) in enumerate(cols):
                if key == "status":
                    self._table.setCellWidget(r, c, self._status_cell(data.get("status", "")))
                    continue
                value = data.get(key)
                if key == "amount":
                    text = format_money(value)
                elif key == "payment_method":
                    text = self._t.gettext(_METHOD_KEYS.get((value or "").upper(), "s5.m_cash")) if value else ""
                else:
                    text = "" if value is None else str(value)
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

    def set_view_account_handler(self, handler) -> None:
        """Wire the contextual 'View Account' action to open the party ledger."""
        self._on_view_account = handler
        # A wider actions column so Print + View Account never clip.
        self._table.setColumnWidth(self._table.columnCount() - 1, 210)
        self._render()

    def _action_cell(self, data: dict) -> QWidget:
        host = QWidget(); lay = QHBoxLayout(host)
        lay.setContentsMargins(Spacing.SM, 0, Spacing.SM, 0); lay.setSpacing(Spacing.XS)
        if self._on_print is not None:
            b = ghost_button(self._t.gettext("s4.act_print"))
            b.clicked.connect(lambda _c=False, i=data["id"]: self._on_print(i))
            lay.addWidget(b)
        if (self._on_view_account is not None and self._mode in ("receipt", "payment")
                and data.get("party_id")):
            role = "customer" if self._mode == "receipt" else "supplier"
            v = ghost_button(self._t.gettext("md.view")); v.setProperty("variant", "accent")
            v.clicked.connect(
                lambda _c=False, pid=data["party_id"], rl=role: self._on_view_account(pid, rl))
            lay.addWidget(v)
        lay.addStretch(1)
        return host

    def retranslate(self, translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext(self._title_key()))
        self._search.setPlaceholderText(translator.gettext("md.search"))
        self._refresh_btn.setText(translator.gettext("md.refresh"))
        if self._new_btn is not None:
            from zenith_business.ui.components import escape_amp
            self._new_btn.setText(escape_amp(translator.gettext(self._new_key())))
        cols = self._columns()
        headers = [translator.gettext(h) for h, _k, _a in cols] + [translator.gettext("md.actions")]
        self._table.setHorizontalHeaderLabels(headers)
        self.reload()
