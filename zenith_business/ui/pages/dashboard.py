"""Home business dashboard (Prompt 01F §5).

A compact, operational desktop dashboard — KPI tiles, quick actions, recent
transactions and low-stock — not an oversized website dashboard. All figures are
clearly-labelled DEMONSTRATION data (no persistence, no real accounting).
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Translator
from zenith_business.core.money import D
from zenith_business.ui.components import (
    Card,
    StatTile,
    chip,
    muted,
    primary_button,
    secondary_button,
    standard_icon,
)
from zenith_business.ui.design.tokens import ControlSize, Spacing
from zenith_business.ui.mock.demo_invoice import build_demo_invoice

# KPI definitions: (key, value, accent)
_KPIS = [
    ("dash.today_sales", "128,400 AFN", "info"),
    ("dash.today_purchases", "74,200 AFN", "neutral"),
    ("dash.cash", "356,900 AFN", "success"),
    ("dash.receivables", "512,300 AFN", "warning"),
    ("dash.payables", "208,750 AFN", "danger"),
    ("dash.profit", "18,600 AFN", "success"),
]

# Recent transactions: (time, type_key, party, amount, status_key, money)
_RECENT = [
    ("10:42", "dash.t_sale", "Kabul General Store", "+73,450", "dash.st_credit", "pos"),
    ("10:15", "dash.t_receipt", "Herat Traders", "+30,000", "dash.st_paid", "pos"),
    ("09:58", "dash.t_purchase", "National Foods", "-52,000", "dash.st_paid", "neg"),
    ("09:30", "dash.t_expense", "Shop Rent", "-8,000", "dash.st_paid", "neg"),
    ("09:05", "dash.t_sale", "Mazar Wholesale", "+21,900", "dash.st_paid", "pos"),
]

# Low stock: (item, stock, status_key, chip)
_LOW = [
    ("Basmati Premium 50kg", "22", "dash.st_low", "warning"),
    ("Sugar 50kg", "8", "dash.st_low", "warning"),
    ("Cardamom 1kg", "0", "dash.st_out", "danger"),
    ("Saffron 100g", "3", "dash.st_low", "warning"),
]


def _fmt_qty(value) -> str:
    """Compact quantity: no trailing zeros (e.g. 22, 7.5)."""
    return format(D(value).normalize(), "f")


class DashboardPage(QWidget):
    """Compact operational home dashboard."""

    def __init__(
        self,
        translator: Translator,
        *,
        on_new_sale: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._t = translator
        self._on_new_sale = on_new_sale
        self.setProperty("role", "workspace")

        root = QVBoxLayout(self)
        root.setContentsMargins(Spacing.LG, Spacing.MD, Spacing.LG, Spacing.MD)
        root.setSpacing(Spacing.MD)

        self._ctx = None  # bound to a live context by bind_context (Stage 04)
        root.addLayout(self._build_topbar())
        root.addLayout(self._build_quick_actions())
        root.addWidget(self._build_kpis())
        root.addLayout(self._build_panels(), stretch=1)

    # ---- live data (Stage 04) -------------------------------------------

    def bind_context(self, context) -> None:
        """Replace demonstration figures with real, live business data.

        Today's Sales / Purchases are summed from posted documents; the Recent
        panel lists real recent sales. KPIs without a computed source show a
        truthful ``—`` placeholder rather than fabricated numbers.
        """
        from zenith_business.core.clock import today_iso
        from zenith_business.core.money import format_money

        self._ctx = context
        today = today_iso()
        self._date.setText(today)
        self._demo_chip.setText(self._t.gettext("s4.dash_live"))
        self._demo_chip.setProperty("chip", "success")
        self._demo_chip.style().unpolish(self._demo_chip)
        self._demo_chip.style().polish(self._demo_chip)

        base = context.currencies_repo.base_currency()
        code = base["code"] if base else ""
        sales_today = context.sales_ext_repo.today_total(today)
        purch_today = context.purchases_ext_repo.today_total(today)
        live = {
            "dash.today_sales": f"{format_money(sales_today)} {code}".strip(),
            "dash.today_purchases": f"{format_money(purch_today)} {code}".strip(),
        }
        for key, tile in self._kpi_tiles:
            tile.set_value(live.get(key, "—"))

        self.refresh_recent()
        self.refresh_low_stock()

    def refresh_recent(self) -> None:
        """Repopulate the Recent panel from real recent sales."""
        if self._ctx is None:
            return
        from PyQt6.QtGui import QColor

        from zenith_business.core.money import format_money
        from zenith_business.ui.design.tokens import Color
        try:
            rows = self._ctx.sales_documents.list(limit=6)
        except Exception:
            rows = []
        self._recent.setRowCount(len(rows))
        for r, row in enumerate(rows):
            paid = (row.get("remaining_amount") in ("0", "0.00", None))
            status_key = "dash.st_paid" if paid else "dash.st_credit"
            vals = [str(row.get("sale_date", "")), self._t.gettext("s4.t_sale"),
                    row.get("party_name") or self._t.gettext("s4.walkin"),
                    format_money(row.get("grand_total")), self._t.gettext(status_key)]
            for cidx, text in enumerate(vals):
                item = QTableWidgetItem(text)
                if cidx == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    item.setForeground(QColor(Color.POSITIVE))
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self._recent.setItem(r, cidx, item)

    # ---- top bar ---------------------------------------------------------

    def _build_topbar(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(Spacing.MD)
        self._title = QLabel(self._t.gettext("dash.title"))
        self._title.setProperty("role", "page-title")
        row.addWidget(self._title)
        self._date = muted(build_demo_invoice().date)
        row.addWidget(self._date)
        row.addStretch(1)
        self._demo_chip = chip(self._t.gettext("dash.demo"), "neutral")
        row.addWidget(self._demo_chip)
        return row

    # ---- quick actions ---------------------------------------------------

    def _build_quick_actions(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(Spacing.SM)
        self._qa: list[tuple[str, QWidget]] = []
        specs = [
            ("dash.new_sale", "new", True),
            ("dash.new_purchase", "new", False),
            ("dash.receive", "receive", False),
            ("dash.pay", "receive", False),
            ("dash.new_expense", "new", False),
        ]
        for key, icon, primary in specs:
            btn = primary_button(self._t.gettext(key)) if primary else secondary_button(self._t.gettext(key))
            btn.setIcon(standard_icon(icon))
            if key == "dash.new_sale" and self._on_new_sale is not None:
                btn.clicked.connect(lambda _c=False: self._on_new_sale())
            else:
                btn.setEnabled(key == "dash.new_sale")
            self._qa.append((key, btn))
            row.addWidget(btn)
        row.addStretch(1)
        return row

    # ---- KPI tiles -------------------------------------------------------

    def _build_kpis(self) -> QWidget:
        wrap = QFrame()
        grid = QGridLayout(wrap)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(Spacing.MD)
        self._kpi_tiles: list[tuple[str, StatTile]] = []
        for i, (key, value, accent) in enumerate(_KPIS):
            tile = StatTile(self._t.gettext(key), value, accent=accent)
            tile.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            grid.addWidget(tile, i // 3, i % 3)
            self._kpi_tiles.append((key, tile))
        return wrap

    # ---- bottom panels ---------------------------------------------------

    def _build_panels(self) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(Spacing.MD)
        row.addWidget(self._build_recent(), stretch=3)
        row.addWidget(self._build_low_stock(), stretch=2)
        return row

    def _table(self, cols: int) -> QTableWidget:
        t = QTableWidget(0, cols)
        t.verticalHeader().setVisible(False)
        t.setAlternatingRowColors(True)
        t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        t.verticalHeader().setDefaultSectionSize(ControlSize.TABLE_ROW_HEIGHT)
        return t

    def _build_recent(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "brand")
        title = QLabel(self._t.gettext("dash.recent")); title.setProperty("role", "card-title")
        title.setProperty("accent", "brand")
        card.body.addWidget(title)
        cols = ["dash.col_time", "dash.col_type", "dash.col_party", "dash.col_amount", "dash.col_status"]
        self._recent = self._table(len(cols))
        self._recent.setHorizontalHeaderLabels([self._t.gettext(k) for k in cols])
        h = self._recent.horizontalHeader()
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setHighlightSections(False)
        self._recent.setColumnWidth(0, 74); self._recent.setColumnWidth(1, 90)
        self._recent.setColumnWidth(3, 100); self._recent.setColumnWidth(4, 80)
        self._recent.setRowCount(len(_RECENT))
        from PyQt6.QtGui import QColor

        from zenith_business.ui.design.tokens import Color
        for r, (time, tkey, party, amount, skey, money) in enumerate(_RECENT):
            vals = [time, self._t.gettext(tkey), party, amount, self._t.gettext(skey)]
            for cidx, text in enumerate(vals):
                item = QTableWidgetItem(text)
                if cidx == 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    item.setForeground(QColor(Color.POSITIVE if money == "pos" else Color.NEGATIVE))
                else:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self._recent.setItem(r, cidx, item)
        card.body.addWidget(self._recent)
        self._recent_cols = cols
        return card

    def _build_low_stock(self) -> QWidget:
        card = Card(role="section"); card.setProperty("accent", "teal")
        title = QLabel(self._t.gettext("dash.low_stock")); title.setProperty("role", "card-title")
        title.setProperty("accent", "teal")
        card.body.addWidget(title)
        self._low_rows_host = QVBoxLayout(); self._low_rows_host.setSpacing(Spacing.XS)
        card.body.addLayout(self._low_rows_host)
        card.body.addStretch(1)
        self._low_card = card
        self._set_low_rows([(name, stock, self._t.gettext(skey), kind) for name, stock, skey, kind in _LOW])
        return card

    def _set_low_rows(self, rows: list[tuple[str, str, str, str]]) -> None:
        """Replace the low-stock rows (name, qty, status_text, chip_kind)."""
        while self._low_rows_host.count():
            item = self._low_rows_host.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)  # detach immediately so it stops painting
                w.deleteLater()
        if not rows:
            key = "s4.dash_all_stocked" if self._ctx is not None else "s4.dash_no_data"
            self._low_rows_host.addWidget(muted(self._t.gettext(key)))
            return
        for name, stock, status_text, kind in rows:
            line = QHBoxLayout(); line.setSpacing(Spacing.SM)
            line.addWidget(QLabel(name), 1)
            line.addWidget(muted(stock))
            line.addWidget(chip(status_text, kind))
            holder = QWidget(); holder.setLayout(line)
            self._low_rows_host.addWidget(holder)

    def refresh_low_stock(self) -> None:
        """Real low-stock: items at or below their reorder level (or out)."""
        if self._ctx is None:
            return
        rows: list[tuple[str, str, str, str]] = []
        try:
            items = self._ctx.items_repo.list_active()
        except Exception:
            items = []
        for it in items:
            if not it.get("track_inventory", 1):
                continue
            try:
                on_hand = D(self._ctx.inventory.on_hand(it["id"]))
            except Exception:
                continue
            reorder = D(it.get("reorder_level") or 0)
            out = on_hand <= 0
            low = out or (reorder > 0 and on_hand <= reorder)
            if not low:
                continue
            status = self._t.gettext("dash.st_out" if out else "dash.st_low")
            rows.append((it.get("name", ""), _fmt_qty(on_hand),
                         status, "danger" if out else "warning"))
        rows.sort(key=lambda r: r[0])
        self._set_low_rows(rows[:8])

    # ---- i18n ------------------------------------------------------------

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext("dash.title"))
        self._demo_chip.setText(
            translator.gettext("s4.dash_live" if self._ctx is not None else "dash.demo"))
        for key, btn in self._qa:
            btn.setText(translator.gettext(key))
        for key, tile in self._kpi_tiles:
            tile.set_label(translator.gettext(key))
        self._recent.setHorizontalHeaderLabels(
            [translator.gettext(k) for k in self._recent_cols]
        )
        if self._ctx is not None:
            # Live data: re-fetch (labels/row-count follow the real rows).
            self.bind_context(self._ctx)
            return
        for r, (_time, tkey, _party, _amount, skey, _m) in enumerate(_RECENT):
            self._recent.item(r, 1).setText(translator.gettext(tkey))
            self._recent.item(r, 4).setText(translator.gettext(skey))
