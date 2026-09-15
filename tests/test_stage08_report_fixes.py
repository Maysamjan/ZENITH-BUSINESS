"""Stage 08 printed-report fixes: identity, item count, Dari font.

Three owner-reported defects on the printed costing reports. Each is pinned by
what it actually produces, not by the shape of the code that produces it.
"""

from __future__ import annotations

import pytest

from zenith_business.core.i18n import LANG_DARI, LANG_ENGLISH, Translator
from zenith_business.services.purchase_documents import PurchaseLine


@pytest.fixture
def shop(admin_context):
    ctx = admin_context
    ctx.financial_years.create(name="FY26", start_date="2026-01-01",
                               end_date="2026-12-31", make_active=True)
    ctx.main = ctx.warehouses.create(code="MAIN", name="Main Store", is_default=True)
    ctx.bag = ctx.units_repo.id_by_code("BAG")
    ctx.rice = ctx.items.create(item_code="RICE", name="Rice", base_unit_id=ctx.bag,
                                purchase_price="100", default_sale_price="150")
    ctx.sugar = ctx.items.create(item_code="SUGAR", name="Sugar", base_unit_id=ctx.bag,
                                 purchase_price="80", default_sale_price="110")
    sup = ctx.parties.create(party_code="S1", name="Karim", is_supplier=True)
    ctx.purchase_documents.post_purchase(
        currency_code="AFN", warehouse_id=ctx.main, party_id=sup, amount_paid="0",
        purchase_date="2026-02-01",
        lines=[PurchaseLine(item_id=ctx.rice, unit_id=ctx.bag, quantity="10",
                            unit_price="100"),
               PurchaseLine(item_id=ctx.sugar, unit_id=ctx.bag, quantity="20",
                            unit_price="80")])
    return ctx


def _valuation_payload(ctx, language=LANG_ENGLISH):
    from zenith_business.ui.documents.costing_report_page import CostingReportPage

    page = CostingReportPage(ctx, Translator(language))
    page._set_kind("valuation")
    return page._last


# ---- 1. the customer's business identity, never the product's ------------

def test_the_report_identity_is_the_name_setup_stored(admin_context):
    """Setup stores the business name as a setting; the Company screen may never
    be opened. Printing the PRODUCT name on the customer's own report is wrong."""
    from zenith_business.ui.documents.print_builder import _company_info

    assert admin_context.company_repo.get() is None      # Company screen untouched
    assert _company_info(admin_context).name == "Test Co."


def test_the_company_screen_still_wins_over_the_setup_name(admin_context):
    from zenith_business.ui.documents.print_builder import _company_info

    admin_context.company.save(legal_name="Kabul Traders Ltd",
                               display_name="Kabul Traders Ltd")
    assert _company_info(admin_context).name == "Kabul Traders Ltd"


def test_the_product_name_is_only_the_last_resort(context):
    """With nothing configured at all there is still something to print."""
    from zenith_business.ui.documents.print_builder import _company_info

    assert _company_info(context).name == "Zenith Business"


def test_the_printed_costing_report_carries_the_full_identity(shop, qapp):
    from zenith_business.ui.documents.print_builder import build_costing_report_print

    shop.company.save(legal_name="Kabul Traders Ltd", display_name="Kabul Traders Ltd",
                      address="Shar-e-Naw", city="Kabul", phone="+93 700 111 222",
                      email="info@kabultraders.af", tax_id="TIN-9876543")
    data = build_costing_report_print(shop, _valuation_payload(shop))
    company = data.company
    assert company.name == "Kabul Traders Ltd"
    assert "Kabul" in company.address
    assert company.phone == "+93 700 111 222"
    assert company.email == "info@kabultraders.af"
    assert company.tax_id == "TIN-9876543"


def test_the_tax_id_reaches_the_printed_sheet(shop, qapp):
    """It travels on the identity object rather than a reduced copy of it."""
    from PyQt6.QtWidgets import QLabel

    from zenith_business.ui.documents.print_builder import build_costing_report_print
    from zenith_business.ui.print.costing_report_document import CostingReportPrintDocument

    shop.company.save(legal_name="Kabul Traders Ltd", tax_id="TIN-9876543")
    data = build_costing_report_print(shop, _valuation_payload(shop))
    doc = CostingReportPrintDocument(data, Translator(LANG_ENGLISH))
    printed = " ".join(lab.text() for lab in doc.findChildren(QLabel))
    assert "TIN-9876543" in printed


# ---- 2. totals are not items --------------------------------------------

def test_totals_travel_beside_the_rows_not_inside_them(shop, qapp):
    from zenith_business.ui.documents.print_builder import build_costing_report_print

    payload = _valuation_payload(shop)
    data = build_costing_report_print(shop, payload)
    assert len(data.rows) == 2, "the printed table must hold ITEMS only"
    assert len(data.totals) == 2, "the totals must still reach the sheet"


def test_the_printed_item_count_counts_items(shop, qapp):
    """Two items must print as '2 item(s)', not 4."""
    from PyQt6.QtWidgets import QLabel

    from zenith_business.ui.documents.print_builder import build_costing_report_print
    from zenith_business.ui.print.costing_report_document import CostingReportPrintDocument

    data = build_costing_report_print(shop, _valuation_payload(shop))
    doc = CostingReportPrintDocument(data, Translator(LANG_ENGLISH))
    texts = [lab.text() for lab in doc.findChildren(QLabel)]
    assert "2 item(s)" in texts
    assert "4 item(s)" not in texts


def test_the_totals_are_still_printed(shop, qapp):
    from PyQt6.QtWidgets import QLabel

    from zenith_business.ui.documents.print_builder import build_costing_report_print
    from zenith_business.ui.print.costing_report_document import CostingReportPrintDocument

    data = build_costing_report_print(shop, _valuation_payload(shop))
    doc = CostingReportPrintDocument(data, Translator(LANG_ENGLISH))
    printed = " ".join(lab.text() for lab in doc.findChildren(QLabel))
    assert "Total inventory value" in printed
    assert "2,600.00" in printed          # 1,000 rice + 1,600 sugar


def test_the_locked_inventory_report_sheet_is_untouched(shop, qapp):
    """Stage 06 keeps its own document and its own behaviour."""
    from zenith_business.ui.print.inventory_report_document import (
        InventoryReportPrintData,
        InventoryReportPrintDocument,
    )

    assert InventoryReportPrintDocument is not None
    assert not hasattr(InventoryReportPrintData, "totals")


# ---- 3. Dari uses the bundled font, with no fallback --------------------

def test_dari_asks_for_the_bundled_font_and_nothing_else(shop, qapp):
    """A system face substituted for Persian makes the sheet look foreign."""
    from zenith_business.ui.documents.print_builder import build_costing_report_print
    from zenith_business.ui.print.costing_report_document import CostingReportPrintDocument

    data = build_costing_report_print(shop, _valuation_payload(shop, LANG_DARI))
    doc = CostingReportPrintDocument(data, Translator(LANG_DARI))
    sheet = doc.styleSheet()
    assert '"Vazirmatn"' in sheet
    for fallback in ("Segoe UI", "Tahoma", "Noto Naskh Arabic", "sans-serif"):
        assert fallback not in sheet, f"Dari fell back to {fallback}"


def test_english_keeps_the_shared_font_stack(shop, qapp):
    from zenith_business.ui.documents.print_builder import build_costing_report_print
    from zenith_business.ui.print.costing_report_document import CostingReportPrintDocument

    data = build_costing_report_print(shop, _valuation_payload(shop))
    doc = CostingReportPrintDocument(data, Translator(LANG_ENGLISH))
    assert "Segoe UI" in doc.styleSheet(), "English rendering must be unchanged"


def test_every_dari_element_is_covered_by_the_font_rule(shop, qapp):
    """Title, headers, table text, totals and footer — not just the table."""
    from zenith_business.ui.documents.print_builder import build_costing_report_print
    from zenith_business.ui.print.costing_report_document import CostingReportPrintDocument

    data = build_costing_report_print(shop, _valuation_payload(shop, LANG_DARI))
    doc = CostingReportPrintDocument(data, Translator(LANG_DARI))
    sheet = doc.styleSheet()
    # QLabel covers the title, company block, totals and footer; the table and
    # its header carry the family explicitly.
    assert sheet.count('font-family: "Vazirmatn"') >= 3
    assert "QHeaderView::section" in sheet


def test_dari_stays_right_to_left(shop, qapp):
    from PyQt6.QtCore import Qt

    from zenith_business.ui.documents.print_builder import build_costing_report_print
    from zenith_business.ui.print.costing_report_document import CostingReportPrintDocument

    data = build_costing_report_print(shop, _valuation_payload(shop, LANG_DARI))
    doc = CostingReportPrintDocument(data, Translator(LANG_DARI))
    assert doc.layoutDirection() == Qt.LayoutDirection.RightToLeft


# ---- the Gross Profit sheet counts nothing -------------------------------

def _payload(ctx, kind, language=LANG_ENGLISH):
    from zenith_business.ui.documents.costing_report_page import CostingReportPage

    page = CostingReportPage(ctx, Translator(language))
    page._set_kind(kind)
    return page._last


def test_gross_profit_prints_no_item_count(shop, qapp):
    """Net sales and COGS are calculation steps, not stock."""
    from PyQt6.QtWidgets import QLabel

    from zenith_business.ui.documents.print_builder import build_costing_report_print
    from zenith_business.ui.print.costing_report_document import CostingReportPrintDocument

    data = build_costing_report_print(shop, _payload(shop, "gross_profit"))
    assert data.show_item_count is False
    doc = CostingReportPrintDocument(data, Translator(LANG_ENGLISH))
    printed = " ".join(lab.text() for lab in doc.findChildren(QLabel))
    assert "item(s)" not in printed
    # The figures live in the table, and must still all be on the sheet.
    from PyQt6.QtWidgets import QTableWidget
    table = doc.findChildren(QTableWidget)[0]
    rows = [table.item(r, 0).text() for r in range(table.rowCount())]
    assert "Gross profit" in rows and "Net sales" in rows


def test_gross_profit_prints_no_item_count_in_dari(shop, qapp):
    from PyQt6.QtWidgets import QLabel

    from zenith_business.ui.documents.print_builder import build_costing_report_print
    from zenith_business.ui.print.costing_report_document import CostingReportPrintDocument

    data = build_costing_report_print(shop, _payload(shop, "gross_profit", LANG_DARI))
    doc = CostingReportPrintDocument(data, Translator(LANG_DARI))
    printed = " ".join(lab.text() for lab in doc.findChildren(QLabel))
    assert "قلم" not in printed


def test_the_valuation_still_counts_its_items(shop, qapp):
    """Removing the count from one report must not remove it from the other."""
    from PyQt6.QtWidgets import QLabel

    from zenith_business.ui.documents.print_builder import build_costing_report_print
    from zenith_business.ui.print.costing_report_document import CostingReportPrintDocument

    data = build_costing_report_print(shop, _payload(shop, "valuation"))
    assert data.show_item_count is True
    doc = CostingReportPrintDocument(data, Translator(LANG_ENGLISH))
    printed = [lab.text() for lab in doc.findChildren(QLabel)]
    assert "2 item(s)" in printed


def test_the_cogs_report_still_counts_its_items(shop, qapp):
    from zenith_business.ui.documents.print_builder import build_costing_report_print

    assert build_costing_report_print(shop, _payload(shop, "cogs")).show_item_count is True


# ---- the bundled Dari font must survive packaging ------------------------

def test_the_bundled_dari_font_is_registered_at_runtime(qapp):
    """The face the sheet asks for has to be one Qt actually has.

    Asking for "Vazirmatn" with no fallback only helps if Vazirmatn is loaded;
    otherwise Qt picks a default and the sheet looks foreign again. This runs on
    whatever platform the suite runs on — including Windows in CI.
    """
    from zenith_business.core.fonts import FONT_FAMILY, apply_base_font, is_bundled_available

    apply_base_font(qapp)
    assert is_bundled_available(), f"{FONT_FAMILY} was not registered with Qt"


def test_dari_text_actually_resolves_to_the_bundled_font(shop, qapp):
    """Not what the stylesheet asks for — what Qt resolves it to."""
    from PyQt6.QtGui import QFontInfo
    from PyQt6.QtWidgets import QLabel, QTableWidget

    from zenith_business.core.fonts import FONT_FAMILY, apply_base_font
    from zenith_business.ui.documents.print_builder import build_costing_report_print
    from zenith_business.ui.print.costing_report_document import CostingReportPrintDocument

    apply_base_font(qapp)
    data = build_costing_report_print(shop, _payload(shop, "valuation", LANG_DARI))
    doc = CostingReportPrintDocument(data, Translator(LANG_DARI))
    doc.ensurePolished()
    resolved = {QFontInfo(w.font()).family()
                for w in doc.findChildren(QLabel) + doc.findChildren(QTableWidget)}
    assert resolved, "the sheet rendered no text at all"
    assert resolved == {FONT_FAMILY}, f"Dari fell back to {resolved - {FONT_FAMILY}}"


def test_the_font_files_are_packaged_with_the_application():
    """A Windows build with no font files would silently fall back."""
    from pathlib import Path

    import zenith_business

    fonts = Path(zenith_business.__file__).parent / "resources" / "fonts"
    faces = sorted(p.name for p in fonts.glob("Vazirmatn-*.ttf"))
    assert faces, "the bundled Vazirmatn faces are missing from the package"
    spec = (Path(zenith_business.__file__).parent.parent
            / "packaging" / "zenith_business.spec").read_text()
    assert "collect_data_files" in spec and "zenith_business" in spec, (
        "the PyInstaller spec no longer collects the resource tree, so a frozen"
        " build would ship without the Dari font")
