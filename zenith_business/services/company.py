"""Company / business profile service (Stage 03 §5).

A single company record holds the business identity used by the shell, invoices,
reports and the print engine. Logo is stored as a path under the app data dir
(never an arbitrary developer-machine absolute path). Changes are audited.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from zenith_business.core.logging_setup import get_logger
from zenith_business.database.connection import Database
from zenith_business.repositories.master import (
    CompanyRepository,
    CurrencyRepository,
    WarehouseRepository,
)
from zenith_business.repositories.system import AuditRepository
from zenith_business.services.authorization import AuthorizationService
from zenith_business.services.exceptions import ValidationError
from zenith_business.services.session import SessionContext

_logger = get_logger("services.company")


class CompanyService:
    def __init__(self, db: Database, company: CompanyRepository,
                 currencies: CurrencyRepository, audit: AuditRepository,
                 session: SessionContext, authz: AuthorizationService,
                 logo_dir: Path | None = None,
                 warehouses: WarehouseRepository | None = None) -> None:
        self._db = db
        self._company = company
        self._currencies = currencies
        self._warehouses = warehouses
        self._audit = audit
        self._session = session
        self._authz = authz
        self._logo_dir = Path(logo_dir) if logo_dir else None

    def get(self) -> dict | None:
        self._authz.require("company.manage")
        return self._company.get()

    def save(self, *, legal_name: str, display_name: str | None = None,
             trade_name: str | None = None, address: str | None = None,
             city: str | None = None, country: str | None = None, phone: str | None = None,
             secondary_phone: str | None = None, email: str | None = None,
             website: str | None = None, tax_id: str | None = None,
             registration_number: str | None = None, default_currency_id: int | None = None,
             default_warehouse_id: int | None = None, default_language: str = "fa_AF",
             logo_path: str | None = None, invoice_footer: str | None = None,
             invoice_terms: str | None = None) -> int:
        self._authz.require("company.manage")
        legal_name = (legal_name or "").strip()
        if not legal_name:
            raise ValidationError("Business name is required.",
                                  user_message="Business name is required.")
        if default_currency_id is not None and self._currencies.get(default_currency_id) is None:
            raise ValidationError("Unknown base currency.")
        # Never store a dangling default warehouse reference (§8).
        if (default_warehouse_id is not None and self._warehouses is not None
                and self._warehouses.get(default_warehouse_id) is None):
            raise ValidationError(
                "Unknown default warehouse.",
                user_message="The selected default warehouse does not exist.")
        with self._db.transaction():
            cid = self._company.upsert(
                legal_name=legal_name, display_name=display_name, trade_name=trade_name,
                address=address, city=city, country=country, phone=phone,
                secondary_phone=secondary_phone, email=email, website=website, tax_id=tax_id,
                registration_number=registration_number, default_currency_id=default_currency_id,
                default_warehouse_id=default_warehouse_id, default_language=default_language,
                logo_path=logo_path, invoice_footer=invoice_footer, invoice_terms=invoice_terms)
            self._audit.record(action="company.update", user_id=self._session.user_id,
                               username=self._session.username, entity_type="company",
                               entity_id=cid, details=f"name={legal_name}")
        return cid

    def import_logo(self, source_path: str | Path) -> str:
        """Copy a chosen logo into the managed app data dir; return the stored path.

        Storing a copy (not the original absolute path) keeps the logo available
        for Home/invoices/reports/print even if the source file later moves (§5).
        """
        self._authz.require("company.manage")
        src = Path(source_path)
        if not src.exists() or not src.is_file():
            raise ValidationError("Logo file not found.",
                                  user_message="The selected logo file could not be found.")
        if src.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            raise ValidationError(
                f"Unsupported logo type: {src.suffix}",
                user_message="Please choose a valid PNG or JPG image.")
        if self._logo_dir is None:
            raise ValidationError("No logo storage location configured.")
        self._logo_dir.mkdir(parents=True, exist_ok=True)
        target = self._logo_dir / f"company_logo{src.suffix.lower()}"
        shutil.copy2(src, target)
        _logger.info("Company logo stored at %s", target)
        return str(target)
