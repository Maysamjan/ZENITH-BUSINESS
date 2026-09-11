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
        self._setup_page = InitialAdminSetupPage(self._t, self._handle_setup)
        self._login_page = LoginPage(self._t, self._handle_login)
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
        v = self._t.gettext("login.version")
        lic = self._t.gettext("login.licence")
        dev = self._t.gettext("login.licence_dev")
        return f"{IDENTITY.company} · {v} {IDENTITY.version} · {lic}: {dev}"

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

    def _show_initial_page(self) -> None:
        if self._ctx.is_setup_required:
            self._show_page(self._setup_page)
        else:
            self._show_page(self._login_page)
            self._login_page.focus_first()

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
            if isinstance(exc, (AccountLockedError, AccountInactiveError)):
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
