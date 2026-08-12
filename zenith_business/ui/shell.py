"""Application shell chrome: header, primary navigation, contextual bar.

Prompt 01B §3-§6. Preserves the Chortkeh-style concept — **top** navigation,
center working area, bottom status — with an original, professional Zenith
visual identity. No business functionality is implemented; the pieces here are
structural so real module commands can be added later without redesigning the
main window.
"""

from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from zenith_business.core.i18n import Translator
from zenith_business.core.identity import IDENTITY
from zenith_business.ui.components import vertical_line
from zenith_business.ui.design.tokens import ControlSize, Spacing


def _btn_text(text: str) -> str:
    """Escape ``&`` for button labels so it renders literally.

    Qt treats a single ``&`` in a button/menu label as a mnemonic marker. Until
    deliberate Alt-mnemonics are assigned per module, escape it (e.g.
    'Buy & Sell') so labels display correctly.
    """
    return text.replace("&", "&&")


def _repolish(widget: QWidget) -> None:
    """Re-apply the stylesheet after a dynamic property change."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


class HeaderBar(QFrame):
    """Deep-navy brand header with identity (leading) and user/language (trailing)."""

    def __init__(
        self,
        translator: Translator,
        *,
        on_language: Callable[[str], None],
        on_home: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._t = translator
        self._on_language = on_language
        self.setObjectName("HeaderBar")
        self.setFixedHeight(ControlSize.HEADER_HEIGHT)

        row = QHBoxLayout(self)
        row.setContentsMargins(Spacing.LG, Spacing.SM, Spacing.LG, Spacing.SM)
        row.setSpacing(Spacing.MD)

        # Brand mark (square) — clickable to return home.
        self._mark = QLabel(IDENTITY.product[:1])  # "Z"
        self._mark.setObjectName("BrandMark")
        self._mark.setFixedSize(34, 34)
        self._mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mark.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mark.mousePressEvent = lambda _e: on_home()  # type: ignore[assignment]
        row.addWidget(self._mark)

        brand_col = QVBoxLayout()
        brand_col.setSpacing(0)
        self._wordmark = QLabel(IDENTITY.product.upper())
        self._wordmark.setObjectName("BrandWordmark")
        self._sub = QLabel(IDENTITY.company)
        self._sub.setObjectName("BrandSub")
        brand_col.addWidget(self._wordmark)
        brand_col.addWidget(self._sub)
        row.addLayout(brand_col)

        row.addStretch(1)

        # Trailing: user + divider + language segmented control.
        self._user = QLabel()
        self._user.setProperty("role", "header-muted")
        row.addWidget(self._user)
        row.addWidget(vertical_line())

        self._seg_en = QPushButton("EN")
        self._seg_dari = QPushButton("دری")
        for btn, code in ((self._seg_en, "en"), (self._seg_dari, "fa_AF")):
            btn.setProperty("segment", "true")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda _c=False, x=code: self._on_language(x))
        row.addWidget(self._seg_en)
        row.addWidget(self._seg_dari)

        self.retranslate(translator)

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._user.setText(
            f"{translator.gettext('header.user_guest')}  ·  "
            f"{translator.gettext('header.channel_dev')}"
        )
        selected = translator.language
        self._seg_en.setProperty("selected", "true" if selected == "en" else "false")
        self._seg_dari.setProperty(
            "selected", "true" if selected == "fa_AF" else "false"
        )
        _repolish(self._seg_en)
        _repolish(self._seg_dari)


class PrimaryNav(QFrame):
    """White primary navigation strip: Home + top-level category buttons."""

    def __init__(
        self,
        translator: Translator,
        categories: list[str],
        *,
        on_home: Callable[[], None],
        on_select: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._t = translator
        self._categories = categories
        self._on_select = on_select
        self.setObjectName("PrimaryNav")
        self.setFixedHeight(ControlSize.NAV_HEIGHT)

        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(Spacing.SM, 0, Spacing.SM, 0)
        self._row.setSpacing(Spacing.XS)

        self._home_btn = QPushButton()
        self._home_btn.setProperty("nav", "true")
        self._home_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._home_btn.clicked.connect(lambda: on_home())
        self._row.addWidget(self._home_btn)

        self._buttons: dict[str, QPushButton] = {}
        for key in categories:
            btn = QPushButton()
            btn.setProperty("nav", "true")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _c=False, k=key: self._on_select(k))
            self._buttons[key] = btn
            self._row.addWidget(btn)

        self._row.addStretch(1)
        self.retranslate(translator)

    def set_selected(self, key: str | None) -> None:
        """Highlight the selected category (or none for Home)."""
        self._home_btn.setProperty("selected", "true" if key is None else "false")
        _repolish(self._home_btn)
        for k, btn in self._buttons.items():
            btn.setProperty("selected", "true" if k == key else "false")
            _repolish(btn)

    def button(self, key: str) -> QPushButton:
        return self._buttons[key]

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
        self._home_btn.setText(_btn_text(translator.gettext("action.home")))
        for key, btn in self._buttons.items():
            btn.setText(_btn_text(translator.gettext(key)))


class ContextBar(QFrame):
    """Contextual command bar below the primary navigation (Prompt 01B §6)."""

    def __init__(self, translator: Translator, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._t = translator
        self.setObjectName("ContextBar")
        self.setFixedHeight(ControlSize.CONTEXT_HEIGHT)

        self._row = QHBoxLayout(self)
        self._row.setContentsMargins(Spacing.LG, Spacing.XS, Spacing.LG, Spacing.XS)
        self._row.setSpacing(Spacing.SM)

        self._title = QLabel()
        self._title.setObjectName("ContextTitle")
        self._row.addWidget(self._title)
        self._row.addWidget(vertical_line())

        self._commands_host = QHBoxLayout()
        self._commands_host.setSpacing(Spacing.SM)
        self._row.addLayout(self._commands_host)
        self._row.addStretch(1)

        self._hint = QLabel()
        self._hint.setProperty("role", "muted")
        self._row.addWidget(self._hint)

        self.show_hint()

    def _clear(self) -> None:
        while self._commands_host.count():
            item = self._commands_host.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def show_hint(self) -> None:
        self._clear()
        self._title.setText(self._t.gettext("context.commands"))
        self._hint.setText(self._t.gettext("context.select_hint"))
        self._hint.setVisible(True)

    def set_commands(
        self, commands: list[tuple[str, bool, Callable[[], None] | None]]
    ) -> None:
        """Populate command buttons.

        Each item is (label, enabled, callback). Disabled buttons represent
        not-yet-built module actions and carry the standard placeholder tooltip.
        """
        self._clear()
        self._title.setText(self._t.gettext("context.commands"))
        self._hint.setVisible(False)
        note = self._t.gettext("menu.placeholder_note")
        for label, enabled, callback in commands:
            btn = QPushButton(_btn_text(label))
            btn.setProperty("toolbar", "true")
            btn.setEnabled(enabled)
            if enabled and callback is not None:
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(lambda _c=False, cb=callback: cb())
            else:
                btn.setToolTip(note)
            self._commands_host.addWidget(btn)

    def command_buttons(self) -> list[QPushButton]:
        return [
            self._commands_host.itemAt(i).widget()  # type: ignore[return-value]
            for i in range(self._commands_host.count())
            if self._commands_host.itemAt(i).widget() is not None
        ]

    def retranslate(self, translator: Translator) -> None:
        self._t = translator
