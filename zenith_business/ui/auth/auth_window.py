"""Authentication window — startup gate (Stage 02 §2, §11).

Hosts the initial-setup and login pages inside one branded, bilingual dialog. It
is shown BEFORE the main window: production must authenticate first and never open
straight into the dashboard. On success it stores the signed-in user on the
application context and accepts.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.config import AppConfig, LANG_DARI, LANG_ENGLISH
from zenith_business.core.i18n import Direction, Translator, resolve_direction
from zenith_business.core.identity import IDENTITY
from zenith_business.core.logging_setup import get_logger
from zenith_business.services.context import ApplicationContext
from zenith_business.services.exceptions import AuthenticationError, ValidationError, ZenithError
from zenith_business.services.session import CurrentUser
from zenith_business.ui.auth.activation_page import ActivationPage
from zenith_business.ui.auth.login_page import LoginPage
from zenith_business.ui.auth.setup_page import InitialAdminSetupPage
from zenith_business.ui.design.tokens import Spacing

_logger = get_logger("ui.auth")


class AuthWindow(QDialog):
    """Modal startup gate. ``exec()`` returns ``Accepted`` once authenticated."""

    def __init__(
        self,
        context: ApplicationContext,
        config: AppConfig,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._ctx = context
        self._config = config
        self._t = Translator(config.ui.language)
        self.authenticated_user: CurrentUser | None = None

        self.setWindowTitle(IDENTITY.title)
        # Two-panel desktop composition; comfortably fits the 1366×768 floor.
        self.setMinimumSize(880, 560)
        self.resize(980, 620)

        self._build()
        self._apply_direction()
        self._show_initial_page()
        self._centre_on_screen()

    def _centre_on_screen(self) -> None:
        from PyQt6.QtWidgets import QApplication
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        # Never exceed the work area (small laptop screens).
        w = min(self.width(), int(avail.width() * 0.96))
        h = min(self.height(), int(avail.height() * 0.94))
        self.resize(w, h)
        frame = self.frameGeometry()
        frame.moveCenter(avail.center())
        self.move(frame.topLeft())

    # ---- construction ----------------------------------------------------

    def _build(self) -> None:
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_brand_panel(), 5)
        outer.addWidget(self._build_form_panel(), 6)
        self._sync_lang_buttons()

    # -- left: Zenith Soft developer brand panel --------------------------

    def _build_brand_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("AuthBrandPanel")
        col = QVBoxLayout(panel)
        col.setContentsMargins(Spacing.XXL, Spacing.XXL, Spacing.XXL, Spacing.XXL)
        col.setSpacing(Spacing.SM)

        mark = QLabel("Z")
        mark.setObjectName("AuthBrandMark")
        mark.setFixedSize(60, 60)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(mark)
        col.addSpacing(Spacing.MD)

        self._brand_company = QLabel(self._t.gettext("brand.company"))
        self._brand_company.setObjectName("AuthBrandCompany")
        col.addWidget(self._brand_company)
        self._brand_kind = QLabel(self._t.gettext("brand.kind"))
        self._brand_kind.setObjectName("AuthBrandKind")
        col.addWidget(self._brand_kind)

        line = QWidget()
        line.setObjectName("AuthBrandRule")
        line.setFixedHeight(1)
        col.addSpacing(Spacing.LG)
        col.addWidget(line)
        col.addSpacing(Spacing.LG)

        self._brand_lead = QLabel(self._t.gettext("brand.product_lead"))
        self._brand_lead.setObjectName("AuthBrandLead")
        self._brand_lead.setWordWrap(True)
        col.addWidget(self._brand_lead)

        col.addStretch(1)

        # contact block (phone/email kept LTR-readable even in RTL)
        self._contact_rows: list[tuple[QLabel, str]] = []
        col.addWidget(self._contact_row("brand.phone_label", "0785228719", ltr=True))
        col.addWidget(self._contact_row("brand.email_label",
                                        "zenithsoft.info@gmail.com", ltr=True))
        col.addWidget(self._contact_row("brand.address_label",
                                        self._t.gettext("brand.address_value"),
                                        value_key="brand.address_value"))
        return panel

    def _contact_row(self, label_key: str, value: str, *, ltr: bool = False,
                     value_key: str | None = None) -> QWidget:
        row = QWidget()
        row.setObjectName("AuthContactRow")
        rl = QVBoxLayout(row)
        rl.setContentsMargins(0, Spacing.XS, 0, Spacing.XS)
        rl.setSpacing(1)
        lab = QLabel(self._t.gettext(label_key))
        lab.setObjectName("AuthContactLabel")
        val = QLabel(value)
        val.setObjectName("AuthContactValue")
        val.setWordWrap(True)
        if ltr:
            # Phone / email must read left-to-right regardless of UI direction.
            val.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            val.setAlignment(Qt.AlignmentFlag.AlignLeft)
        rl.addWidget(lab)
        rl.addWidget(val)
        self._contact_rows.append((lab, label_key))
        if value_key is not None:
            self._contact_rows.append((val, value_key))
        return row

    # -- right: product login / setup form panel --------------------------

    def _build_form_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("AuthFormPanel")
        col = QVBoxLayout(panel)
        col.setContentsMargins(Spacing.XXL, Spacing.LG, Spacing.XXL, Spacing.LG)
        col.setSpacing(Spacing.SM)

        # top: language switch (trailing per direction)
        top = QHBoxLayout()
        top.addStretch(1)
        self._lang_en = self._lang_button(LANG_ENGLISH, "auth.lang_en")
        self._lang_fa = self._lang_button(LANG_DARI, "auth.lang_fa")
        top.addWidget(self._lang_en)
        top.addWidget(self._lang_fa)
        col.addLayout(top)

        # middle scrolls on very short screens; product identity + stacked form
        mid = QWidget()  # transparent via the AuthScroll descendant rule (theme.py)
        mcol = QVBoxLayout(mid)
        mcol.setContentsMargins(0, 0, 0, 0)
        mcol.setSpacing(Spacing.XS)
        mcol.addStretch(1)

        self._product_wm = QLabel(IDENTITY.product.upper())
        self._product_wm.setObjectName("AuthProduct")
        mcol.addWidget(self._product_wm)
        self._product_tag = QLabel(self._t.gettext("auth.brand_tagline"))
        self._product_tag.setObjectName("AuthTagline")
        mcol.addWidget(self._product_tag)
        mcol.addSpacing(Spacing.LG)

        self._stack = QStackedWidget()
        self._stack.setObjectName("AuthStack")
        self._stack.setStyleSheet("QStackedWidget#AuthStack { background: transparent; }")
        # Activation is a PAGE IN THIS STACK, not a dialog in front of it. There
        # is no path from it to the login form except a licence that evaluates
        # to FULL or DEMO, which is what makes the gate a gate.
        self._activation_page = ActivationPage(
            self._t, on_activate=self._handle_activate,
            on_copy_request=self._handle_copy_request,
            on_make_request=self._handle_make_request,
            on_import=self._handle_import_license, on_recheck=self._handle_recheck)
        self._setup_page = InitialAdminSetupPage(self._t, self._handle_setup)
        self._login_page = LoginPage(self._t, self._handle_login,
                                     on_forgot=self._handle_forgot_password)
        self._stack.addWidget(self._activation_page)
        self._stack.addWidget(self._setup_page)
        self._stack.addWidget(self._login_page)
        mcol.addWidget(self._stack)
        mcol.addStretch(2)

        scroll = QScrollArea()
        scroll.setObjectName("AuthScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(mid)
        col.addWidget(scroll, 1)

        # footer: version + licence status (pinned)
        self._footer = QLabel(self._version_text())
        self._footer.setObjectName("AuthFooter")
        col.addWidget(self._footer)
        return panel

    def _version_text(self) -> str:
        """The footer, reading the REAL licence state — one source of truth.

        This used to print the development-build text unconditionally, so an
        activated installation still told the customer it was unlicensed every
        time they signed in.
        """
        from zenith_business.ui.components import license_summary

        v = self._t.gettext("login.version")
        lic = self._t.gettext("login.licence")
        licensing = getattr(self._ctx, "licensing", None)
        try:
            state = (license_summary(self._t, licensing.evaluate())
                     if licensing is not None
                     else self._t.gettext("login.licence_dev"))
        except Exception:
            state = self._t.gettext("login.licence_dev")
        return f"{IDENTITY.company} · {v} {IDENTITY.version} · {lic}: {state}"

    def _lang_button(self, code: str, key: str) -> QPushButton:
        btn = QPushButton(self._t.gettext(key))
        btn.setProperty("authlang", "true")
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(lambda: self._switch_language(code))
        return btn

    # ---- page flow -------------------------------------------------------

    def _show_page(self, page: QWidget) -> None:
        """Switch pages and let the card shrink/grow to the visible page.

        Hidden pages get an Ignored size policy so the QStackedWidget adopts the
        current page's size hint instead of the tallest page's — no dead space.
        """
        for i in range(self._stack.count()):
            widget = self._stack.widget(i)
            policy = widget.sizePolicy()
            policy.setVerticalPolicy(
                QSizePolicy.Policy.Preferred if widget is page else QSizePolicy.Policy.Ignored)
            widget.setSizePolicy(policy)
        self._stack.setCurrentWidget(page)
        page.adjustSize()

    # ---- the licence gate ------------------------------------------------

    def license_state(self):
        """Re-read the licence. Never cached: one boolean is one thing to defeat."""
        licensing = getattr(self._ctx, "licensing", None)
        if licensing is None:                       # pragma: no cover - legacy contexts
            return None
        return licensing.evaluate()

    def _licence_allows_login(self) -> bool:
        state = self.license_state()
        return True if state is None else bool(state.allows_login)

    def _show_initial_page(self) -> None:
        """Licence FIRST, then setup or login. This order is the requirement."""
        state = self.license_state()
        if state is not None and not state.allows_login:
            self._activation_page.show_state(state)
            self._show_page(self._activation_page)
            _logger.info("Licence gate: %s (%s) — activation required.",
                         state.status, state.reason)
            return
        if self._ctx.is_setup_required:
            self._show_page(self._setup_page)
        else:
            self._show_page(self._login_page)
            self._login_page.focus_first()

    def _handle_copy_request(self) -> None:
        """Put the request code on the clipboard — the normal first step."""
        from PyQt6.QtWidgets import QApplication

        licensing = getattr(self._ctx, "licensing", None)
        if licensing is None:                       # pragma: no cover
            return
        try:
            code = licensing.request_code()
        except Exception as exc:                    # pragma: no cover - defensive
            self._activation_page.say(str(exc), bad=True)
            return
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(code)
        _logger.info("Request code copied for machine %s.",
                     licensing.machine.short)
        self._activation_page.say(self._t.gettext("act.request_copied"))

    def _handle_activate(self, product_key: str) -> None:
        """Paste in, licence out. The path almost every customer will use."""
        licensing = getattr(self._ctx, "licensing", None)
        if licensing is None:                       # pragma: no cover
            return
        try:
            state = licensing.import_product_key(product_key)
        except Exception as exc:                    # LicenseError is not a ZenithError
            self._activation_page.show_state(licensing.evaluate())
            self._activation_page.set_error(self._licence_message(exc))
            return
        _logger.info("Activated by product key at the gate: %s (%s)",
                     state.license_id, state.status)
        self._activation_page.clear_key()
        self._announce_activation(state)

    def _licence_message(self, exc: Exception) -> str:
        """Say a licensing refusal in the language on screen.

        The service raises an English sentence and, where it can, a catalogue
        key. The key wins when the catalogue knows it; otherwise the English is
        still better than nothing, which is what a missing translation would
        otherwise leave the customer with.
        """
        key = getattr(exc, "key", None)
        if key:
            translated = self._t.gettext(key)
            if translated != key:
                return translated
        return getattr(exc, "user_message", str(exc))

    def _announce_activation(self, state) -> None:
        from PyQt6.QtWidgets import QMessageBox

        QMessageBox.information(
            self, self._t.gettext("act.title"),
            self._t.gettext("act.activated").replace("{id}", state.license_id))
        self._footer.setText(self._version_text())
        # Straight on to setup or login — activation is not a destination.
        self._show_initial_page()

    def _handle_recheck(self) -> None:
        state = self.license_state()
        if state is None or state.allows_login:
            self._footer.setText(self._version_text())
            self._show_initial_page()
            return
        self._activation_page.show_state(state)

    def _handle_make_request(self) -> None:
        from pathlib import Path

        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        licensing = getattr(self._ctx, "licensing", None)
        if licensing is None:                       # pragma: no cover
            return
        suggested = f"zenith-activation-{licensing.machine.fingerprint[:12]}.zreq"
        name, _ = QFileDialog.getSaveFileName(
            self, self._t.gettext("act.make_request"),
            str(Path.home() / suggested), self._t.gettext("sec.lic_req_filter"))
        if not name:
            return
        try:
            # The business name comes from the service, which returns the
            # customer's own name or nothing — never a sample or the product.
            path = licensing.create_activation_request(name)
        except OSError as exc:
            self._activation_page.say(str(exc), bad=True)
            return
        self._activation_page.say(
            self._t.gettext("sec.lic_request_saved").replace("{file}", path.name))
        QMessageBox.information(
            self, self._t.gettext("act.make_request"),
            self._t.gettext("sec.lic_request_next").replace("{file}", str(path)))

    def _handle_import_license(self) -> None:
        from pathlib import Path

        from PyQt6.QtWidgets import QFileDialog, QMessageBox

        licensing = getattr(self._ctx, "licensing", None)
        if licensing is None:                       # pragma: no cover
            return
        name, _ = QFileDialog.getOpenFileName(
            self, self._t.gettext("act.import"), str(Path.home()),
            self._t.gettext("sec.lic_filter"))
        if not name:
            return
        try:
            state = licensing.import_license(name)
        except Exception as exc:                    # LicenseError is not a ZenithError
            message = self._licence_message(exc)
            self._activation_page.say(message, bad=True)
            self._activation_page.show_state(licensing.evaluate())
            QMessageBox.critical(self, self._t.gettext("act.import"), message)
            return
        _logger.info("Licence imported at the gate: %s (%s)",
                     state.license_id, state.status)
        self._announce_activation(state)

    def _handle_setup(self, values: dict) -> None:
        if values["password"] != values["confirm_password"]:
            self._setup_page.set_error(self._t.gettext("setup.error_mismatch"))
            return
        try:
            self._ctx.setup.create_administrator(
                username=values["username"], password=values["password"],
                confirm_password=values["confirm_password"], full_name=values["full_name"],
                preferred_language=self._t.language,
                company_name=values["company_name"] or None)
        except ValidationError as exc:
            self._setup_page.set_error(exc.user_message)
            return
        except ZenithError as exc:
            self._setup_page.set_error(exc.user_message)
            return
        # Success → move to login, prefilled, and ask them to sign in.
        self._login_page.username.setText(values["username"])
        self._show_page(self._login_page)
        self._login_page.set_error(self._t.gettext("setup.created"))
        self._login_page.focus_first()

    def _handle_login(self, username: str, password: str) -> None:
        # Checked again here, not only when the page was chosen: a licence can be
        # deleted, expire or be replaced while this screen sits open, and the
        # answer must be the current one, not the one from when it was drawn.
        if not self._licence_allows_login():
            self._show_initial_page()
            return
        if not username or not password:
            self._login_page.set_error(self._t.gettext("login.error_required"))
            return
        self._login_page.set_busy(True)
        try:
            user = self._ctx.auth.login(username, password)
        except AuthenticationError as exc:
            # Generic message unless the account state is specifically locked/inactive.
            from zenith_business.services.exceptions import (
                AccountInactiveError,
                AccountLockedError,
            )
            if isinstance(exc, AccountLockedError):
                self._show_lockout(username, exc.user_message)
            elif isinstance(exc, AccountInactiveError):
                self._login_page.set_error(exc.user_message)
            else:
                self._login_page.set_error(self._t.gettext("login.error_invalid"))
            self._login_page.set_busy(False)
            return
        except ZenithError as exc:
            self._login_page.set_error(exc.user_message)
            self._login_page.set_busy(False)
            return
        self.authenticated_user = user
        self._config.ui.language = self._t.language
        _logger.info("Authentication gate passed for %r.", user.username)
        self.accept()

    def _show_lockout(self, username: str, fallback: str) -> None:
        """Tell the owner how long the lock still has to run, to the second.

        The service knows the exact expiry; ``fallback`` is used only if that
        read is unavailable, so a locked account is never met with silence.
        """
        seconds = 0
        try:
            security = getattr(self._ctx, "security", None)
            if security is not None:
                seconds = int(security.guard_state(username).seconds_remaining or 0)
        except Exception:  # pragma: no cover - a read failure must not block the screen
            _logger.warning("Could not read the lockout countdown.", exc_info=True)
        if seconds > 0:
            self._login_page.show_lockout(seconds)
        else:
            self._login_page.set_error(fallback)

    def _handle_forgot_password(self) -> None:
        """The way back in for an owner with nobody to ask (final §4)."""
        from PyQt6.QtWidgets import QDialog as _QDialog
        from PyQt6.QtWidgets import QMessageBox

        from zenith_business.ui.auth.recovery_dialog import RecoveryDialog

        dialog = RecoveryDialog(self._ctx, self._t,
                                username=self._login_page.username.text().strip(),
                                parent=self)
        if dialog.exec() != _QDialog.DialogCode.Accepted:
            return
        _logger.info("Owner password reset with a recovery code.")
        self._login_page.username.setText(dialog.recovered_username or "")
        self._login_page.set_error(self._t.gettext("rec.done"))
        self._login_page.focus_first()
        QMessageBox.information(self, self._t.gettext("rec.title"),
                                self._t.gettext("rec.done"))

    # ---- language / direction -------------------------------------------

    def _switch_language(self, code: str) -> None:
        if code not in (LANG_DARI, LANG_ENGLISH):
            return
        self._t.set_language(code)
        self._config.ui.language = code
        self._apply_direction()
        self._brand_company.setText(self._t.gettext("brand.company"))
        self._brand_kind.setText(self._t.gettext("brand.kind"))
        self._brand_lead.setText(self._t.gettext("brand.product_lead"))
        self._product_tag.setText(self._t.gettext("auth.brand_tagline"))
        self._footer.setText(self._version_text())
        for widget, key in self._contact_rows:
            widget.setText(self._t.gettext(key))
        self._activation_page.retranslate(self._t)
        self._setup_page.retranslate(self._t)
        self._login_page.retranslate(self._t)
        self._sync_lang_buttons()

    def _sync_lang_buttons(self) -> None:
        for btn, code in ((self._lang_en, LANG_ENGLISH), (self._lang_fa, LANG_DARI)):
            btn.setProperty("selected", "true" if self._t.language == code else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _apply_direction(self) -> None:
        direction = resolve_direction(self._t.language, self._config.ui.direction)
        self.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft if direction == Direction.RTL
            else Qt.LayoutDirection.LeftToRight)

    # ---- test / bootstrap helpers ---------------------------------------

    @property
    def translator(self) -> Translator:
        return self._t

    def current_direction(self) -> Direction:
        return resolve_direction(self._t.language, self._config.ui.direction)
