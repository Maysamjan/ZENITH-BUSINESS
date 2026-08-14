"""Financial-year service (Stage 03 §6).

Owns the higher-level rules on top of the ``financial_years`` table: valid date
range, exactly one active year, close/reopen (permission-controlled), and a
posting guard. The guard (`assert_postable`) is exposed for the FUTURE transaction
modules to call — it is deliberately NOT retrofitted into the LOCKED Stage 02
sales/purchase posting (that would change a locked contract); it will be wired in
when those production modules are built.
"""

from __future__ import annotations

from zenith_business.database.connection import Database
from zenith_business.repositories.financial_years import FinancialYearRepository
from zenith_business.repositories.system import AuditRepository
from zenith_business.services.authorization import AuthorizationService
from zenith_business.services.exceptions import ValidationError
from zenith_business.services.session import SessionContext


def _is_iso_date(value: str) -> bool:
    from zenith_business.core.clock import to_date
    return bool(value) and to_date(value) is not None and len(value) == 10


class FinancialYearService:
    def __init__(self, db: Database, years: FinancialYearRepository, audit: AuditRepository,
                 session: SessionContext, authz: AuthorizationService) -> None:
        self._db = db
        self._years = years
        self._audit = audit
        self._session = session
        self._authz = authz

    def list(self) -> list[dict]:
        self._authz.require("financialyear.view")
        return self._years.list_all()

    def active(self) -> dict | None:
        self._authz.require("financialyear.view")
        return self._years.active()

    def create(self, *, name: str, start_date: str, end_date: str,
               make_active: bool = False) -> int:
        self._authz.require("financialyear.manage")
        name = (name or "").strip()
        if not name:
            raise ValidationError("Financial year name is required.",
                                  user_message="Financial year name is required.")
        if not _is_iso_date(start_date) or not _is_iso_date(end_date):
            raise ValidationError("Dates must be YYYY-MM-DD.",
                                  user_message="Please enter valid start and end dates.")
        if start_date >= end_date:
            raise ValidationError("Start date must be before end date.",
                                  user_message="The start date must be before the end date.")
        if self._years.get_by_name(name) is not None:
            raise ValidationError("Duplicate financial year name.",
                                  user_message="A financial year with that name already exists.")
        if self._years.overlapping(start_date, end_date):
            raise ValidationError("Overlapping financial year.",
                                  user_message="This period overlaps an existing financial year.")
        with self._db.transaction():
            if make_active:
                self._years.clear_active()
            year_id = self._years.create(name=name, start_date=start_date, end_date=end_date,
                                         is_active=make_active)
            self._audit.record(action="financialyear.create", user_id=self._session.user_id,
                               username=self._session.username, entity_type="financial_year",
                               entity_id=year_id, details=f"name={name}")
        return year_id

    def set_active(self, year_id: int) -> None:
        self._authz.require("financialyear.manage")
        year = self._years.get(year_id)
        if year is None:
            raise ValidationError("No such financial year.")
        if year["status"] == "CLOSED":
            raise ValidationError("Cannot activate a closed year.",
                                  user_message="A closed financial year cannot be made active.")
        with self._db.transaction():
            self._years.clear_active()
            self._years.set_active(year_id)
            self._audit.record(action="financialyear.activate", user_id=self._session.user_id,
                               username=self._session.username, entity_type="financial_year",
                               entity_id=year_id)

    def close(self, year_id: int) -> None:
        self._authz.require("financialyear.manage")
        year = self._years.get(year_id)
        if year is None:
            raise ValidationError("No such financial year.")
        if year["status"] == "CLOSED":
            raise ValidationError("Year already closed.",
                                  user_message="This financial year is already closed.")
        with self._db.transaction():
            self._years.close(year_id, self._session.user_id)
            self._audit.record(action="financialyear.close", user_id=self._session.user_id,
                               username=self._session.username, entity_type="financial_year",
                               entity_id=year_id)

    def reopen(self, year_id: int) -> None:
        self._authz.require("financialyear.manage")
        year = self._years.get(year_id)
        if year is None:
            raise ValidationError("No such financial year.")
        with self._db.transaction():
            self._years.reopen(year_id)
            self._audit.record(action="financialyear.reopen", user_id=self._session.user_id,
                               username=self._session.username, entity_type="financial_year",
                               entity_id=year_id)

    # ---- posting guard for future transaction modules -------------------

    def is_postable(self, date: str) -> bool:
        """True if ``date`` falls inside the active, OPEN financial year."""
        year = self._years.active()
        if year is None or year["status"] != "OPEN":
            return False
        return year["start_date"] <= date <= year["end_date"]

    def assert_postable(self, date: str) -> None:
        if not self.is_postable(date):
            raise ValidationError(
                f"No open financial year for date {date}.",
                user_message="This date is not within an open financial year.")
