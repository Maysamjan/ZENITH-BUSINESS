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
from zenith_business.ui.components import Card, apply_shadow
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
        self.setMinimumSize(560, 640)

        self._build()
        self._apply_direction()
        self._show_initial_page()

    # ---- construction ----------------------------------------------------

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # A scroll area guarantees the branded card never overlaps its own fields
        # on short windows — content scrolls instead of being squeezed.
        scroll = QScrollArea()
        scroll.setObjectName("AuthScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        backdrop = QWidget()
        backdrop.setObjectName("AuthBackdrop")
        scroll.setWidget(backdrop)

        root = QVBoxLayout(backdrop)
        root.setContentsMargins(Spacing.XXL, Spacing.LG, Spacing.XXL, Spacing.LG)
        root.setSpacing(Spacing.LG)

        # top: language switch (leading/trailing follows layout direction)
        top = QHBoxLayout()
        top.setSpacing(Spacing.SM)
        top.addStretch(1)
        self._lang_en = self._lang_button(LANG_ENGLISH, "auth.lang_en")
        self._lang_fa = self._lang_button(LANG_DARI, "auth.lang_fa")
        top.addWidget(self._lang_en)
        top.addWidget(self._lang_fa)
        root.addLayout(top)

        root.addStretch(1)

        # brand block
        brand = QVBoxLayout()
        brand.setSpacing(Spacing.XS)
        brand.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        mark = QLabel("Z")
        mark.setObjectName("AuthBrandMark")
        mark.setFixedSize(64, 64)
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.addWidget(mark, alignment=Qt.AlignmentFlag.AlignHCenter)
        self._brand_title = QLabel(IDENTITY.product.upper())
        self._brand_title.setObjectName("AuthBrandTitle")
        self._brand_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.addWidget(self._brand_title)
        self._brand_tagline = QLabel(self._t.gettext("auth.brand_tagline"))
        self._brand_tagline.setObjectName("AuthBrandTagline")
        self._brand_tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.addWidget(self._brand_tagline)
        root.addLayout(brand)

        # card with stacked pages
        card = Card(role="card")
        card.setObjectName("AuthCard")
        card.setMaximumWidth(460)
        card.body.setContentsMargins(Spacing.XL, Spacing.XL, Spacing.XL, Spacing.XL)
        apply_shadow(card, blur=40, y=10, alpha=70)

        self._stack = QStackedWidget()
        self._stack.setObjectName("AuthStack")
        self._stack.setStyleSheet("QStackedWidget#AuthStack { background: transparent; }")
        self._setup_page = InitialAdminSetupPage(self._t, self._handle_setup)
        self._login_page = LoginPage(self._t, self._handle_login)
        self._stack.addWidget(self._setup_page)
        self._stack.addWidget(self._login_page)
        card.body.addWidget(self._stack)

        card_row = QHBoxLayout()
        card_row.addStretch(1)
        card_row.addWidget(card)
        card_row.addStretch(1)
        root.addLayout(card_row)

        root.addStretch(2)

        self._footer = QLabel(self._t.gettext("login.footer"))
        self._footer.setObjectName("AuthFooter")
        self._footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._footer)

        self._sync_lang_buttons()

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
        self._brand_tagline.setText(self._t.gettext("auth.brand_tagline"))
        self._footer.setText(self._t.gettext("login.footer"))
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
