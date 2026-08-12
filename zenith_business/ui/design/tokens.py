"""Design tokens — the single source of truth for the visual system.

These constants are the ONLY approved source for color, spacing, sizing,
typography, radii, and semantic field widths (Prompt 01/01B §10-§14). Screens
must never hard-code raw pixel/hex values; they reference these tokens so the
whole application stays visually consistent and themable, and adapts predictably
under Windows DPI scaling.

Visual language (Prompt 01B): a deep-navy brand **header** for a serious
financial-application feel, a clean white **primary navigation** strip with clear
selected states, a light **contextual command** bar, and a calm light **content**
surface. Colors are semantic so a future theme can re-point them centrally.
"""

from __future__ import annotations

from enum import IntEnum


class Spacing(IntEnum):
    """Spacing / margin scale (logical px). Use these, never raw numbers."""

    NONE = 0
    XXS = 2
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32
    XXXL = 48

    # Semantic layout spacing — tuned for professional information density
    # (Prompt 01C §5): tight, rhythmic, never cramped.
    PAGE_MARGIN = 14
    SECTION_GAP = 12
    CARD_PAD_H = 14
    CARD_PAD_V = 12
    FIELD_VGAP = 7
    FIELD_HGAP = 10


class Radius(IntEnum):
    """Border-radius scale."""

    NONE = 0
    SM = 5
    MD = 8
    LG = 12
    XL = 16
    PILL = 999


class ControlSize(IntEnum):
    """Heights / hit-targets for chrome and controls (logical px)."""

    # Shell chrome
    HEADER_HEIGHT = 54
    NAV_HEIGHT = 42
    CONTEXT_HEIGHT = 40
    STATUSBAR_HEIGHT = 26

    # Controls (denser for fast daily data entry — Prompt 01C §5)
    INPUT_HEIGHT = 30
    INPUT_COMPACT_HEIGHT = 26
    BUTTON_HEIGHT = 32
    TOOLBAR_BUTTON_HEIGHT = 28
    NAV_BUTTON_HEIGHT = 32

    # Tables
    TABLE_ROW_HEIGHT = 28
    TABLE_HEADER_HEIGHT = 30

    # Stat / KPI tiles
    STAT_TILE_HEIGHT = 46

    # Iconography
    ICON_SM = 16
    ICON_MD = 18
    ICON_LG = 22

    # Dialogs
    DIALOG_MIN_WIDTH = 420
    DIALOG_MIN_HEIGHT = 180


class FieldWidth(IntEnum):
    """Semantic minimum field widths (logical px) — Prompt 01B §13.

    Rule: FIELD WIDTH MUST MATCH INFORMATION PURPOSE. Forms pick the category
    that matches a field's meaning so content is never clipped and related fields
    align consistently.

    ==========  =====  ============================================
    Category    px     Typical use
    ==========  =====  ============================================
    XS          70     small numeric / codes
    SM          120    dates / short numbers
    MD          200    standard inputs
    LG          300    person / product names
    XL          460    descriptions / addresses / long values
    ==========  =====  ============================================
    """

    XS = 70
    SM = 120
    MD = 200
    LG = 300
    XL = 460


class Typography:
    """Font families and a clear type hierarchy (points) — Prompt 01B §11.

    Persian/Dari + English friendly using a system/fallback stack; no unlicensed
    fonts are bundled (§21).
    """

    # Single source of truth for the app + print font stack. Bundled Vazirmatn
    # (Persian/Dari + Latin, one consistent baseline for mixed content) leads,
    # with system faces as fallbacks. See :mod:`zenith_business.core.fonts`.
    FAMILY = '"Vazirmatn", "Segoe UI", "Tahoma", "Noto Naskh Arabic", sans-serif'

    # Hierarchy (Prompt 01B §11)
    SIZE_BRAND_HOME = 30      # home-screen product wordmark
    SIZE_BRAND_HEADER = 15    # header wordmark
    SIZE_PAGE_TITLE = 18      # page/form title
    SIZE_SECTION_TITLE = 12   # section heading within a form
    SIZE_BODY = 10            # normal text / inputs
    SIZE_LABEL = 10           # field labels
    SIZE_SECONDARY = 9        # secondary/muted text
    SIZE_TABLE_HEADER = 9     # table headers
    SIZE_STATUS = 9           # status bar
    SIZE_CAPTION = 9          # captions / hints
    SIZE_NAV = 10             # primary navigation
    SIZE_TAGLINE = 12         # home tagline
    SIZE_STAT_VALUE = 13      # stat/KPI tile value
    SIZE_STAT_LABEL = 9       # stat/KPI tile label
    SIZE_TOTAL = 15           # emphasized grand total

    WEIGHT_NORMAL = 400
    WEIGHT_MEDIUM = 500
    WEIGHT_SEMIBOLD = 600
    WEIGHT_BOLD = 700


class Color:
    """Semantic color tokens (Prompt 01B §10).

    A single restrained, professional business palette. Screens reference these
    names, never raw hex, so a future theme can re-point them centrally.
    """

    # ---- surfaces / neutrals ----
    BACKGROUND = "#F4F6F9"       # app content background
    SURFACE = "#FFFFFF"          # cards, inputs, tables, nav strip
    SURFACE_ALT = "#EEF2F7"      # alternating rows, subtle panels
    SURFACE_SUNKEN = "#E7ECF3"   # sunken wells, contextual bar
    BORDER = "#D7DEE7"
    BORDER_STRONG = "#B9C3D0"

    # ---- text ----
    TEXT_PRIMARY = "#16202C"
    TEXT_SECONDARY = "#5A6675"
    TEXT_MUTED = "#8A96A5"
    TEXT_ON_PRIMARY = "#FFFFFF"
    TEXT_DISABLED = "#9AA4B1"

    # ---- brand / primary ----
    PRIMARY = "#1F6FEB"
    PRIMARY_HOVER = "#1A5FCC"
    PRIMARY_PRESSED = "#164FA8"
    PRIMARY_SOFT = "#E7F0FE"     # tinted selected/hover background

    # ---- selection ----
    SELECTED = "#1F6FEB"
    SELECTED_BG = "#E7F0FE"

    # ---- status (with soft backgrounds for chips/states) ----
    SUCCESS = "#1E874B"
    SUCCESS_SOFT = "#E4F3EA"
    WARNING = "#B7791F"
    WARNING_SOFT = "#FBF1DD"
    DANGER = "#C0392B"
    DANGER_SOFT = "#FBE7E4"
    INFO = "#1F6FEB"
    INFO_SOFT = "#E7F0FE"

    DISABLED = "#9AA4B1"

    # ---- shell chrome ----
    HEADER_BG = "#14263D"        # deep navy brand header
    HEADER_BG_ALT = "#1B3554"
    HEADER_TEXT = "#FFFFFF"
    HEADER_TEXT_MUTED = "#A9B6C7"
    HEADER_BORDER = "#0E1B2C"

    NAV_BG = "#FFFFFF"
    NAV_BORDER = "#D7DEE7"

    CONTEXT_BG = "#EEF2F7"
    CONTEXT_BORDER = "#D7DEE7"

    STATUSBAR_BG = "#14263D"
    STATUSBAR_TEXT = "#C4D0DE"
    STATUSBAR_BORDER = "#0E1B2C"

    # ---- secondary / accent (breaks the blue-only monotony; Prompt 01E §14) ----
    ACCENT = "#0E9E8E"           # teal
    ACCENT_HOVER = "#0C8577"
    ACCENT_SOFT = "#E1F4F1"
    ACCENT_TEXT = "#0A6E63"

    # ---- workspace depth (subtle tinted gradient, not flat gray) ----
    WORKSPACE_TOP = "#EFF3FA"
    WORKSPACE_BOTTOM = "#E5ECF6"

    # ---- semantic financial / status roles ----
    POSITIVE = "#1E874B"         # positive financial value
    POSITIVE_SOFT = "#E4F3EA"
    NEGATIVE = "#C0392B"         # debt / negative value
    NEGATIVE_SOFT = "#FBE7E4"

    CASH = "#1E874B"             # cash transaction  -> success
    CASH_SOFT = "#E4F3EA"
    CREDIT = "#B7791F"           # credit transaction -> warning
    CREDIT_SOFT = "#FBF1DD"
    PARTIAL = "#C46A10"          # partial payment    -> amber
    PARTIAL_SOFT = "#FBEBD8"

    IN_STOCK = "#1E874B"
    LOW_STOCK = "#B7791F"
    OUT_OF_STOCK = "#C0392B"

    # ---- interaction surfaces ----
    SELECTED_ROW_BG = "#E7F0FE"          # committed selected row (brand tint)
    ACTIVE_ROW_BG = "#FFF8EC"            # active editing row (warm tint)
    ACTIVE_ROW_ACCENT = "#E0A93B"        # active editing row left accent
    SEARCH_SELECTION_BG = "#D8E8FE"      # highlighted autocomplete result
    INPUT_FOCUS = "#1F6FEB"
    READONLY_BG = "#F1F4F8"              # read-only / disabled surface

    # ---- print (customer-facing invoice; ink-friendly) ----
    PRINT_BG = "#FFFFFF"
    PRINT_INK = "#1B2430"
    PRINT_MUTED = "#5A6675"
    PRINT_ACCENT = "#14263D"             # brand navy for header/title accents
    PRINT_ACCENT_SOFT = "#EDF1F6"
    PRINT_RULE = "#C9D2DD"
    PRINT_TOTAL = "#14263D"
