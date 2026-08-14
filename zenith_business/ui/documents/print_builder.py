"""Build the LOCKED print :class:`InvoiceData` from persisted Stage 04 documents.

The printed document uses the SAME persisted transaction shown on screen — there
is no separate mock print data. Decimal strings are converted to float only here,
at the display boundary (the print engine formats floats); the stored financial
truth remains exact Decimal text. Customer-only view: cost/profit/internal stock
are never printed.

One converter per document kind (sale, purchase, sales return, purchase return)
returns an :class:`InvoiceData` plus the ``title_key`` the print engine should
render, so the SAME reflowing A4/A5 engine composes every document type.
"""

from __future__ import annotations

from zenith_business.services.context import ApplicationContext
from zenith_business.ui.mock.demo_invoice import CompanyInfo, InvoiceData, InvoiceLine

# i18n title keys understood by the (additive) print engine.
TITLE_SALE = "print.title"
TITLE_PURCHASE = "s4.print.purchase_title"
TITLE_SALES_RETURN = "s4.print.sales_return_title"
TITLE_PURCHASE_RETURN = "s4.print.purchase_return_title"


def _f(text) -> float:
    try:
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def _company_info(ctx: ApplicationContext) -> CompanyInfo:
    row = ctx.company_repo.get() or {}
    return CompanyInfo(
        name=(row.get("display_name") or row.get("legal_name") or "Zenith Business"),
        address=" ".join(x for x in (row.get("address"), row.get("city")) if x),
        phone=row.get("phone") or "",
        email=row.get("email") or "",
        tax_id=row.get("tax_id") or "",
    )


def _lines_from(ctx: ApplicationContext, rows: list[dict]) -> list[InvoiceLine]:
    unit_by_id: dict = {u["id"]: u for u in ctx.units_repo.list_all()}
    item_by_id: dict = {}
    lines: list[InvoiceLine] = []
    for ln in rows:
        if ln["item_id"] not in item_by_id:
            item_by_id[ln["item_id"]] = ctx.items_repo.get(ln["item_id"]) or {}
        item = item_by_id[ln["item_id"]]
        unit = unit_by_id.get(ln["unit_id"], {})
        lines.append(InvoiceLine(
            code=item.get("item_code", ""), name=item.get("name", ""),
            unit=unit.get("symbol") or unit.get("name_en") or "",
            qty=_f(ln["quantity"]), price=_f(ln["unit_price"]),
            discount=_f(ln.get("discount", 0))))
    return lines


def _party(ctx: ApplicationContext, party_id, default_name: str) -> dict:
    party = ctx.parties_repo.get(party_id) if party_id else None
    return party or {"name": default_name}


def build_sale_invoice(ctx: ApplicationContext, sale_id: int) -> tuple[InvoiceData, str]:
    """Real Sales-Invoice print data from a persisted sale."""
    sale = ctx.sales_repo.get(sale_id)
    if sale is None:
        raise ValueError(f"No sale {sale_id}")
    party = _party(ctx, sale.get("party_id"), "Walk-in Customer")
    data = InvoiceData(
        company=_company_info(ctx),
        number=sale["document_no"], date=sale["sale_date"],
        currency=(ctx.currencies_repo.get(sale["currency_id"]) or {}).get("code", ""),
        salesperson=(ctx.users_repo.get_by_id(sale["created_by"]) or {}).get("full_name", "")
        if sale.get("created_by") else "",
        customer_code=party.get("party_code") or "",
        customer_name=party.get("name") or "Walk-in Customer",
        customer_phone=party.get("phone") or "",
        customer_address=party.get("address") or "",
        lines=_lines_from(ctx, ctx.sales_repo.lines_for(sale_id)),
        paid=_f(sale["amount_paid"]))
    return data, TITLE_SALE


def build_purchase_invoice(ctx: ApplicationContext, purchase_id: int) -> tuple[InvoiceData, str]:
    """Real Purchase-Invoice print data from a persisted purchase (supplier as party)."""
    purchase = ctx.purchases_repo.get(purchase_id)
    if purchase is None:
        raise ValueError(f"No purchase {purchase_id}")
    party = _party(ctx, purchase.get("party_id"), "Cash Supplier")
    data = InvoiceData(
        company=_company_info(ctx),
        number=purchase["document_no"], date=purchase["purchase_date"],
        currency=(ctx.currencies_repo.get(purchase["currency_id"]) or {}).get("code", ""),
        salesperson=(ctx.users_repo.get_by_id(purchase["created_by"]) or {}).get("full_name", "")
        if purchase.get("created_by") else "",
        customer_code=party.get("party_code") or "",
        customer_name=party.get("name") or "Cash Supplier",
        customer_phone=party.get("phone") or "",
        customer_address=party.get("address") or "",
        lines=_lines_from(ctx, ctx.purchases_repo.lines_for(purchase_id)),
        paid=_f(purchase["amount_paid"]))
    return data, TITLE_PURCHASE


def build_sales_return(ctx: ApplicationContext, return_id: int) -> tuple[InvoiceData, str]:
    """Real Sales-Return credit-note print data from a persisted sales return."""
    ret = ctx.sales_returns_repo.get(return_id)
    if ret is None:
        raise ValueError(f"No sales return {return_id}")
    party = _party(ctx, ret.get("party_id"), "Walk-in Customer")
    data = InvoiceData(
        company=_company_info(ctx),
        number=ret["document_no"], date=ret["return_date"],
        currency=(ctx.currencies_repo.get(ret["currency_id"]) or {}).get("code", ""),
        salesperson=(ctx.users_repo.get_by_id(ret["created_by"]) or {}).get("full_name", "")
        if ret.get("created_by") else "",
        customer_code=party.get("party_code") or "",
        customer_name=party.get("name") or "Walk-in Customer",
        customer_phone=party.get("phone") or "",
        customer_address=party.get("address") or "",
        lines=_lines_from(ctx, ctx.sales_returns_repo.lines_for(return_id)),
        paid=_f(ret["grand_total"]))  # a credit note is settled in full
    return data, TITLE_SALES_RETURN


def build_purchase_return(ctx: ApplicationContext, return_id: int) -> tuple[InvoiceData, str]:
    """Real Purchase-Return debit-note print data from a persisted purchase return."""
    ret = ctx.purchase_returns_repo.get(return_id)
    if ret is None:
        raise ValueError(f"No purchase return {return_id}")
    party = _party(ctx, ret.get("party_id"), "Cash Supplier")
    data = InvoiceData(
        company=_company_info(ctx),
        number=ret["document_no"], date=ret["return_date"],
        currency=(ctx.currencies_repo.get(ret["currency_id"]) or {}).get("code", ""),
        salesperson=(ctx.users_repo.get_by_id(ret["created_by"]) or {}).get("full_name", "")
        if ret.get("created_by") else "",
        customer_code=party.get("party_code") or "",
        customer_name=party.get("name") or "Cash Supplier",
        customer_phone=party.get("phone") or "",
        customer_address=party.get("address") or "",
        lines=_lines_from(ctx, ctx.purchase_returns_repo.lines_for(return_id)),
        paid=_f(ret["grand_total"]))
    return data, TITLE_PURCHASE_RETURN
