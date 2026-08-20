"""Stage 03 master-data screens (§10, §13-§21).

Each page composes the shared :class:`ManagementPage` / :class:`FormDialog`, loads
data through services (never SQL), and surfaces service ``user_message`` errors.
Pages are bilingual and inherit RTL/LTR from the shell.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Translator
from zenith_business.core.money import D, format_money
from zenith_business.services.context import ApplicationContext
from zenith_business.services.exceptions import ZenithError
from zenith_business.ui.components import (
    Card,
    field_label,
    ghost_button,
    page_subtitle,
    page_title,
    primary_button,
    secondary,
    section_title,
)
from zenith_business.ui.design.tokens import FieldWidth, Spacing
from zenith_business.ui.master.framework import Column, FormDialog, ManagementPage


def _t(tr: Translator, key: str) -> str:
    return tr.gettext(key)


class _BasePage(QWidget):
    """Common wiring: hold the context + translator, reload on show."""

    def __init__(self, ctx: ApplicationContext, translator: Translator,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._ctx = ctx
        self._t = translator
        self.page: ManagementPage | None = None

    def reload(self) -> None:  # overridden
        pass

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        if self.page is not None:
            self.page.retranslate(translator)


# ------------------------------------------------------------------ Items ---

class ItemsPage(_BasePage):
    def __init__(self, ctx, translator, parent=None) -> None:
        super().__init__(ctx, translator, parent)
        columns = [
            Column("item_code", "items.col_code", width=110),
            Column("name", "items.col_name", stretch=True),
            Column("alternate_name", "items.col_altname", width=160),
            Column("barcode", "items.col_barcode", width=120),
            Column("purchase_display", "items.col_purchase", width=110, align="r"),
            Column("sale_display", "items.col_sale", width=110, align="r"),
            Column("is_active", "items.col_status", width=110, kind="status"),
        ]
        self.page = ManagementPage(
            translator, title_key="items.title", subtitle_key=None, columns=columns,
            new_label_key="items.new", on_new=self._new, on_edit=self._edit,
            on_toggle_active=self._toggle)
        self.page.connect_refresh(self.reload)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.page)

    def reload(self) -> None:
        rows = self._ctx.items.list()
        for r in rows:
            r["purchase_display"] = format_money(r["purchase_price"])
            r["sale_display"] = format_money(r["default_sale_price"])
        self.page.set_rows(rows)

    def _dialog(self, existing: dict | None) -> None:
        t = self._t
        title = _t(t, "items.edit_title" if existing else "items.new")
        dlg = FormDialog(t, title, parent=self.window())
        g1 = dlg.add_section(_t(t, "items.sec_general"))
        code = QLineEdit(); name = QLineEdit(); alt = QLineEdit(); barcode = QLineEdit()
        dlg.add_field(g1, 0, 0, _t(t, "items.col_code"), code, width=FieldWidth.SM)
        dlg.add_field(g1, 0, 1, _t(t, "items.col_barcode"), barcode, width=FieldWidth.MD)
        dlg.add_field(g1, 1, 0, _t(t, "items.col_name"), name, width=FieldWidth.LG)
        dlg.add_field(g1, 1, 1, _t(t, "items.col_altname"), alt, width=FieldWidth.MD)

        g2 = dlg.add_section(_t(t, "items.sec_classification"))
        cat = QComboBox(); cat.addItem(_t(t, "md.all"), None)
        for c in self._ctx.categories_repo.list_active():
            cat.addItem(c["name_en"], c["id"])
        unit = QComboBox()
        for u in self._ctx.units_repo.list_active():
            unit.addItem(f"{u['name_en']} ({u['code']})", u["id"])
        stockable = QCheckBox(_t(t, "items.f_stockable")); stockable.setChecked(True)
        dlg.add_field(g2, 0, 0, _t(t, "items.col_category"), cat, width=FieldWidth.MD)
        dlg.add_field(g2, 0, 1, _t(t, "items.col_unit"), unit, width=FieldWidth.MD)
        g2.addWidget(stockable, 1, 0, 1, 2)

        g3 = dlg.add_section(_t(t, "items.sec_pricing"))
        purchase = QLineEdit("0.00"); sale = QLineEdit("0.00"); minstock = QLineEdit("0")
        dlg.add_field(g3, 0, 0, _t(t, "items.col_purchase"), purchase, width=FieldWidth.SM)
        dlg.add_field(g3, 0, 1, _t(t, "items.col_sale"), sale, width=FieldWidth.SM)
        g4 = dlg.add_section(_t(t, "items.sec_inventory"))
        dlg.add_field(g4, 0, 0, _t(t, "items.col_min"), minstock, width=FieldWidth.SM)

        # Opening Stock — creating an inventory-controlled item can record its
        # current stock via the EXISTING inventory.record_opening service (one
        # OPENING movement). Only offered on create (editing opening stock after
        # the fact would corrupt stock history — "opening" vs "current" stock).
        opening_qty = QLineEdit("0")
        opening_wh = QComboBox()
        for w in self._ctx.warehouses_repo.list_active():
            opening_wh.addItem(w["name"], w["id"])
            if w.get("is_default"):
                opening_wh.setCurrentIndex(opening_wh.count() - 1)
        opening_widgets = []
        if existing is None:
            dlg.add_field(g4, 0, 1, _t(t, "items.f_opening_qty"), opening_qty,
                          width=FieldWidth.SM)
            dlg.add_field(g4, 1, 0, _t(t, "items.f_opening_wh"), opening_wh,
                          width=FieldWidth.MD)
            hint = secondary(_t(t, "items.opening_hint")); hint.setWordWrap(True)
            g4.addWidget(hint, 2, 0, 1, 2)
            opening_widgets = [opening_qty, opening_wh]

            def _sync_opening() -> None:
                on = stockable.isChecked()
                for w in opening_widgets:
                    w.setEnabled(on)
            stockable.toggled.connect(lambda _c: _sync_opening())
            _sync_opening()

        if existing:
            code.setText(existing["item_code"]); code.setEnabled(False)
            name.setText(existing["name"]); alt.setText(existing.get("alternate_name") or "")
            barcode.setText(existing.get("barcode") or "")
            purchase.setText(str(existing["purchase_price"]))
            sale.setText(str(existing["default_sale_price"]))
            minstock.setText(str(existing["reorder_level"]))
            stockable.setChecked(bool(existing["track_inventory"]))
            _select(unit, existing["base_unit_id"]); _select(cat, existing.get("category_id"))

        def submit() -> None:
            try:
                if existing:
                    self._ctx.items.update(
                        existing["id"], name=name.text(), base_unit_id=unit.currentData(),
                        barcode=barcode.text(), alternate_name=alt.text(),
                        category_id=cat.currentData(), purchase_price=purchase.text(),
                        default_sale_price=sale.text(), reorder_level=minstock.text(),
                        track_inventory=stockable.isChecked())
                else:
                    new_id = self._ctx.items.create(
                        item_code=code.text(), name=name.text(), base_unit_id=unit.currentData(),
                        barcode=barcode.text(), alternate_name=alt.text(),
                        category_id=cat.currentData(), purchase_price=purchase.text(),
                        default_sale_price=sale.text(), reorder_level=minstock.text(),
                        track_inventory=stockable.isChecked())
                    # Record opening stock via the EXISTING inventory service (one
                    # OPENING movement) when a stockable item is created with a
                    # positive opening quantity and a warehouse is chosen.
                    if (stockable.isChecked()
                            and D(opening_qty.text() or "0") > 0
                            and opening_wh.currentData() is not None):
                        self._ctx.inventory.record_opening(
                            item_id=new_id, warehouse_id=opening_wh.currentData(),
                            quantity_on_hand=opening_qty.text())
            except ZenithError as exc:
                dlg.set_error(exc.user_message); return
            dlg.accept(); self.reload()

        dlg.set_submit(submit)
        dlg.exec()

    def _new(self) -> None:
        self._dialog(None)

    def _edit(self, row: dict) -> None:
        self._dialog(self._ctx.items.get(row["id"]))

    def _toggle(self, row: dict) -> None:
        self._ctx.items.set_active(row["id"], not bool(row.get("is_active", 1)))
        self.reload()


# ----------------------------------------------------------------- Persons --

class PersonsPage(_BasePage):
    def __init__(self, ctx, translator, parent=None) -> None:
        super().__init__(ctx, translator, parent)
        columns = [
            Column("party_code", "persons.col_code", width=110),
            Column("name", "persons.col_name", stretch=True),
            Column("company_name", "persons.col_company", width=180),
            Column("phone", "persons.col_phone", width=130),
            Column("roles_display", "persons.col_roles", width=160),
            Column("is_active", "persons.col_status", width=110, kind="status"),
        ]
        self._on_view_account = None  # set by main window (contextual ledger, round 2)
        self.page = ManagementPage(
            translator, title_key="persons.title", subtitle_key=None, columns=columns,
            new_label_key="persons.new", on_new=self._new, on_edit=self._edit,
            on_toggle_active=self._toggle, on_view=self._view, view_label_key="md.view")
        self.page.connect_refresh(self.reload)
        self._role_filter = QComboBox()
        for key, val in (("md.all", None), ("persons.role_customer", "customer"),
                         ("persons.role_supplier", "supplier"), ("persons.role_both", "both")):
            self._role_filter.addItem(_t(translator, key), val)
        self._role_filter.currentIndexChanged.connect(lambda _i: self.reload())
        self.page.add_filter(self._role_filter)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.addWidget(self.page)

    def reload(self) -> None:
        role = self._role_filter.currentData()
        rows = self._ctx.parties.list(role=role)
        for r in rows:
            marks = []
            if r["is_customer"]:
                marks.append(_t(self._t, "persons.f_customer"))
            if r["is_supplier"]:
                marks.append(_t(self._t, "persons.f_supplier"))
            r["roles_display"] = " + ".join(marks)
        self.page.set_rows(rows)

    def set_view_account_handler(self, handler) -> None:
        """Wire the contextual 'View Account' action (party_id, role) -> ledger."""
        self._on_view_account = handler

    def _view(self, row: dict) -> None:
        if self._on_view_account is None:
            return
        role = "customer" if row.get("is_customer") else "supplier"
        self._on_view_account(row["id"], role)

    def _dialog(self, existing: dict | None) -> None:
        t = self._t
        title = _t(t, "persons.edit_title" if existing else "persons.new")
        dlg = FormDialog(t, title, parent=self.window())
        g1 = dlg.add_section(_t(t, "persons.sec_identity"))
        code = QLineEdit(); name = QLineEdit(); company = QLineEdit()
        is_cust = QCheckBox(_t(t, "persons.f_customer")); is_cust.setChecked(True)
        is_sup = QCheckBox(_t(t, "persons.f_supplier"))
        dlg.add_field(g1, 0, 0, _t(t, "persons.col_code"), code, width=FieldWidth.SM)
        dlg.add_field(g1, 0, 1, _t(t, "persons.col_company"), company, width=FieldWidth.LG)
        dlg.add_field(g1, 1, 0, _t(t, "persons.col_name"), name, width=FieldWidth.LG)
        roles_row = QHBoxLayout(); roles_row.addWidget(is_cust); roles_row.addWidget(is_sup)
        roles_row.addStretch(1)
        roles_host = QWidget(); roles_host.setLayout(roles_row)
        g1.addWidget(roles_host, 2, 0, 1, 2)

        g2 = dlg.add_section(_t(t, "persons.sec_contact"))
        phone = QLineEdit(); email = QLineEdit(); address = QLineEdit()
        dlg.add_field(g2, 0, 0, _t(t, "persons.col_phone"), phone, width=FieldWidth.MD)
        dlg.add_field(g2, 0, 1, _t(t, "co.email"), email, width=FieldWidth.MD)
        dlg.add_field(g2, 1, 0, _t(t, "co.address"), address, width=FieldWidth.XL)

        g3 = dlg.add_section(_t(t, "persons.sec_financial"))
        credit = QLineEdit("0.00"); opening = QLineEdit("0.00")
        dlg.add_field(g3, 0, 0, _t(t, "si.credit_limit"), credit, width=FieldWidth.SM)
        dlg.add_field(g3, 0, 1, _t(t, "si.prev_balance"), opening, width=FieldWidth.SM)

        if existing:
            code.setText(existing["party_code"]); code.setEnabled(False)
            name.setText(existing["name"]); company.setText(existing.get("company_name") or "")
            is_cust.setChecked(bool(existing["is_customer"]))
            is_sup.setChecked(bool(existing["is_supplier"]))
            phone.setText(existing.get("phone") or ""); email.setText(existing.get("email") or "")
            address.setText(existing.get("address") or "")
            credit.setText(str(existing["credit_limit"]))
            opening.setText(str(existing["opening_balance"]))

        def submit() -> None:
            try:
                if existing:
                    self._ctx.parties.update(
                        existing["id"], name=name.text(), is_customer=is_cust.isChecked(),
                        is_supplier=is_sup.isChecked(), company_name=company.text(),
                        phone=phone.text(), email=email.text(), address=address.text(),
                        credit_limit=credit.text(), opening_balance=opening.text())
                else:
                    self._ctx.parties.create(
                        party_code=code.text(), name=name.text(),
                        is_customer=is_cust.isChecked(), is_supplier=is_sup.isChecked(),
                        company_name=company.text(), phone=phone.text(), email=email.text(),
                        address=address.text(), credit_limit=credit.text(),
                        opening_balance=opening.text())
            except ZenithError as exc:
                dlg.set_error(exc.user_message); return
            dlg.accept(); self.reload()

        dlg.set_submit(submit)
        dlg.exec()

    def _new(self) -> None:
        self._dialog(None)

    def _edit(self, row: dict) -> None:
        self._dialog(self._ctx.parties.get(row["id"]))

    def _toggle(self, row: dict) -> None:
        self._ctx.parties.set_active(row["id"], not bool(row.get("is_active", 1)))
        self.reload()


# -------------------------------------------------------------- Warehouses --

class WarehousesPage(_BasePage):
    def __init__(self, ctx, translator, parent=None) -> None:
        super().__init__(ctx, translator, parent)
        columns = [
            Column("code", "wh.col_code", width=110),
            Column("name", "wh.col_name", stretch=True),
            Column("address", "wh.col_address", width=200),
            Column("phone", "wh.col_phone", width=130),
            Column("default_display", "wh.col_default", width=100, align="c"),
            Column("is_active", "wh.col_status", width=110, kind="status"),
        ]
        self.page = ManagementPage(
            translator, title_key="wh.title", subtitle_key=None, columns=columns,
            new_label_key="wh.new", on_new=self._new, on_edit=self._edit,
            on_toggle_active=self._toggle)
        self.page.connect_refresh(self.reload)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.addWidget(self.page)

    def reload(self) -> None:
        rows = self._ctx.warehouses.list()
        for r in rows:
            r["default_display"] = "★" if r.get("is_default") else ""
        self.page.set_rows(rows)

    def _dialog(self, existing: dict | None) -> None:
        t = self._t
        dlg = FormDialog(t, _t(t, "wh.edit_title" if existing else "wh.new"),
                         parent=self.window())
        g = dlg.add_section(_t(t, "wh.title"))
        code = QLineEdit(); name = QLineEdit(); address = QLineEdit(); phone = QLineEdit()
        notes = QLineEdit(); is_default = QCheckBox(_t(t, "wh.f_default"))
        dlg.add_field(g, 0, 0, _t(t, "wh.col_code"), code, width=FieldWidth.SM)
        dlg.add_field(g, 0, 1, _t(t, "wh.col_phone"), phone, width=FieldWidth.MD)
        dlg.add_field(g, 1, 0, _t(t, "wh.col_name"), name, width=FieldWidth.LG)
        dlg.add_field(g, 2, 0, _t(t, "wh.col_address"), address, width=FieldWidth.XL)
        dlg.add_field(g, 3, 0, _t(t, "wh.f_notes"), notes, width=FieldWidth.XL)
        g.addWidget(is_default, 4, 0, 1, 2)
        if existing:
            code.setText(existing["code"]); code.setEnabled(False)
            name.setText(existing["name"]); address.setText(existing.get("address") or "")
            phone.setText(existing.get("phone") or ""); notes.setText(existing.get("notes") or "")
            is_default.setChecked(bool(existing.get("is_default")))

        def submit() -> None:
            try:
                if existing:
                    self._ctx.warehouses.update(existing["id"], name=name.text(),
                                                address=address.text(), phone=phone.text(),
                                                notes=notes.text())
                    if is_default.isChecked() and not existing.get("is_default"):
                        self._ctx.warehouses.set_default(existing["id"])
                else:
                    self._ctx.warehouses.create(
                        code=code.text(), name=name.text(), address=address.text(),
                        phone=phone.text(), notes=notes.text(),
                        is_default=is_default.isChecked())
            except ZenithError as exc:
                dlg.set_error(exc.user_message); return
            dlg.accept(); self.reload()

        dlg.set_submit(submit)
        dlg.exec()

    def _new(self) -> None:
        self._dialog(None)

    def _edit(self, row: dict) -> None:
        self._dialog(self._ctx.warehouses_repo.get(row["id"]))

    def _toggle(self, row: dict) -> None:
        self._ctx.warehouses.set_active(row["id"], not bool(row.get("is_active", 1)))
        self.reload()


# ------------------------------------------------------------ Financial Yr --

class FinancialYearsPage(_BasePage):
    def __init__(self, ctx, translator, parent=None) -> None:
        super().__init__(ctx, translator, parent)
        columns = [
            Column("name", "fy.col_name", stretch=True),
            Column("start_date", "fy.col_start", width=140),
            Column("end_date", "fy.col_end", width=140),
            Column("status_display", "fy.col_status", width=110),
            Column("active_display", "fy.col_active", width=90, align="c"),
        ]
        self.page = ManagementPage(
            translator, title_key="fy.title", subtitle_key=None, columns=columns,
            new_label_key="fy.new", on_new=self._new, on_edit=self._actions)
        self.page.connect_refresh(self.reload)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.addWidget(self.page)

    def reload(self) -> None:
        rows = self._ctx.financial_years.list()
        for r in rows:
            r["status_display"] = _t(self._t,
                "fy.status_open" if r["status"] == "OPEN" else "fy.status_closed")
            r["active_display"] = "★" if r.get("is_active") else ""
        self.page.set_rows(rows)

    def _new(self) -> None:
        t = self._t
        dlg = FormDialog(t, _t(t, "fy.new"), parent=self.window())
        g = dlg.add_section(_t(t, "fy.title"))
        name = QLineEdit(); start = QLineEdit(); end = QLineEdit()
        make_active = QCheckBox(_t(t, "fy.f_make_active")); make_active.setChecked(True)
        dlg.add_field(g, 0, 0, _t(t, "fy.f_name"), name, width=FieldWidth.MD)
        dlg.add_field(g, 1, 0, _t(t, "fy.f_start"), start, width=FieldWidth.MD)
        dlg.add_field(g, 1, 1, _t(t, "fy.f_end"), end, width=FieldWidth.MD)
        g.addWidget(make_active, 2, 0, 1, 2)

        def submit() -> None:
            try:
                self._ctx.financial_years.create(
                    name=name.text(), start_date=start.text().strip(),
                    end_date=end.text().strip(), make_active=make_active.isChecked())
            except ZenithError as exc:
                dlg.set_error(exc.user_message); return
            dlg.accept(); self.reload()

        dlg.set_submit(submit)
        dlg.exec()

    def _actions(self, row: dict) -> None:
        """Edit action opens a small activate/close chooser."""
        t = self._t
        dlg = FormDialog(t, row["name"], parent=self.window())
        dlg.add_section(row["name"])
        bar = QHBoxLayout()
        if row["status"] == "OPEN" and not row.get("is_active"):
            b = primary_button(_t(t, "fy.set_active"))
            b.clicked.connect(lambda: self._do(lambda: self._ctx.financial_years.set_active(row["id"]), dlg))
            bar.addWidget(b)
        if row["status"] == "OPEN":
            c = ghost_button(_t(t, "fy.close"))
            c.clicked.connect(lambda: self._do(lambda: self._ctx.financial_years.close(row["id"]), dlg))
            bar.addWidget(c)
        bar.addStretch(1)
        host = QWidget(); host.setLayout(bar)
        dlg._body.addWidget(host)  # noqa: SLF001 - intentional compose
        dlg._save.setVisible(False)
        dlg.exec()

    def _do(self, action: Callable[[], None], dlg: QDialog) -> None:
        try:
            action()
        except ZenithError as exc:
            dlg.set_error(exc.user_message); return
        dlg.accept(); self.reload()


# ------------------------------------------------------------------- Users --

class UsersPage(_BasePage):
    def __init__(self, ctx, translator, parent=None) -> None:
        super().__init__(ctx, translator, parent)
        columns = [
            Column("username", "usr.col_username", width=160),
            Column("full_name", "usr.col_fullname", stretch=True),
            Column("roles_display", "usr.col_roles", width=200),
            Column("is_active", "usr.col_status", width=110, kind="status"),
        ]
        self.page = ManagementPage(
            translator, title_key="usr.title", subtitle_key=None, columns=columns,
            new_label_key="usr.new", on_new=self._new, on_edit=self._edit,
            on_toggle_active=self._toggle)
        self.page.connect_refresh(self.reload)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.addWidget(self.page)

    def reload(self) -> None:
        rows = self._ctx.users.list_users()
        for r in rows:
            roles = self._ctx.users_repo.roles_for_user(r["id"])
            r["roles_display"] = ", ".join(x["name"] for x in roles)
        self.page.set_rows(rows)

    def _new(self) -> None:
        t = self._t
        dlg = FormDialog(t, _t(t, "usr.new"), parent=self.window())
        g = dlg.add_section(_t(t, "usr.sec_account"))
        username = QLineEdit(); fullname = QLineEdit(); password = QLineEdit()
        password.setEchoMode(QLineEdit.EchoMode.Password)
        dlg.add_field(g, 0, 0, _t(t, "usr.f_username"), username, width=FieldWidth.MD)
        dlg.add_field(g, 0, 1, _t(t, "usr.f_fullname"), fullname, width=FieldWidth.LG)
        dlg.add_field(g, 1, 0, _t(t, "usr.f_password"), password, width=FieldWidth.MD)
        g2 = dlg.add_section(_t(t, "usr.sec_access"))
        role = QComboBox()
        for r in self._ctx.roles_repo.list_all():
            role.addItem(r["name"], r["code"])
        dlg.add_field(g2, 0, 0, _t(t, "usr.f_role"), role, width=FieldWidth.MD)

        def submit() -> None:
            try:
                self._ctx.users.create_user(
                    username=username.text(), password=password.text(),
                    full_name=fullname.text(), role_codes=[role.currentData()])
            except ZenithError as exc:
                dlg.set_error(exc.user_message); return
            dlg.accept(); self.reload()

        dlg.set_submit(submit)
        dlg.exec()

    def _edit(self, row: dict) -> None:
        t = self._t
        dlg = FormDialog(t, _t(t, "usr.edit_title"), parent=self.window())
        g = dlg.add_section(_t(t, "usr.sec_account"))
        fullname = QLineEdit(row["full_name"])
        newpw = QLineEdit(); newpw.setEchoMode(QLineEdit.EchoMode.Password)
        dlg.add_field(g, 0, 0, _t(t, "usr.f_fullname"), fullname, width=FieldWidth.LG)
        dlg.add_field(g, 1, 0, _t(t, "usr.reset_pw"), newpw, width=FieldWidth.MD)
        g2 = dlg.add_section(_t(t, "usr.sec_access"))
        role = QComboBox()
        current = {x["code"] for x in self._ctx.users_repo.roles_for_user(row["id"])}
        for r in self._ctx.roles_repo.list_all():
            role.addItem(r["name"], r["code"])
        for i in range(role.count()):
            if role.itemData(i) in current:
                role.setCurrentIndex(i); break
        dlg.add_field(g2, 0, 0, _t(t, "usr.f_role"), role, width=FieldWidth.MD)

        def submit() -> None:
            try:
                self._ctx.users.update_profile(row["id"], full_name=fullname.text())
                self._ctx.users.set_roles(row["id"], [role.currentData()])
                if newpw.text().strip():
                    self._ctx.users.reset_password(row["id"], newpw.text())
            except ZenithError as exc:
                dlg.set_error(exc.user_message); return
            dlg.accept(); self.reload()

        dlg.set_submit(submit)
        dlg.exec()

    def _toggle(self, row: dict) -> None:
        try:
            self._ctx.users.set_active(row["id"], not bool(row.get("is_active", 1)))
        except ZenithError:
            pass  # last-admin protection surfaces via the row staying active
        self.reload()


# --------------------------------------------------------- Units/Categories -

class UnitsPage(_BasePage):
    def __init__(self, ctx, translator, parent=None) -> None:
        super().__init__(ctx, translator, parent)
        columns = [
            Column("code", "unit.col_code", width=110),
            Column("name_en", "unit.col_en", stretch=True),
            Column("name_fa", "unit.col_fa", width=180),
            Column("symbol", "unit.col_symbol", width=90),
            Column("is_active", "md.active", width=110, kind="status"),
        ]
        self.page = ManagementPage(
            translator, title_key="unit.title", subtitle_key=None, columns=columns,
            new_label_key="unit.new", on_new=self._new, on_edit=self._edit,
            on_toggle_active=self._toggle)
        self.page.connect_refresh(self.reload)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.addWidget(self.page)

    def reload(self) -> None:
        self.page.set_rows(self._ctx.units.list())

    def _dialog(self, existing) -> None:
        t = self._t
        dlg = FormDialog(t, _t(t, "unit.new"), parent=self.window())
        g = dlg.add_section(_t(t, "unit.title"))
        code = QLineEdit(); en = QLineEdit(); fa = QLineEdit(); sym = QLineEdit()
        dec = QCheckBox(_t(t, "unit.f_decimal")); dec.setChecked(True)
        dlg.add_field(g, 0, 0, _t(t, "unit.col_code"), code, width=FieldWidth.SM)
        dlg.add_field(g, 0, 1, _t(t, "unit.col_symbol"), sym, width=FieldWidth.SM)
        dlg.add_field(g, 1, 0, _t(t, "unit.col_en"), en, width=FieldWidth.MD)
        dlg.add_field(g, 1, 1, _t(t, "unit.col_fa"), fa, width=FieldWidth.MD)
        g.addWidget(dec, 2, 0, 1, 2)
        if existing:
            code.setText(existing["code"]); code.setEnabled(False)
            en.setText(existing["name_en"]); fa.setText(existing["name_fa"])
            sym.setText(existing.get("symbol") or ""); dec.setChecked(bool(existing["decimal_allowed"]))

        def submit() -> None:
            try:
                if existing:
                    self._ctx.units.update(existing["id"], name_en=en.text(), name_fa=fa.text(),
                                           symbol=sym.text(), decimal_allowed=dec.isChecked())
                else:
                    self._ctx.units.create(code=code.text(), name_en=en.text(), name_fa=fa.text(),
                                           symbol=sym.text(), decimal_allowed=dec.isChecked())
            except ZenithError as exc:
                dlg.set_error(exc.user_message); return
            dlg.accept(); self.reload()

        dlg.set_submit(submit)
        dlg.exec()

    def _new(self) -> None:
        self._dialog(None)

    def _edit(self, row) -> None:
        self._dialog(self._ctx.units_repo.get(row["id"]))

    def _toggle(self, row) -> None:
        self._ctx.units.set_active(row["id"], not bool(row.get("is_active", 1)))
        self.reload()


class CategoriesPage(_BasePage):
    def __init__(self, ctx, translator, parent=None) -> None:
        super().__init__(ctx, translator, parent)
        columns = [
            Column("code", "cat.col_code", width=110),
            Column("name_en", "cat.col_en", stretch=True),
            Column("name_fa", "cat.col_fa", width=200),
            Column("is_active", "md.active", width=110, kind="status"),
        ]
        self.page = ManagementPage(
            translator, title_key="cat.title", subtitle_key=None, columns=columns,
            new_label_key="cat.new", on_new=self._new, on_edit=self._edit,
            on_toggle_active=self._toggle)
        self.page.connect_refresh(self.reload)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.addWidget(self.page)

    def reload(self) -> None:
        self.page.set_rows(self._ctx.categories.list())

    def _dialog(self, existing) -> None:
        t = self._t
        dlg = FormDialog(t, _t(t, "cat.new"), parent=self.window())
        g = dlg.add_section(_t(t, "cat.title"))
        code = QLineEdit(); en = QLineEdit(); fa = QLineEdit()
        parent = QComboBox(); parent.addItem(_t(t, "cat.parent_none"), None)
        for cparent in self._ctx.categories_repo.list_active():
            if not existing or cparent["id"] != existing["id"]:  # can't parent to self
                parent.addItem(cparent["name_en"], cparent["id"])
        dlg.add_field(g, 0, 0, _t(t, "cat.col_code"), code, width=FieldWidth.SM)
        dlg.add_field(g, 0, 1, _t(t, "cat.col_parent"), parent, width=FieldWidth.MD)
        dlg.add_field(g, 1, 0, _t(t, "cat.col_en"), en, width=FieldWidth.MD)
        dlg.add_field(g, 1, 1, _t(t, "cat.col_fa"), fa, width=FieldWidth.MD)
        if existing:
            code.setText(existing["code"]); code.setEnabled(False)
            en.setText(existing["name_en"]); fa.setText(existing["name_fa"])
            _select(parent, existing.get("parent_id"))

        def submit() -> None:
            try:
                if existing:
                    self._ctx.categories.update(existing["id"], name_en=en.text(),
                                                name_fa=fa.text(), parent_id=parent.currentData())
                else:
                    self._ctx.categories.create(code=code.text(), name_en=en.text(),
                                                name_fa=fa.text(), parent_id=parent.currentData())
            except ZenithError as exc:
                dlg.set_error(exc.user_message); return
            dlg.accept(); self.reload()

        dlg.set_submit(submit)
        dlg.exec()

    def _new(self) -> None:
        self._dialog(None)

    def _edit(self, row) -> None:
        self._dialog(self._ctx.categories_repo.get(row["id"]))

    def _toggle(self, row) -> None:
        self._ctx.categories.set_active(row["id"], not bool(row.get("is_active", 1)))
        self.reload()


# ------------------------------------------------------------------- Roles --

class RolesPage(_BasePage):
    def __init__(self, ctx, translator, parent=None) -> None:
        super().__init__(ctx, translator, parent)
        columns = [
            Column("name", "role.col_name", stretch=True),
            Column("code", "role.col_code", width=160),
            Column("perm_count", "role.col_perms", width=140, align="c"),
        ]
        self.page = ManagementPage(
            translator, title_key="role.title", subtitle_key=None, columns=columns,
            new_label_key="md.new", on_new=None, on_edit=self._edit_perms)
        self.page.connect_refresh(self.reload)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.addWidget(self.page)

    def reload(self) -> None:
        rows = self._ctx.roles.list_roles()
        for r in rows:
            r["perm_count"] = len(self._ctx.roles.permissions_for_role(r["id"]))
        self.page.set_rows(rows)

    def _edit_perms(self, row: dict) -> None:
        t = self._t
        dlg = FormDialog(t, f"{row['name']} — {_t(t, 'role.edit_perms')}", parent=self.window())
        current = self._ctx.roles.permissions_for_role(row["id"])
        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setMinimumHeight(360)
        holder = QWidget(); col = QVBoxLayout(holder); col.setSpacing(Spacing.SM)
        checks: dict[str, QCheckBox] = {}
        for group, pairs in self._ctx.roles.permission_groups():
            col.addWidget(section_title(group.title()))
            for code, label in pairs:
                cb = QCheckBox(label); cb.setChecked(code in current)
                checks[code] = cb
                col.addWidget(cb)
        col.addStretch(1)
        scroll.setWidget(holder)
        dlg._body.addWidget(scroll)  # noqa: SLF001

        def submit() -> None:
            selected = [c for c, cb in checks.items() if cb.isChecked()]
            try:
                self._ctx.roles.set_permissions(row["id"], selected)
            except ZenithError as exc:
                dlg.set_error(exc.user_message); return
            dlg.accept(); self.reload()

        dlg.set_submit(submit)
        dlg.exec()


# ----------------------------------------------------------------- Company --

class CompanyPage(_BasePage):
    """Single-record settings form (not a list)."""

    def __init__(self, ctx, translator, parent=None) -> None:
        super().__init__(ctx, translator, parent)
        t = translator
        page_outer = QVBoxLayout(self)
        page_outer.setContentsMargins(0, 0, 0, 0)
        # A scroll area keeps the tall settings form from compressing/overlapping
        # on short windows — it scrolls instead (same pattern as the auth screens).
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        page_outer.addWidget(scroll)
        holder = QWidget()
        scroll.setWidget(holder)
        outer = QVBoxLayout(holder)
        outer.setContentsMargins(Spacing.PAGE_MARGIN, Spacing.PAGE_MARGIN,
                                 Spacing.PAGE_MARGIN, Spacing.PAGE_MARGIN)
        self._title = page_title(_t(t, "co.title"))
        self._subtitle = page_subtitle(_t(t, "co.subtitle"))
        outer.addWidget(self._title)
        outer.addWidget(self._subtitle)
        outer.addSpacing(Spacing.MD)

        card = Card(role="section"); card.setMaximumWidth(820)
        self._error = None
        from zenith_business.ui.components import error_label
        self._error = error_label(""); self._error.setVisible(False)
        card.body.addWidget(self._error)

        def sec(title_key):
            card.body.addWidget(section_title(_t(t, title_key)))
            g = QGridLayout(); g.setHorizontalSpacing(Spacing.FIELD_HGAP)
            g.setVerticalSpacing(Spacing.FIELD_VGAP); card.body.addLayout(g)
            return g

        def add(grid, r, c, label, w, width=None):
            box = QVBoxLayout(); box.setSpacing(Spacing.XXS)
            box.addWidget(field_label(_t(t, label)))
            if width:
                w.setMinimumWidth(int(width))
            box.addWidget(w)
            host = QWidget(); host.setLayout(box); grid.addWidget(host, r, c)
            return w

        g1 = sec("co.sec_identity")
        self.legal = QLineEdit(); self.display = QLineEdit()
        self.tax = QLineEdit(); self.reg = QLineEdit()
        add(g1, 0, 0, "co.legal_name", self.legal, FieldWidth.LG)
        add(g1, 0, 1, "co.display_name", self.display, FieldWidth.MD)
        add(g1, 1, 0, "co.tax_id", self.tax, FieldWidth.MD)
        add(g1, 1, 1, "co.reg_no", self.reg, FieldWidth.MD)

        g2 = sec("co.sec_contact")
        self.address = QLineEdit(); self.city = QLineEdit(); self.phone = QLineEdit()
        self.email = QLineEdit(); self.website = QLineEdit()
        add(g2, 0, 0, "co.address", self.address, FieldWidth.XL)
        add(g2, 1, 0, "co.city", self.city, FieldWidth.MD)
        add(g2, 1, 1, "co.phone", self.phone, FieldWidth.MD)
        add(g2, 2, 0, "co.email", self.email, FieldWidth.MD)
        add(g2, 2, 1, "co.website", self.website, FieldWidth.MD)

        g3 = sec("co.sec_defaults")
        self.currency = QComboBox()
        for cur in self._ctx.currencies_repo.list_active():
            self.currency.addItem(f"{cur['code']} — {cur['name']}", cur["id"])
        self.warehouse = QComboBox()
        self.warehouse.addItem(_t(t, "md.all"), None)
        for wh in self._ctx.warehouses_repo.list_active():
            self.warehouse.addItem(f"{wh['name']} ({wh['code']})", wh["id"])
        self.footer = QLineEdit()
        add(g3, 0, 0, "co.currency", self.currency, FieldWidth.MD)
        add(g3, 0, 1, "wh.title", self.warehouse, FieldWidth.MD)
        add(g3, 1, 0, "co.footer", self.footer, FieldWidth.XL)

        # ---- logo (§5, §6) ----
        card.body.addWidget(section_title(_t(t, "co.sec_logo")))
        logo_row = QHBoxLayout(); logo_row.setSpacing(Spacing.MD)
        from PyQt6.QtWidgets import QFrame
        self._logo_preview = QLabel()
        self._logo_preview.setFixedSize(96, 96)
        self._logo_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._logo_preview.setFrameShape(QFrame.Shape.StyledPanel)
        logo_row.addWidget(self._logo_preview)
        logo_btns = QVBoxLayout(); logo_btns.setSpacing(Spacing.XS)
        from zenith_business.ui.components import muted, secondary_button
        self._choose_logo = secondary_button(_t(t, "co.choose_logo"))
        self._choose_logo.clicked.connect(self._pick_logo)
        self._remove_logo = ghost_button(_t(t, "co.remove_logo"))
        self._remove_logo.clicked.connect(self._clear_logo)
        logo_btns.addWidget(self._choose_logo)
        logo_btns.addWidget(self._remove_logo)
        logo_btns.addWidget(muted(_t(t, "co.logo_hint")))
        logo_btns.addStretch(1)
        logo_row.addLayout(logo_btns)
        logo_row.addStretch(1)
        card.body.addLayout(logo_row)
        self._logo_path: str | None = None

        save = primary_button(_t(t, "action.save"))
        save.clicked.connect(self._save)
        card.body.addSpacing(Spacing.SM)
        card.body.addWidget(save)
        outer.addWidget(card)
        outer.addStretch(1)
        self.reload()

    def reload(self) -> None:
        row = self._ctx.company_repo.get()
        if not row:
            return
        self.legal.setText(row.get("legal_name") or "")
        self.display.setText(row.get("display_name") or "")
        self.tax.setText(row.get("tax_id") or "")
        self.reg.setText(row.get("registration_number") or "")
        self.address.setText(row.get("address") or "")
        self.city.setText(row.get("city") or "")
        self.phone.setText(row.get("phone") or "")
        self.email.setText(row.get("email") or "")
        self.website.setText(row.get("website") or "")
        self.footer.setText(row.get("invoice_footer") or "")
        _select(self.currency, row.get("default_currency_id"))
        _select(self.warehouse, row.get("default_warehouse_id"))
        self._logo_path = row.get("logo_path")
        self._render_logo()

    def _render_logo(self) -> None:
        from PyQt6.QtGui import QPixmap
        if self._logo_path and Path(self._logo_path).exists():
            pix = QPixmap(self._logo_path)
            if not pix.isNull():
                self._logo_preview.setPixmap(pix.scaled(
                    92, 92, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
                return
        self._logo_preview.setPixmap(QPixmap())
        self._logo_preview.setText(_t(self._t, "co.no_logo"))
        self._logo_preview.setWordWrap(True)

    def _pick_logo(self) -> None:
        from PyQt6.QtWidgets import QFileDialog
        path, _f = QFileDialog.getOpenFileName(
            self, _t(self._t, "co.choose_logo"), "", "Images (*.png *.jpg *.jpeg)")
        if not path:
            return
        try:
            self._logo_path = self._ctx.company.import_logo(path)
        except ZenithError as exc:
            self._error.setText(exc.user_message); self._error.setVisible(True); return
        self._render_logo()

    def _clear_logo(self) -> None:
        self._logo_path = None
        self._render_logo()

    def _save(self) -> None:
        self._error.setVisible(False)
        try:
            self._ctx.company.save(
                legal_name=self.legal.text(), display_name=self.display.text(),
                tax_id=self.tax.text(), registration_number=self.reg.text(),
                address=self.address.text(), city=self.city.text(), phone=self.phone.text(),
                email=self.email.text(), website=self.website.text(),
                default_currency_id=self.currency.currentData(),
                default_warehouse_id=self.warehouse.currentData(),
                logo_path=self._logo_path,
                invoice_footer=self.footer.text())
        except ZenithError as exc:
            self._error.setText(exc.user_message); self._error.setVisible(True); return
        self._error.setText(_t(self._t, "md.saved"))
        self._error.setProperty("role", "secondary")
        self._error.setVisible(True)

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._title.setText(_t(translator, "co.title"))
        self._subtitle.setText(_t(translator, "co.subtitle"))


def _select(combo: QComboBox, value) -> None:
    for i in range(combo.count()):
        if combo.itemData(i) == value:
            combo.setCurrentIndex(i)
            return
