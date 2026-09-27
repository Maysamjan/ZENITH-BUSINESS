"""Build the printed :class:`VoucherData` from a persisted Stage 05 document.

Screen == print: the same posted receipt / payment / expense drives the voucher.
Decimal → float only here, at the display boundary. Payment-method codes are
localised through the translator so the voucher reads entirely in the active
language.
"""

from __future__ import annotations

from zenith_business.services.context import ApplicationContext
from zenith_business.ui.documents.print_builder import _company_info, _f
from zenith_business.ui.print.voucher_document import VoucherData

_METHOD_KEYS = {"CASH": "s5.m_cash", "BANK": "s5.m_bank", "TRANSFER": "s5.m_transfer",
                "CHEQUE": "s5.m_cheque", "OTHER": "s5.m_other"}


def _method_label(translator, code) -> str:
    if not code:
        return ""
    return translator.gettext(_METHOD_KEYS.get(str(code).upper(), "s5.m_cash"))


def build_receipt_voucher(ctx: ApplicationContext, translator, receipt_id: int) -> VoucherData:
    r = ctx.receipts_ext_repo.get_full(receipt_id)
    if r is None:
        raise ValueError(f"No receipt {receipt_id}")
    return VoucherData(
        company=_company_info(ctx),
        title_key="s5.print.receipt_title", party_label_key="s5.v_received_from",
        counter_sign_key="s5.v_received_by",
        number=r["document_no"], date=r["receipt_date"],
        currency=r.get("currency_code") or "", amount=_f(r["amount"]),
        party_name=r.get("party_name") or "—", party_code=r.get("party_code") or "",
        party_phone=r.get("party_phone") or "", account_name=r.get("account_name") or "",
        method_label=_method_label(translator, r.get("payment_method")),
        reference=r.get("reference") or "", being=r.get("notes") or "",
        prepared_by=r.get("user_name") or "")


def build_payment_voucher(ctx: ApplicationContext, translator, payment_id: int) -> VoucherData:
    p = ctx.payments_ext_repo.get_full(payment_id)
    if p is None:
        raise ValueError(f"No payment {payment_id}")
    return VoucherData(
        company=_company_info(ctx),
        title_key="s5.print.payment_title", party_label_key="s5.v_paid_to",
        counter_sign_key="s5.v_paid_by",
        number=p["document_no"], date=p["payment_date"],
        currency=p.get("currency_code") or "", amount=_f(p["amount"]),
        party_name=p.get("party_name") or "—", party_code=p.get("party_code") or "",
        party_phone=p.get("party_phone") or "", account_name=p.get("account_name") or "",
        method_label=_method_label(translator, p.get("payment_method")),
        reference=p.get("reference") or "", being=p.get("notes") or "",
        prepared_by=p.get("user_name") or "")


def build_expense_voucher(ctx: ApplicationContext, translator, expense_id: int) -> VoucherData:
    e = ctx.expenses_ext_repo.get_full(expense_id)
    if e is None:
        raise ValueError(f"No expense {expense_id}")
    detail_rows = []
    if e.get("payee"):
        detail_rows.append(("s5.v_paid_to", e["payee"]))
    return VoucherData(
        company=_company_info(ctx),
        title_key="s5.print.expense_title", party_label_key="s5.v_category",
        counter_sign_key="s5.v_paid_by",
        number=e["document_no"], date=e["expense_date"],
        currency=e.get("currency_code") or "", amount=_f(e["amount"]),
        party_name=e.get("category_name") or "—", account_name=e.get("account_name") or "",
        method_label=_method_label(translator, e.get("payment_method")),
        reference=e.get("reference") or "",
        being=e.get("description") or e.get("notes") or "",
        prepared_by=e.get("user_name") or "", detail_rows=detail_rows)
