"""Design tokens — the numeric/vocabulary vocabulary of the UI.

These constants are the ONLY approved source for sizing, spacing, typography,
colors, and standard field widths (Prompt 01 §15-§18, §22). Screens must never
hard-code raw pixel values; they reference these tokens so the whole application
stays visually consistent and adapts predictably under Windows DPI scaling.

Sizing philosophy
-----------------
Values are chosen for readable, business-oriented density and comfortable touch
targets at 100% scaling; because Qt scales logical pixels, they also hold up at
125%/150%. Field widths are expressed as *semantic* sizes (name, amount, date,
...) so a label like "موجودی اول دوره" always gets a field wide enough to show
realistic values comfortably (§16) — no arbitrary fixed widths per screen.
"""

from __future__ import annotations

from enum import IntEnum


class Spacing(IntEnum):
    """Standard spacing/margins (logical px). Use these, not raw numbers."""

    NONE = 0
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32


class Radius(IntEnum):
    """Border-radius scale for panels, cards, buttons, inputs."""

    NONE = 0
    SM = 4
    MD = 6
    LG = 10
    PILL = 999


class ControlSize(IntEnum):
    """Heights and hit-targets for interactive controls (logical px)."""

    INPUT_HEIGHT = 32
    BUTTON_HEIGHT = 34
    TABLE_ROW_HEIGHT = 30
    TABLE_HEADER_HEIGHT = 34
    MENUBAR_HEIGHT = 38
    STATUSBAR_HEIGHT = 26
    ICON = 18


class FieldWidth(IntEnum):
    """Semantic minimum field widths (logical px) — Prompt 01 §16.

    Business forms pick the width that matches the *meaning* of a field so
    content is never clipped and related fields align consistently.
    """

    TINY = 64       # short codes, small integers
    QUANTITY = 110  # quantities with decimals
    DATE = 130      # dates (consistent width across the app)
    AMOUNT = 160    # currency amounts incl. realistic large values
    CODE = 160      # document/reference numbers
    NAME = 260      # person/product names
    DESCRIPTION = 420  # descriptions/notes (wide)
    DROPDOWN = 220  # combo boxes; must show selected text clearly


class Typography:
    """Font families and sizes (points). Persian/Dari + English friendly (§21)."""

    # System/fallback stack that renders Persian and Latin cleanly on Windows
    # without redistributing unlicensed fonts. Segoe UI is the Windows default;
    # Tahoma/Nazanin render Persian well; sans-serif is the final fallback.
    FAMILY = '"Segoe UI", "Tahoma", "Noto Naskh Arabic", "B Nazanin", sans-serif'

    SIZE_CAPTION = 9
    SIZE_BODY = 10
    SIZE_CONTROL = 10
    SIZE_SECTION = 12   # section headings within a form
    SIZE_PAGE = 16      # page/form title
    SIZE_BRAND = 30     # home-screen product name
    SIZE_BRAND_TAGLINE = 12

    WEIGHT_NORMAL = 400
    WEIGHT_MEDIUM = 500
    WEIGHT_BOLD = 700


class Color:
    """Application color palette (calm, professional, business-oriented — §34).

    A single light theme is defined for Stage 01. A dark theme, if introduced,
    will extend this same token set so screens never reference raw hex values.
    """

    # Brand
    PRIMARY = "#1F6FEB"       # Zenith blue — primary actions, accents
    PRIMARY_HOVER = "#1A5FCC"
    PRIMARY_PRESSED = "#164FA8"

    # Neutrals / surfaces
    BACKGROUND = "#F5F7FA"    # window background
    SURFACE = "#FFFFFF"       # cards, inputs, tables
    SURFACE_ALT = "#EEF1F6"   # alternating rows, subtle panels
    BORDER = "#D5DBE3"
    BORDER_STRONG = "#B7C0CD"

    # Text
    TEXT = "#1B2430"
    TEXT_MUTED = "#5B6673"
    TEXT_ON_PRIMARY = "#FFFFFF"
    TEXT_DISABLED = "#9AA4B1"

    # Status
    SUCCESS = "#2E7D46"
    WARNING = "#B7791F"
    ERROR = "#C0392B"
    INFO = "#1F6FEB"

    # Shell chrome
    MENUBAR_BG = "#FFFFFF"
    HEADER_BG = "#FFFFFF"
    STATUSBAR_BG = "#EEF1F6"
