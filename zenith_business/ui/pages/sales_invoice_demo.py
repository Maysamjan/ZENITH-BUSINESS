"""Sales Invoice — VISUAL PROTOTYPE (Prompt 01C §3).

The reference design for the whole application. It establishes the grid-based
business-form architecture: a compact transaction header at the top, a dominant
line-item grid in the center, and totals + operational info + actions at the
bottom — using the full workspace width and height.

IMPORTANT: This is a pure UI prototype. It does NOT save data, performs NO
accounting/inventory logic, and creates NO database tables. All figures are
clearly-labelled demonstration data.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
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
    LabeledField,
    StatTile,
    apply_field_width,
    apply_shadow,
    chip,
    escape_amp,
    primary_button,
    secondary_button,
)
from zenith_business.ui.design.tokens import (
    Color,
    ControlSize,
    FieldWidth,
    Spacing,
    Typography,
)

# Clearly-fake demonstration line items (no business data / no persistence).
_ROWS = [
    ("IT-1001", "Cooking Oil 5L", "Ctn", 10, 320.00, 0.00, 3200.00, "Main"),
    ("IT-1002", "Basmati Rice 25kg", "Bag", 25, 1450.00, 50.00, 36200.00, "Main"),
    ("IT-1003", "Green Tea 500g", "Box", 40, 120.00, 0.00, 4800.00, "Main"),
    ("IT-1004", "Sugar 50kg", "Bag", 8, 2600.00, 0.00, 20800.00, "Main"),
    ("IT-1005", "Tomato Paste 800g", "Ctn", 15, 540.00, 20.00, 8080.00, "Store-2"),
    ("IT-1006", "Sunflower Oil 1L", "Ctn", 30, 95.00, 0.00, 2850.00, "Main"),
]


class SalesInvoiceDemoPage(QScrollArea):
    """Full-workspace Sales Invoice prototype screen.

    Wrapped in a resizable scroll area: at 1600×900 / 1920×1080 the content fills
    the viewport and the line-item grid expands to dominate; at 1366×768 the
    grid keeps a healthy minimum and the page scrolls gracefully instead of
    clipping the totals or actions.
    """

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._t = translator
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        inner = QWidget()
        self.setWidget(inner)
        root = QVBoxLayout(inner)
        root.setContentsMargins(
            Spacing.PAGE_MARGIN, Spacing.PAGE_MARGIN,
            Spacing.PAGE_MARGIN, Spacing.PAGE_MARGIN,
        )
        root.setSpacing(Spacing.SECTION_GAP)

        root.addLayout(self._build_titlebar())
        root.addLayout(self._build_header_band())
        root.addWidget(self._build_grid(), stretch=1)   # dominant center
        root.addLayout(self._build_bottom_band())
        root.addWidget(self._build_action_bar())

    # ---- helpers ---------------------------------------------------------

    def _combo(self, items: list[str]) -> QComboBox:
        box = QComboBox()
        box.addItems(items)
        return box

    def _line(self, placeholder: str = "") -> QLineEdit:
        edit = QLineEdit()
        if placeholder:
            edit.setPlaceholderText(placeholder)
        return edit

    def _amount(self, value: float = 0.0) -> QDoubleSpinBox:
        box = QDoubleSpinBox()
        box.setMaximum(1_000_000_000)
        box.setDecimals(2)
        box.setGroupSeparatorShown(True)
        box.setValue(value)
        box.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return box

    def _card_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setProperty("role", "card-title")
        return lbl

    # ---- title bar -------------------------------------------------------

    def _build_titlebar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(Spacing.MD)
        self._title = QLabel(self._t.gettext("si.title"))
        self._title.setProperty("role", "page-title")
        row.addWidget(self._title)
        self._badge = chip(self._t.gettext("si.prototype_badge"), "warning")
        row.addWidget(self._badge)
        row.addStretch(1)
        self._demo_chip = chip(self._t.gettext("si.demo_data"), "neutral")
        row.addWidget(self._demo_chip)
        return row

    # ---- header band (invoice details + customer) ------------------------

    def _build_header_band(self) -> QHBoxLayout:
        band = QHBoxLayout()
        band.setSpacing(Spacing.SECTION_GAP)
        band.addWidget(self._build_invoice_details(), stretch=3)
        band.addWidget(self._build_customer_panel(), stretch=2)
        return band

    def _build_invoice_details(self) -> QWidget:
        card = Card(role="section")
        apply_shadow(card)
        grid = QGridLayout()
        grid.setHorizontalSpacing(Spacing.LG)
        grid.setVerticalSpacing(Spacing.SM)

        t = self._t
        inv_no = apply_field_width(self._line("SALE-000001"), FieldWidth.SM)
        date = QDateEdit(); date.setCalendarPopup(True); date.setDisplayFormat("yyyy/MM/dd")
        apply_field_width(date, FieldWidth.SM)
        currency = self._combo(["AFN", "USD", "PKR", "EUR"]); apply_field_width(currency, FieldWidth.SM)
        rate = apply_field_width(self._line("1.00"), FieldWidth.SM)
        warehouse = self._combo(["Main", "Store-2", "Transit"]); apply_field_width(warehouse, FieldWidth.MD)
        salesperson = self._combo(["—", "Ahmad", "Sara"]); apply_field_width(salesperson, FieldWidth.MD)
        reference = apply_field_width(self._line(), FieldWidth.MD)
        description = apply_field_width(self._line(), FieldWidth.LG)

        cells = [
            (t.gettext("si.invoice_no"), inv_no),
            (t.gettext("si.date"), date),
            (t.gettext("si.currency"), currency),
            (t.gettext("si.rate"), rate),
            (t.gettext("si.warehouse"), warehouse),
            (t.gettext("si.salesperson"), salesperson),
            (t.gettext("si.reference"), reference),
        ]
        self._detail_fields: list[LabeledField] = []
        for i, (label, control) in enumerate(cells):
            lf = LabeledField(label, control)
            self._detail_fields.append(lf)
            grid.addWidget(lf, i // 4, i % 4)
        # Description spans the remaining width on its row.
        desc_lf = LabeledField(t.gettext("si.description"), description)
        self._detail_fields.append(desc_lf)
        grid.addWidget(desc_lf, 1, 3)
        for c in range(4):
            grid.setColumnStretch(c, 1)

        card.body.addLayout(grid)
        return card

    def _build_customer_panel(self) -> QWidget:
        card = Card(role="section")
        apply_shadow(card)
        t = self._t
        card.body.addWidget(self._card_title(t.gettext("si.customer")))

        grid = QGridLayout()
        grid.setHorizontalSpacing(Spacing.LG)
        grid.setVerticalSpacing(Spacing.SM)

        code = apply_field_width(self._line("C-1001"), FieldWidth.SM)
        name = apply_field_width(self._line(t.gettext("list.search")), FieldWidth.LG)
        phone = apply_field_width(self._line("070 000 0000"), FieldWidth.MD)
        address = apply_field_width(self._line(), FieldWidth.LG)

        self._customer_fields = [
            LabeledField(t.gettext("si.customer_code"), code),
            LabeledField(t.gettext("si.customer_name"), name),
            LabeledField(t.gettext("si.phone"), phone),
            LabeledField(t.gettext("si.address"), address),
        ]
        grid.addWidget(self._customer_fields[0], 0, 0)
        grid.addWidget(self._customer_fields[1], 0, 1)
        grid.addWidget(self._customer_fields[2], 1, 0)
        grid.addWidget(self._customer_fields[3], 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 2)
        card.body.addLayout(grid)

        # Balance / credit indicators (demonstration values).
        indicators = QHBoxLayout()
        indicators.setSpacing(Spacing.SM)
        self._prev_balance = self._indicator(
            t.gettext("si.prev_balance"), "12,500.00 AFN", "danger"
        )
        self._credit_limit = self._indicator(
            t.gettext("si.credit_limit"), "50,000.00 AFN", "info"
        )
        indicators.addWidget(self._prev_balance)
        indicators.addWidget(self._credit_limit)
        indicators.addStretch(1)
        card.body.addLayout(indicators)
        card.body.addStretch(1)
        return card

    def _indicator(self, label: str, value: str, accent: str) -> QWidget:
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent;")
        row = QHBoxLayout(wrap)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(Spacing.SM)
        lab = QLabel(label); lab.setProperty("role", "field-label")
        row.addWidget(lab)
        row.addWidget(chip(value, accent))
        return wrap

    # ---- center grid -----------------------------------------------------

    def _grid_columns(self) -> list[str]:
        return [
            "si.col_row", "si.col_item_code", "si.col_item_name", "si.col_unit",
            "si.col_qty", "si.col_price", "si.col_discount", "si.col_total",
            "si.col_warehouse",
        ]

    def _build_grid(self) -> QWidget:
        keys = self._grid_columns()
        table = QTableWidget(len(_ROWS) + 1, len(keys))  # +1 empty entry row
        table.setHorizontalHeaderLabels([self._t.gettext(k) for k in keys])
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setDefaultSectionSize(ControlSize.TABLE_ROW_HEIGHT)

        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Item Name
        header.setHighlightSections(False)
        widths = {0: 44, 1: 110, 3: 70, 4: 80, 5: 110, 6: 90, 7: 120, 8: 100}
        for col, w in widths.items():
            table.setColumnWidth(col, w)
        # Keep the grid a healthy, dominant size even on smaller screens.
        table.setMinimumHeight(220)

        numeric = {4, 5, 6, 7}
        for r, (code, name, unit, qty, price, disc, total, wh) in enumerate(_ROWS):
            values = [str(r + 1), code, name, unit, f"{qty:,}",
                      f"{price:,.2f}", f"{disc:,.2f}", f"{total:,.2f}", wh]
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                align = (Qt.AlignmentFlag.AlignRight if col in numeric
                         else Qt.AlignmentFlag.AlignLeft)
                item.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(r, col, item)
        # Trailing empty row hints where the next line is entered.
        for col in range(len(keys)):
            table.setItem(len(_ROWS), col, QTableWidgetItem(""))
        table.item(len(_ROWS), 0).setText(str(len(_ROWS) + 1))

        table.selectRow(1)
        self._table = table
        return table

    # ---- bottom band (operational info + summary) ------------------------

    def _build_bottom_band(self) -> QHBoxLayout:
        band = QHBoxLayout()
        band.setSpacing(Spacing.SECTION_GAP)
        band.addWidget(self._build_operational(), stretch=3)
        band.addWidget(self._build_summary(), stretch=2)
        return band

    def _build_operational(self) -> QWidget:
        card = Card(role="section")
        apply_shadow(card)
        t = self._t
        card.body.addWidget(self._card_title(t.gettext("si.operational")))
        tiles = QHBoxLayout()
        tiles.setSpacing(Spacing.MD)
        self._op_tiles = [
            StatTile(t.gettext("si.op_stock"), "142 Ctn", accent="info"),
            StatTile(t.gettext("si.op_last_purchase"), "310.00 AFN"),
            StatTile(t.gettext("si.op_last_sale"), "325.00 AFN"),
            StatTile(t.gettext("si.op_avg_cost"), "308.40 AFN", accent="success"),
        ]
        for tile in self._op_tiles:
            tile.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            tiles.addWidget(tile)
        card.body.addLayout(tiles)
        card.body.addStretch(1)
        return card

    def _build_summary(self) -> QWidget:
        card = Card(role="section")
        apply_shadow(card)
        t = self._t

        grid = QGridLayout()
        grid.setHorizontalSpacing(Spacing.XL)
        grid.setVerticalSpacing(Spacing.XS)
        rows = [
            ("si.subtotal", "75,930.00"),
            ("si.discount", "120.00"),
            ("si.additional", "0.00"),
            ("si.tax", "0.00"),
        ]
        self._summary_labels: list[tuple[str, QLabel]] = []
        for i, (key, value) in enumerate(rows):
            name = QLabel(t.gettext(key)); name.setProperty("role", "total-label")
            val = QLabel(value); val.setProperty("role", "total-value")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(name, i, 0)
            grid.addWidget(val, i, 1)
            self._summary_labels.append((key, name))
        grid.setColumnStretch(1, 1)
        card.body.addLayout(grid)

        # Emphasized grand total.
        gt = QFrame(); gt.setProperty("role", "grand-total")
        gt_row = QHBoxLayout(gt)
        gt_row.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        self._grand_label = QLabel(t.gettext("si.grand_total"))
        self._grand_label.setProperty("role", "grand-total-label")
        gt_val = QLabel("75,810.00 AFN")
        gt_val.setProperty("role", "grand-total-value")
        gt_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        gt_row.addWidget(self._grand_label)
        gt_row.addStretch(1)
        gt_row.addWidget(gt_val)
        card.body.addWidget(gt)

        # Payment split.
        pay = QGridLayout()
        pay.setHorizontalSpacing(Spacing.XL)
        pay.setVerticalSpacing(Spacing.XS)
        self._cash_label = QLabel(t.gettext("si.cash_received"))
        self._cash_label.setProperty("role", "total-label")
        cash_val = QLabel("40,000.00"); cash_val.setProperty("role", "total-value")
        cash_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._rem_label = QLabel(t.gettext("si.remaining"))
        self._rem_label.setProperty("role", "total-label")
        rem_val = QLabel("35,810.00"); rem_val.setProperty("role", "total-value")
        rem_val.setProperty("accent", "danger")
        rem_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        pay.addWidget(self._cash_label, 0, 0); pay.addWidget(cash_val, 0, 1)
        pay.addWidget(self._rem_label, 1, 0); pay.addWidget(rem_val, 1, 1)
        pay.setColumnStretch(1, 1)
        card.body.addLayout(pay)
        return card

    # ---- action bar ------------------------------------------------------

    def _build_action_bar(self) -> QWidget:
        bar = QFrame(); bar.setProperty("role", "actionbar")
        apply_shadow(bar, blur=18, y=3, alpha=30)
        row = QHBoxLayout(bar)
        row.setContentsMargins(Spacing.MD, Spacing.SM, Spacing.MD, Spacing.SM)
        row.setSpacing(Spacing.SM)
        t = self._t

        # (label_key, shortcut, primary)
        specs = [
            ("si.act_new", "F2", False),
            ("si.act_save", "Ctrl+S", True),
            ("si.act_save_print", "Ctrl+P", False),
            ("si.act_print", "F9", False),
            ("si.act_receive", "F6", False),
        ]
        self._action_buttons: list[tuple[str, QWidget]] = []
        for key, shortcut, is_primary in specs:
            btn = primary_button(t.gettext(key)) if is_primary else secondary_button(t.gettext(key))
            btn.setToolTip(shortcut)
            self._action_buttons.append((key, btn))
            row.addWidget(btn)
            hint = QLabel(shortcut); hint.setProperty("role", "shortcut")
            row.addWidget(hint)
        row.addStretch(1)
        self._close_btn = secondary_button(t.gettext("si.act_close"))
        row.addWidget(self._close_btn)
        return bar

    # ---- i18n ------------------------------------------------------------

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(translator.gettext("si.title"))
        self._badge.setText(translator.gettext("si.prototype_badge"))
        self._demo_chip.setText(translator.gettext("si.demo_data"))
        keys = self._grid_columns()
        self._table.setHorizontalHeaderLabels([translator.gettext(k) for k in keys])
        self._grand_label.setText(translator.gettext("si.grand_total"))
        self._cash_label.setText(translator.gettext("si.cash_received"))
        self._rem_label.setText(translator.gettext("si.remaining"))
        for key, label in self._summary_labels:
            label.setText(translator.gettext(key))
        for key, btn in self._action_buttons:
            btn.setText(escape_amp(translator.gettext(key)))
        self._close_btn.setText(escape_amp(translator.gettext("si.act_close")))
