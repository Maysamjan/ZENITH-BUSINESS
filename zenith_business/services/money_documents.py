"""Stage 05 money-movement services — receipts, payments, expenses.

Each posted document is ONE atomic transaction composed from LOCKED primitives:
header (Stage 02 repo) + Stage 05 metadata + balanced double-entry ledger
(FinancialRepository) + party-balance effect (ledger-derived) + document number
+ audit — all commit or all roll back. Money is Decimal end to end; malformed /
non-finite / zero / negative input is rejected before any write.

Ledger direction:
    Receipt : Dr <fund cash/bank>            Cr Accounts Receivable (customer)
    Payment : Dr Accounts Payable (supplier) Cr <fund cash/bank>
    Expense : Dr <expense account>           Cr <fund cash/bank>

Customer/supplier balances are never edited directly — a receipt/payment moves the
party's ledger balance, and the Stage 04 ``PartyBalanceRepository`` re-derives it.
"""

from __future__ import annotations

from dataclasses import dataclass

from zenith_business.core.clock import now_iso, today_iso
from zenith_business.core.logging_setup import get_logger
from zenith_business.core.money import D, money
from zenith_business.database.connection import Database
from zenith_business.repositories.documents import ExpenseRepository, FinancialRepository, \
    PaymentRepository, ReceiptRepository
from zenith_business.repositories.documents_s4 import PartyBalanceRepository
from zenith_business.repositories.master import AccountRepository, CurrencyRepository
from zenith_business.repositories.money_s5 import (
    ExpenseCategoryRepository,
    ExpenseExtRepository,
    FundRepository,
    PaymentExtRepository,
    ReceiptExtRepository,
)
from zenith_business.repositories.parties import PartyRepository
from zenith_business.repositories.system import AuditRepository
from zenith_business.services.authorization import AuthorizationService
from zenith_business.services.document_math import assert_journal_balanced, parse_money_input
from zenith_business.services.exceptions import ValidationError
from zenith_business.services.financial_year import FinancialYearService
from zenith_business.services.numbering import DocumentNumberService
from zenith_business.services.session import SessionContext

_logger = get_logger("services.money_doc")

_ACCT_AR = "1100"
_ACCT_AP = "2000"

# Recognised payment methods (stored as a stable code; the UI localises the label).
PAYMENT_METHODS = ("CASH", "BANK", "TRANSFER", "CHEQUE", "OTHER")


@dataclass
class PostedMoneyDoc:
    id: int
    document_no: str
    amount: str
    remaining: str = "0.00"


def _positive_amount(value, *, field: str) -> D:
    amount = money(parse_money_input(value, field=field))
    if amount <= 0:
        raise ValidationError(f"{field} must be greater than zero.",
                              user_message="The amount must be greater than zero.")
    return amount


def _valid_rate(value) -> D:
    rate = money(parse_money_input(value, field="exchange rate"))
    if rate <= 0:
        raise ValidationError("Exchange rate must be greater than zero.",
                              user_message="The exchange rate must be greater than zero.")
    return rate


def _valid_method(method: str | None) -> str:
    m = (method or "CASH").upper()
    if m not in PAYMENT_METHODS:
        raise ValidationError(f"Unknown payment method {method!r}.",
                              user_message="Select a valid payment method.")
    return m


class _MoneyBase:
    def __init__(self, db, accounts, currencies, parties, balances, funds,
                 numbering, audit, session, authz, financial_years):
        self._db = db
        self._accounts = accounts
        self._currencies = currencies
        self._parties = parties
        self._balances = balances
        self._funds = funds
        self._numbering = numbering
        self._audit = audit
        self._session = session
        self._authz = authz
        self._fy = financial_years

    def _resolve_currency(self, code: str) -> dict:
        currency = self._currencies.get_by_code(code)
        if currency is None:
            raise ValidationError(f"Unknown currency {code!r}.",
                                  user_message="Select a valid currency.")
        return currency

    def _resolve_fund(self, account_id: int | None) -> dict:
        if account_id is None:
            raise ValidationError("A cash/bank/fund account is required.",
                                  user_message="Select the cash/bank/fund account.")
        fund = self._funds.get(account_id)
        if fund is None or not fund["is_active"] or not fund["is_fund"]:
            raise ValidationError("Unknown or invalid fund account.",
                                  user_message="The selected fund account is not available.")
        return fund

    def _resolve_party(self, party_id: int | None, *, role: str) -> dict:
        if party_id is None:
            raise ValidationError(f"A {role} is required.",
                                  user_message=f"Select a {role}.")
        party = self._parties.get(party_id)
        if party is None or not party["is_active"]:
            raise ValidationError("Unknown or inactive party.",
                                  user_message="The selected party is not available.")
        if role == "customer" and not party["is_customer"]:
            raise ValidationError("Party is not a customer.",
                                  user_message="That party is not a customer.")
        if role == "supplier" and not party["is_supplier"]:
            raise ValidationError("Party is not a supplier.",
                                  user_message="That party is not a supplier.")
        return party


class ReceiptService(_MoneyBase):
    def __init__(self, db: Database, receipts: ReceiptRepository, ext: ReceiptExtRepository,
                 financial: FinancialRepository, accounts: AccountRepository,
                 currencies: CurrencyRepository, parties: PartyRepository,
                 balances: PartyBalanceRepository, funds: FundRepository,
                 numbering: DocumentNumberService, audit: AuditRepository,
                 session: SessionContext, authz: AuthorizationService,
                 financial_years: FinancialYearService) -> None:
        super().__init__(db, accounts, currencies, parties, balances, funds,
                         numbering, audit, session, authz, financial_years)
        self._receipts = receipts
        self._ext = ext
        self._financial = financial

    def list(self, **kw) -> list[dict]:
        self._authz.require("receipts.view")
        return self._ext.list_documents(**kw)

    def get(self, receipt_id: int) -> dict | None:
        self._authz.require("receipts.view")
        return self._ext.get_full(receipt_id)

    def receivable(self, party_id: int) -> str:
        self._authz.require("receipts.view")
        return self._balances.receivable(party_id)

    def post_receipt(self, *, party_id: int, account_id: int, amount,
                     currency_code: str, exchange_rate=1, payment_method: str | None = None,
                     reference: str | None = None, notes: str | None = None,
                     receipt_date: str | None = None) -> PostedMoneyDoc:
        self._authz.require("receipts.create")
        date = receipt_date or today_iso()
        self._fy.assert_postable(date)
        amt = _positive_amount(amount, field="amount received")
        rate = _valid_rate(exchange_rate)
        method = _valid_method(payment_method)
        currency = self._resolve_currency(currency_code)
        fund = self._resolve_fund(account_id)
        self._resolve_party(party_id, role="customer")
        uid = self._session.user_id

        with self._db.transaction():
            document_no = self._numbering.allocate("RCP")
            receipt_id = self._receipts.create(
                document_no=document_no, receipt_date=date, currency_id=currency["id"],
                amount=amt, customer_id=None, account_id=fund["id"], exchange_rate=rate,
                reference=reference, notes=notes, status="POSTED", created_by=uid)
            self._ext.set_meta(receipt_id, party_id=party_id, payment_method=method,
                               posted_at=now_iso(), posted_by=uid)
            self._post_ledger(receipt_id, document_no, date, amt, fund["id"], party_id,
                              currency["id"], uid)
            self._audit.record(action="receipts.create", user_id=uid,
                               username=self._session.username, entity_type="receipt",
                               entity_id=receipt_id, document_no=document_no,
                               details=f"party={party_id} amount={amt} fund={fund['code']}")
        remaining = self._balances.receivable(party_id)
        _logger.info("Posted receipt %s (amount=%s)", document_no, amt)
        return PostedMoneyDoc(receipt_id, document_no, str(amt), remaining)

    def _post_ledger(self, receipt_id, doc_no, date, amt, fund_id, party_id, currency_id, uid):
        entry_no = self._numbering.allocate("JV")
        entry_id = self._financial.create_entry(
            entry_no=entry_no, entry_date=date, source_type="RECEIPT", source_id=receipt_id,
            description=f"Receipt {doc_no}", created_by=uid)
        self._financial.add_line(entry_id=entry_id, account_id=fund_id, debit=amt,
                                 currency_id=currency_id, memo="Cash/bank received")
        self._financial.add_line(entry_id=entry_id,
                                 account_id=self._accounts.id_by_code(_ACCT_AR),
                                 credit=amt, party_type="CUSTOMER", party_id=party_id,
                                 currency_id=currency_id, memo="Settle receivable")
        assert_journal_balanced(self._financial, entry_id)


class PaymentService(_MoneyBase):
    def __init__(self, db: Database, payments: PaymentRepository, ext: PaymentExtRepository,
                 financial: FinancialRepository, accounts: AccountRepository,
                 currencies: CurrencyRepository, parties: PartyRepository,
                 balances: PartyBalanceRepository, funds: FundRepository,
                 numbering: DocumentNumberService, audit: AuditRepository,
                 session: SessionContext, authz: AuthorizationService,
                 financial_years: FinancialYearService) -> None:
        super().__init__(db, accounts, currencies, parties, balances, funds,
                         numbering, audit, session, authz, financial_years)
        self._payments = payments
        self._ext = ext
        self._financial = financial

    def list(self, **kw) -> list[dict]:
        self._authz.require("payments.view")
        return self._ext.list_documents(**kw)

    def get(self, payment_id: int) -> dict | None:
        self._authz.require("payments.view")
        return self._ext.get_full(payment_id)

    def payable(self, party_id: int) -> str:
        self._authz.require("payments.view")
        return self._balances.payable(party_id)

    def post_payment(self, *, party_id: int, account_id: int, amount,
                     currency_code: str, exchange_rate=1, payment_method: str | None = None,
                     reference: str | None = None, notes: str | None = None,
                     payment_date: str | None = None) -> PostedMoneyDoc:
        self._authz.require("payments.create")
        date = payment_date or today_iso()
        self._fy.assert_postable(date)
        amt = _positive_amount(amount, field="amount paid")
        rate = _valid_rate(exchange_rate)
        method = _valid_method(payment_method)
        currency = self._resolve_currency(currency_code)
        fund = self._resolve_fund(account_id)
        self._resolve_party(party_id, role="supplier")
        uid = self._session.user_id

        with self._db.transaction():
            document_no = self._numbering.allocate("PAY")
            payment_id = self._payments.create(
                document_no=document_no, payment_date=date, currency_id=currency["id"],
                amount=amt, supplier_id=None, account_id=fund["id"], exchange_rate=rate,
                reference=reference, notes=notes, status="POSTED", created_by=uid)
            self._ext.set_meta(payment_id, party_id=party_id, payment_method=method,
                               posted_at=now_iso(), posted_by=uid)
            self._post_ledger(payment_id, document_no, date, amt, fund["id"], party_id,
                              currency["id"], uid)
            self._audit.record(action="payments.create", user_id=uid,
                               username=self._session.username, entity_type="payment",
                               entity_id=payment_id, document_no=document_no,
                               details=f"party={party_id} amount={amt} fund={fund['code']}")
        remaining = self._balances.payable(party_id)
        _logger.info("Posted payment %s (amount=%s)", document_no, amt)
        return PostedMoneyDoc(payment_id, document_no, str(amt), remaining)

    def _post_ledger(self, payment_id, doc_no, date, amt, fund_id, party_id, currency_id, uid):
        entry_no = self._numbering.allocate("JV")
        entry_id = self._financial.create_entry(
            entry_no=entry_no, entry_date=date, source_type="PAYMENT", source_id=payment_id,
            description=f"Payment {doc_no}", created_by=uid)
        self._financial.add_line(entry_id=entry_id,
                                 account_id=self._accounts.id_by_code(_ACCT_AP),
                                 debit=amt, party_type="SUPPLIER", party_id=party_id,
                                 currency_id=currency_id, memo="Settle payable")
        self._financial.add_line(entry_id=entry_id, account_id=fund_id, credit=amt,
                                 currency_id=currency_id, memo="Cash/bank paid")
        assert_journal_balanced(self._financial, entry_id)


class ExpenseService(_MoneyBase):
    def __init__(self, db: Database, expenses: ExpenseRepository, ext: ExpenseExtRepository,
                 categories: ExpenseCategoryRepository, financial: FinancialRepository,
                 accounts: AccountRepository, currencies: CurrencyRepository,
                 parties: PartyRepository, balances: PartyBalanceRepository,
                 funds: FundRepository, numbering: DocumentNumberService,
                 audit: AuditRepository, session: SessionContext,
                 authz: AuthorizationService, financial_years: FinancialYearService) -> None:
        super().__init__(db, accounts, currencies, parties, balances, funds,
                         numbering, audit, session, authz, financial_years)
        self._expenses = expenses
        self._ext = ext
        self._categories = categories
        self._financial = financial

    def list(self, **kw) -> list[dict]:
        self._authz.require("expenses.view")
        return self._ext.list_documents(**kw)

    def get(self, expense_id: int) -> dict | None:
        self._authz.require("expenses.view")
        return self._ext.get_full(expense_id)

    def categories(self) -> list[dict]:
        self._authz.require("expenses.view")
        return self._categories.list_active()

    def post_expense(self, *, category_id: int, account_id: int, amount,
                     currency_code: str, exchange_rate=1, payment_method: str | None = None,
                     payee: str | None = None, reference: str | None = None,
                     description: str | None = None, notes: str | None = None,
                     expense_date: str | None = None) -> PostedMoneyDoc:
        self._authz.require("expenses.create")
        date = expense_date or today_iso()
        self._fy.assert_postable(date)
        amt = _positive_amount(amount, field="expense amount")
        rate = _valid_rate(exchange_rate)
        method = _valid_method(payment_method)
        currency = self._resolve_currency(currency_code)
        fund = self._resolve_fund(account_id)
        category = self._categories.get(category_id)
        if category is None or not category["is_active"]:
            raise ValidationError("Unknown or inactive expense category.",
                                  user_message="Select a valid expense category.")
        expense_account_id = category["account_id"] or self._accounts.id_by_code("6000")
        if expense_account_id is None:
            raise ValidationError("Expense category has no expense account.",
                                  user_message="This expense category is not configured.")
        uid = self._session.user_id

        with self._db.transaction():
            document_no = self._numbering.allocate("EXP")
            expense_id = self._expenses.create(
                document_no=document_no, expense_date=date, currency_id=currency["id"],
                amount=amt, expense_category_id=category_id, account_id=fund["id"],
                exchange_rate=rate, payee=payee, description=description, reference=reference,
                status="POSTED", created_by=uid)
            self._ext.set_meta(expense_id, payment_method=method, notes=notes,
                               posted_at=now_iso(), posted_by=uid)
            self._post_ledger(expense_id, document_no, date, amt, expense_account_id,
                              fund["id"], currency["id"], uid)
            self._audit.record(action="expenses.create", user_id=uid,
                               username=self._session.username, entity_type="expense",
                               entity_id=expense_id, document_no=document_no,
                               details=f"category={category_id} amount={amt} fund={fund['code']}")
        _logger.info("Posted expense %s (amount=%s)", document_no, amt)
        return PostedMoneyDoc(expense_id, document_no, str(amt))

    def _post_ledger(self, expense_id, doc_no, date, amt, expense_account_id, fund_id,
                     currency_id, uid):
        entry_no = self._numbering.allocate("JV")
        entry_id = self._financial.create_entry(
            entry_no=entry_no, entry_date=date, source_type="EXPENSE", source_id=expense_id,
            description=f"Expense {doc_no}", created_by=uid)
        self._financial.add_line(entry_id=entry_id, account_id=expense_account_id, debit=amt,
                                 currency_id=currency_id, memo="Expense")
        self._financial.add_line(entry_id=entry_id, account_id=fund_id, credit=amt,
                                 currency_id=currency_id, memo="Cash/bank paid")
        assert_journal_balanced(self._financial, entry_id)
