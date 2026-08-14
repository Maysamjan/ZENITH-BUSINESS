"""Stage 03 UI construction — EN + Dari, all master-data screens (§29, §36)."""

from __future__ import annotations

import pytest

from zenith_business.core.config import AppConfig, LANG_DARI, LANG_ENGLISH
from zenith_business.core.i18n import Direction


@pytest.fixture
def wired(qapp, admin_context):
    """A MainWindow wired to a seeded admin context."""
    from zenith_business.ui.main_window import MainWindow

    ctx = admin_context
    bag = ctx.units_repo.id_by_code("BAG")
    ctx.items.create(item_code="RICE", name="Rice", base_unit_id=bag, barcode="600",
                     alternate_name="Basmati", default_sale_price="100")
    ctx.parties.create(party_code="P1", name="Kabul Store", is_customer=True,
                       is_supplier=True, phone="0700")
    ctx.warehouses.create(code="MAIN", name="Main", is_default=True)
    return ctx, MainWindow


_PAGES = ["items", "persons", "warehouses", "categories", "units",
          "company", "financial_years", "users", "roles"]


@pytest.mark.parametrize("lang", [LANG_ENGLISH, LANG_DARI])
def test_all_stage03_pages_construct(wired, lang) -> None:
    ctx, MainWindow = wired
    cfg = AppConfig(); cfg.ui.language = lang
    win = MainWindow(cfg, database=ctx.db, current_user=ctx.session.user,
                     on_logout=lambda: None, context=ctx)
    try:
        for name in _PAGES:
            win._show_stage03(name)  # opens + reloads without raising
            assert win._stage03_pages[name] is not None
    finally:
        win.close()


def test_stage03_category_opens_first_screen(wired) -> None:
    ctx, MainWindow = wired
    cfg = AppConfig(); cfg.ui.language = LANG_ENGLISH
    win = MainWindow(cfg, database=ctx.db, current_user=ctx.session.user,
                     on_logout=lambda: None, context=ctx)
    try:
        win.select_category("menu.base_data")
        assert win.content.currentWidget() is win._stage03_pages["items"]
    finally:
        win.close()


def test_stage03_rtl_direction_in_dari(wired) -> None:
    ctx, MainWindow = wired
    cfg = AppConfig(); cfg.ui.language = LANG_DARI
    win = MainWindow(cfg, database=ctx.db, current_user=ctx.session.user,
                     on_logout=lambda: None, context=ctx)
    try:
        assert win.current_direction() == Direction.RTL
        assert win.layoutDirection().name == "RightToLeft"
    finally:
        win.close()


def test_items_page_lists_seeded_rows(wired) -> None:
    ctx, MainWindow = wired
    cfg = AppConfig(); cfg.ui.language = LANG_ENGLISH
    win = MainWindow(cfg, database=ctx.db, current_user=ctx.session.user,
                     on_logout=lambda: None, context=ctx)
    try:
        page = win._stage03_pages["items"]
        page.reload()
        assert page.page._table.rowCount() == 1  # the seeded Rice item
    finally:
        win.close()
