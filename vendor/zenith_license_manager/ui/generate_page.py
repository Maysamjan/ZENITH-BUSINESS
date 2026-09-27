"""Generate License — the screen a vendor uses every day (Vendor Manager §1, §2).

Left: who is asking and what they get. Right: the key to send back. That is the
whole job, and the layout says so — a vendor pastes a request code into the top
field, picks FULL or DEMO, presses one button, and copies one line.

Everything that can be worked out is worked out: the licence number is the next
unused one for this product and type, the demo length is a row of buttons rather
than a date picker, and the expiry is shown as a date once chosen so nobody has
to count days in their head.

Nothing here can sign. The signing key is held by the window and passed in only
when Generate is pressed, so a screen left open is not a key left open.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from vendor.zenith_license_manager import issuing, products


class GeneratePage(QWidget):
    """Customer, machine, licence type — then one button."""

    def __init__(self, *, on_generate: Callable[[dict], None],
                 next_serial: Callable[[str, str], int],
                 on_product_changed: Callable[[], None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on_generate = on_generate
        self._next_serial = next_serial
        self._on_product_changed = on_product_changed
        self._issued = None
        #: Set by the window from the signing-key self-test. Issuing is refused
        #: unless this is true, so a wrong key cannot produce a Product Key.
        self._issuing_allowed = False
        self._issuing_blocked_reason = "No signing key loaded."
        # Checking a radio button emits toggled immediately, so the handlers run
        # while the rest of the page is still being built. They wait.
        self._building = True

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(16)

        # The input column scrolls. Without this Qt has nowhere to take the
        # space from on a short window and squeezes the FIRST group box until
        # its labels sit on top of its fields - which is exactly how the
        # "Customer & machine" section came to look broken. A scroll area lets
        # every row keep the height it asked for and moves the shortfall into a
        # scrollbar, so the form is correct at any window size rather than only
        # at a tall one.
        self.input_scroll = QScrollArea()
        self.input_scroll.setWidget(self._build_input())
        self.input_scroll.setWidgetResizable(True)
        self.input_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.input_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Generate License sits OUTSIDE the scroll area. It is the one control
        # that must never be somewhere the vendor has to scroll to find.
        self.generate = QPushButton("⚙  Generate License")
        self.generate.setObjectName("GenerateButton")
        self.generate.setMinimumHeight(42)
        self.generate.clicked.connect(self._submit)

        left = QWidget()
        left_col = QVBoxLayout(left)
        left_col.setContentsMargins(0, 0, 0, 0)
        left_col.setSpacing(12)
        left_col.addWidget(self.input_scroll, 1)
        left_col.addWidget(self.generate)

        root.addWidget(left, 5)
        root.addWidget(self._build_output(), 4)
        self._building = False
        self._sync_type()

    # ---- left: what to issue --------------------------------------------

    @staticmethod
    def _field(label: str, widget: QWidget) -> QWidget:
        """One labelled row: caption on its own line, control full width.

        Returned as a single widget so a caller adds one thing per row and the
        spacing between rows is set in exactly one place.
        """
        holder = QWidget()
        box = QVBoxLayout(holder)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(4)
        caption = QLabel(label)
        caption.setProperty("role", "field-label")
        # The caption never truncates: it is on its own line, and it is allowed
        # to wrap rather than being cut off, which is what a long Dari label
        # needs.
        caption.setWordWrap(True)
        caption.setBuddy(widget)
        box.addWidget(caption)
        box.addWidget(widget)
        return holder

    def _build_input(self) -> QWidget:
        panel = QWidget()
        col = QVBoxLayout(panel)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(12)

        customer = QGroupBox("Customer && Machine")
        # Each label sits ABOVE its field rather than beside it. A two-column
        # QFormLayout was clipping "Machine ID / Request Code" and overlapping
        # the rows below it: the label column is sized to the widest label, and
        # labels carrying a line break got a narrow column and a two-line
        # height that the row never reserved. Stacking removes the failure
        # instead of tuning around it - every label gets the full panel width,
        # so nothing can be cut off however long the text is, and it lays out
        # identically in Dari, where a label column would have to flip side.
        form = QVBoxLayout(customer)
        form.setContentsMargins(14, 16, 14, 14)
        form.setSpacing(10)

        self.product = QComboBox()
        for product in products.CATALOGUE:
            label = product.display_name + ("" if product.supported
                                            else "  (not yet supported)")
            self.product.addItem(label, product.product_id)
        self.product.currentIndexChanged.connect(self._sync_type)
        self.product.currentIndexChanged.connect(self._product_changed)
        form.addWidget(self._field("Product", self.product))

        # The request code is long, so it gets a box rather than a line: a
        # vendor must be able to SEE that the whole thing was pasted. Sized to
        # hold the full 81-character ZBR1 code on three lines at any sensible
        # panel width, and it grows with the window rather than staying fixed.
        self.request = QPlainTextEdit()
        self.request.setPlaceholderText(
            "Paste the customer's request code here — it starts with ZBR1-")
        # Tall enough for the whole 81-character code with room to spare even
        # when it wraps to three lines on a narrow window, and capped so it
        # cannot swallow the rest of the form.
        self.request.setMinimumHeight(78)
        self.request.setMaximumHeight(104)
        self.request.setSizePolicy(QSizePolicy.Policy.Expanding,
                                   QSizePolicy.Policy.Fixed)
        self.request.textChanged.connect(self._preview_machine)
        form.addWidget(self._field("Request Code *", self.request))

        # A read-only field rather than a bare label: it looks like the rest of
        # the form, it can be selected and copied, and it cannot be typed into.
        self.machine_preview = QLineEdit()
        self.machine_preview.setReadOnly(True)
        self.machine_preview.setPlaceholderText(
            "appears when a valid request code is pasted")
        self.machine_preview.setProperty("role", "preview")
        form.addWidget(self._field("Machine ID", self.machine_preview))

        self.customer_name = QLineEdit()
        self.customer_name.setPlaceholderText("Business or customer name")
        form.addWidget(self._field("Customer / Business Name",
                                   self.customer_name))
        self.phone = QLineEdit()
        form.addWidget(self._field("Phone", self.phone))
        self.city = QLineEdit()
        form.addWidget(self._field("City", self.city))
        self.notes = QLineEdit()
        self.notes.setPlaceholderText("Optional")
        form.addWidget(self._field("Notes", self.notes))
        col.addWidget(customer)

        licence = QGroupBox("License")
        lic = QVBoxLayout(licence)
        lic.setContentsMargins(14, 16, 14, 14)
        lic.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(18)
        self.type_group = QButtonGroup(self)
        self.type_full = QRadioButton("FULL")
        self.type_demo = QRadioButton("DEMO")
        self.type_full.setChecked(True)
        for button in (self.type_full, self.type_demo):
            self.type_group.addButton(button)
            button.toggled.connect(self._sync_type)
            row.addWidget(button)
        row.addStretch(1)
        lic.addLayout(row)

        self.demo_row = QWidget()
        demo = QHBoxLayout(self.demo_row)
        demo.setContentsMargins(0, 0, 0, 0)
        demo.setSpacing(12)
        _demo_caption = QLabel("Demo days")
        _demo_caption.setProperty("role", "field-label")
        demo.addWidget(_demo_caption)
        self.days_group = QButtonGroup(self)
        self.day_buttons: list[QRadioButton] = []
        for days in products.ZENITH_BUSINESS.demo_days:
            button = QRadioButton(str(days))
            button.setProperty("days", days)
            button.toggled.connect(self._sync_expiry)
            self.days_group.addButton(button)
            self.day_buttons.append(button)
            demo.addWidget(button)
        self.day_custom = QRadioButton("Custom")
        self.day_custom.toggled.connect(self._sync_expiry)
        self.days_group.addButton(self.day_custom)
        demo.addWidget(self.day_custom)
        self.custom_days = QSpinBox()
        self.custom_days.setRange(1, 3650)
        self.custom_days.setValue(60)
        self.custom_days.valueChanged.connect(self._sync_expiry)
        demo.addWidget(self.custom_days)
        demo.addStretch(1)
        self.day_buttons[1].setChecked(True)          # 14 days, the common case
        lic.addWidget(self.demo_row)

        self.expiry = QLineEdit()
        self.expiry.setPlaceholderText("YYYY-MM-DD")
        self.expiry.textEdited.connect(self._expiry_typed)
        lic.addWidget(self._field("Expiry date", self.expiry))
        self.license_id = QLineEdit()
        lic.addWidget(self._field("License ID", self.license_id))
        col.addWidget(licence)

        col.addStretch(1)
        return panel

    # ---- right: what to send back ---------------------------------------

    def _build_output(self) -> QWidget:
        panel = QGroupBox("Product Key")
        col = QVBoxLayout(panel)

        self.key_box = QPlainTextEdit()
        self.key_box.setReadOnly(True)
        self.key_box.setPlaceholderText(
            "The generated Product Key (ZB1-…) will appear here.")
        col.addWidget(self.key_box, 1)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setProperty("role", "summary")
        col.addWidget(self.summary)

        row = QHBoxLayout()
        self.copy_button = QPushButton("📋  Copy Product Key")
        self.copy_button.clicked.connect(self._copy)
        self.save_button = QPushButton("💾  Save .zlic")
        self.open_button = QPushButton("📁  Open License Folder")
        for button in (self.copy_button, self.save_button, self.open_button):
            button.setEnabled(False)
            row.addWidget(button)
        col.addLayout(row)

        note = QLabel(
            "Send the Product Key to the customer. They paste it into the "
            "activation screen — no file, no email attachment. The .zlic file "
            "is a fallback for when a long code gets mangled in transit.")
        note.setWordWrap(True)
        note.setProperty("role", "hint")
        col.addWidget(note)
        return panel

    # ---- reactions -------------------------------------------------------

    def current_product(self) -> products.Product:
        return products.by_id(self.product.currentData()) or products.ZENITH_BUSINESS

    def _product_changed(self) -> None:
        """Switching product changes which signing key applies, so re-check."""
        if self._building:
            return
        if self._on_product_changed is not None:
            self._on_product_changed()

    def set_issuing_allowed(self, allowed: bool, reason: str = "") -> None:
        """Enable or disable issuing, from the signing-key self-test.

        The button's tooltip carries the reason, so hovering a disabled button
        answers "why can't I?" without a dialog.
        """
        self._issuing_allowed = bool(allowed)
        self._issuing_blocked_reason = reason or "No signing key loaded."
        self.generate.setEnabled(self._issuing_allowed)
        self.generate.setToolTip("" if allowed else self._issuing_blocked_reason)

    def _sync_type(self) -> None:
        if self._building:
            return
        demo = self.type_demo.isChecked()
        self.demo_row.setVisible(demo)
        product = self.current_product()
        self.generate.setEnabled(product.supported)
        if not product.supported:
            self.summary.setText(product.notes)
        self._sync_expiry()
        self._suggest_license_id()

    def _sync_expiry(self) -> None:
        if self._building:
            return
        if not self.type_demo.isChecked():
            # FULL has no expiry by default; a vendor may still type one.
            self.expiry.setPlaceholderText("none — FULL licenses do not expire")
            self.expiry.clear()
            return
        self.expiry.setPlaceholderText("YYYY-MM-DD")
        days = self.selected_days()
        if days:
            self.expiry.setText((date.today() + timedelta(days=days)).isoformat())

    def _expiry_typed(self) -> None:
        """A typed date wins over the day buttons, so untick them."""
        button = self.days_group.checkedButton()
        if button is not None and button is not self.day_custom:
            self.days_group.setExclusive(False)
            button.setChecked(False)
            self.days_group.setExclusive(True)

    def selected_days(self) -> int | None:
        if not self.type_demo.isChecked():
            return None
        if self.day_custom.isChecked():
            return int(self.custom_days.value())
        button = self.days_group.checkedButton()
        return int(button.property("days")) if button is not None else None

    def _suggest_license_id(self) -> None:
        product = self.current_product()
        kind = "DEMO" if self.type_demo.isChecked() else "FULL"
        try:
            serial = self._next_serial(product.product_id, kind)
        except Exception:
            serial = 1
        self.license_id.setText(product.license_id(kind, serial))

    def _preview_machine(self) -> None:
        if self._building:
            return
        text = self.request.toPlainText().strip()
        if not text:
            self.machine_preview.setText("—")
            return
        try:
            request = issuing.parse_request(text)
        except issuing.IssueError as exc:
            self.machine_preview.setText(f"⚠  {exc}")
            return
        self.machine_preview.setText(request.machine_short)

    # ---- generate --------------------------------------------------------

    def _submit(self) -> None:
        values = {
            "product_id": self.current_product().product_id,
            "request_code": self.request.toPlainText().strip(),
            "license_type": "DEMO" if self.type_demo.isChecked() else "FULL",
            "issued_to": self.customer_name.text().strip(),
            "phone": self.phone.text().strip(),
            "city": self.city.text().strip(),
            "notes": self.notes.text().strip(),
            "demo_days": self.selected_days(),
            "expires_at": self.expiry.text().strip() or None,
            "license_id": self.license_id.text().strip() or None,
        }
        if not self._issuing_allowed:
            QMessageBox.critical(self, "Cannot issue this license",
                                 self._issuing_blocked_reason)
            return
        if not values["request_code"]:
            QMessageBox.warning(self, "Machine ID required",
                                "Paste the request code the customer sent you.")
            return
        self._on_generate(values)

    def show_issued(self, issued) -> None:
        """Display a licence that was just signed."""
        self._issued = issued
        self.key_box.setPlainText(issued.product_key)
        expiry = issued.expires_at or "never"
        days = f" ({issued.demo_days} days)" if issued.demo_days else ""
        self.summary.setText(
            f"{issued.license_id} · {issued.license_type} · "
            f"machine {issued.machine_short} · expires {expiry}{days}")
        for button in (self.copy_button, self.save_button, self.open_button):
            button.setEnabled(True)
        self._suggest_license_id()

    def _copy(self) -> None:
        from PyQt6.QtWidgets import QApplication

        if self._issued is None:
            return
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._issued.product_key)
        self.summary.setText("Product Key copied — send it to the customer.")

    @property
    def issued(self):
        return self._issued
