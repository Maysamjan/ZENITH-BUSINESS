"""Party (customer/supplier) service (Stage 03 §15, §16, §23).

One party may be a customer, a supplier, or both — no duplicate records. Enforces
code uniqueness, required name, at least one role, Decimal-safe non-negative
credit limit / opening balance, and audits changes.
"""

from __future__ import annotations

from zenith_business.core.money import money
from zenith_business.database.connection import Database
from zenith_business.repositories.parties import PartyRepository
from zenith_business.repositories.system import AuditRepository
from zenith_business.services.authorization import AuthorizationService
from zenith_business.services.document_math import parse_money_input
from zenith_business.services.exceptions import ValidationError
from zenith_business.services.session import SessionContext


class PartyService:
    def __init__(self, db: Database, parties: PartyRepository, audit: AuditRepository,
                 session: SessionContext, authz: AuthorizationService) -> None:
        self._db = db
        self._parties = parties
        self._audit = audit
        self._session = session
        self._authz = authz

    def list(self, *, role: str | None = None, include_inactive: bool = True,
             limit: int = 500) -> list[dict]:
        self._authz.require("persons.view")
        return self._parties.list(role=role, include_inactive=include_inactive, limit=limit)

    def search(self, term: str, *, role: str | None = None, limit: int = 10) -> list[dict]:
        self._authz.require("persons.view")
        return self._parties.search(term, role=role, limit=limit)

    def get(self, party_id: int) -> dict | None:
        self._authz.require("persons.view")
        return self._parties.get(party_id)

    def _validate(self, *, party_code, name, is_customer, is_supplier,
                  credit_limit, opening_balance):
        party_code = (party_code or "").strip()
        name = (name or "").strip()
        if not party_code:
            raise ValidationError("Person code is required.",
                                  user_message="Person code is required.")
        if not name:
            raise ValidationError("Name is required.", user_message="Name is required.")
        if not (is_customer or is_supplier):
            raise ValidationError("A person must be a customer, a supplier, or both.",
                                  user_message="Select at least one role (customer or supplier).")
        cl = money(parse_money_input(credit_limit, field="credit limit"))
        ob = money(parse_money_input(opening_balance, field="opening balance"))
        if cl < 0:
            raise ValidationError("Credit limit cannot be negative.",
                                  user_message="Credit limit cannot be negative.")
        return party_code, name, cl, ob

    def create(self, *, party_code: str, name: str, is_customer: bool = False,
               is_supplier: bool = False, company_name: str | None = None,
               phone: str | None = None, secondary_phone: str | None = None,
               email: str | None = None, address: str | None = None, city: str | None = None,
               tax_id: str | None = None, credit_limit=0, opening_balance=0,
               notes: str | None = None) -> int:
        self._authz.require("persons.create")
        party_code, name, cl, ob = self._validate(
            party_code=party_code, name=name, is_customer=is_customer, is_supplier=is_supplier,
            credit_limit=credit_limit, opening_balance=opening_balance)
        if self._parties.code_exists(party_code):
            raise ValidationError("Duplicate person code.",
                                  user_message="That person code already exists.")
        with self._db.transaction():
            pid = self._parties.create(
                party_code=party_code, name=name, is_customer=is_customer,
                is_supplier=is_supplier, company_name=company_name, phone=phone,
                secondary_phone=secondary_phone, email=email, address=address, city=city,
                tax_id=tax_id, credit_limit=cl, opening_balance=ob, notes=notes)
            roles = "+".join(r for r, on in (("customer", is_customer), ("supplier", is_supplier)) if on)
            self._audit.record(action="persons.create", user_id=self._session.user_id,
                               username=self._session.username, entity_type="party",
                               entity_id=pid, details=f"code={party_code} roles={roles}")
        return pid

    def update(self, party_id: int, *, name: str, is_customer: bool, is_supplier: bool,
               company_name: str | None = None, phone: str | None = None,
               secondary_phone: str | None = None, email: str | None = None,
               address: str | None = None, city: str | None = None, tax_id: str | None = None,
               credit_limit=0, opening_balance=0, notes: str | None = None) -> None:
        self._authz.require("persons.edit")
        if self._parties.get(party_id) is None:
            raise ValidationError("No such person.")
        _code, name, cl, ob = self._validate(
            party_code="x", name=name, is_customer=is_customer, is_supplier=is_supplier,
            credit_limit=credit_limit, opening_balance=opening_balance)
        with self._db.transaction():
            self._parties.update(
                party_id, name=name, is_customer=is_customer, is_supplier=is_supplier,
                company_name=company_name, phone=phone, secondary_phone=secondary_phone,
                email=email, address=address, city=city, tax_id=tax_id, credit_limit=cl,
                opening_balance=ob, notes=notes)
            self._audit.record(action="persons.update", user_id=self._session.user_id,
                               username=self._session.username, entity_type="party",
                               entity_id=party_id)

    def set_active(self, party_id: int, active: bool) -> None:
        self._authz.require("persons.edit")
        with self._db.transaction():
            self._parties.set_active(party_id, active)
            self._audit.record(action="persons.activate" if active else "persons.deactivate",
                               user_id=self._session.user_id, username=self._session.username,
                               entity_type="party", entity_id=party_id)
