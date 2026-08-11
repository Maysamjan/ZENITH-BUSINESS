"""Design-system foundation: tokens + reusable components (Prompt 01B §26)."""

from __future__ import annotations

import pytest

from zenith_business.ui.design.tokens import (
    Color,
    ControlSize,
    FieldWidth,
    Spacing,
    Typography,
)


def test_field_width_categories_are_ordered() -> None:
    # Semantic widths must increase XS < SM < MD < LG < XL (§13).
    widths = [
        FieldWidth.XS, FieldWidth.SM, FieldWidth.MD, FieldWidth.LG, FieldWidth.XL
    ]
    assert widths == sorted(widths)
    assert len(set(widths)) == 5


def test_semantic_color_tokens_present() -> None:
    # Prompt 01B §10 requires these semantic tokens to exist and be hex colors.
    for name in (
        "BACKGROUND", "SURFACE", "SURFACE_ALT", "BORDER", "TEXT_PRIMARY",
        "TEXT_SECONDARY", "PRIMARY", "PRIMARY_HOVER", "SELECTED", "SUCCESS",
        "WARNING", "DANGER", "DISABLED",
    ):
        value = getattr(Color, name)
        assert isinstance(value, str) and value.startswith("#")


def test_typography_hierarchy_is_distinct() -> None:
    # Branding > page title > section > body, and body is readable (not tiny).
    assert Typography.SIZE_BRAND_HOME > Typography.SIZE_PAGE_TITLE
    assert Typography.SIZE_PAGE_TITLE > Typography.SIZE_SECTION_TITLE
    assert Typography.SIZE_SECTION_TITLE >= Typography.SIZE_BODY
    assert Typography.SIZE_BODY >= 9


def test_control_dimensions_present() -> None:
    assert ControlSize.INPUT_HEIGHT > 0
    assert ControlSize.HEADER_HEIGHT > ControlSize.STATUSBAR_HEIGHT
    # Denser professional layout (§5): page margin is compact but not zero.
    assert Spacing.MD <= Spacing.PAGE_MARGIN <= Spacing.XL


# ---- widgets (need a QApplication) --------------------------------------


@pytest.fixture(autouse=True)
def _needs_qt(qapp):
    return qapp


def test_components_construct() -> None:
    from zenith_business.ui.components import (
        Card,
        EmptyState,
        PageHeader,
        chip,
        primary_button,
    )

    assert primary_button("Save").property("variant") == "primary"
    assert chip("OK", "success").property("chip") == "success"
    assert Card().property("role") == "card"
    PageHeader("Title", "Subtitle")
    es = EmptyState("t", "s")
    es.set_text("t2", "s2")


def test_form_and_table_pages_construct() -> None:
    from zenith_business.core.i18n import Translator
    from zenith_business.ui.pages.form_demo import FormDemoPage
    from zenith_business.ui.pages.table_demo import TableDemoPage

    t = Translator("en")
    FormDemoPage(t)
    table = TableDemoPage(t)
    assert table.table.rowCount() > 0
    assert table.table.columnCount() == 7


def test_sales_invoice_prototype_constructs_both_directions() -> None:
    from zenith_business.core.i18n import Translator
    from zenith_business.ui.pages.sales_invoice_demo import SalesInvoiceDemoPage

    for lang in ("en", "fa_AF"):
        page = SalesInvoiceDemoPage(Translator(lang))
        # Dominant line-item grid with the full column set + a trailing entry row.
        assert page._table.columnCount() == 9
        assert page._table.rowCount() >= 6
        # Retranslate must not raise.
        page.retranslate(Translator("fa_AF" if lang == "en" else "en"))


def test_stat_tile_and_labeled_field() -> None:
    from PyQt6.QtWidgets import QLineEdit

    from zenith_business.ui.components import LabeledField, StatTile
    from zenith_business.ui.design.tokens import FieldWidth

    tile = StatTile("Stock", "10")
    tile.set_value("20")
    lf = LabeledField("Name", QLineEdit(), width=FieldWidth.LG)
    assert lf.control.minimumWidth() == int(FieldWidth.LG)
