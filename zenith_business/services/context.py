"""Application context — dependency wiring (Stage 02 §4, §48).

A single composition root that, given an open :class:`Database`, builds every
repository and service and the shared :class:`SessionContext`. The UI and the
startup sequence talk to this object; they never construct repositories or run
SQL themselves. This keeps the layered architecture (UI → service → repository →
database) honest and testable.
"""

from __future__ import annotations

from pathlib import Path

from zenith_business.core.logging_setup import get_logger
from zenith_business.database.connection import Database
from zenith_business.database.migrations import MigrationRunner
from zenith_business.repositories.documents import (
    ExpenseRepository,
    FinancialRepository,
    InventoryRepository,
    PaymentRepository,
    PurchaseRepository,
    ReceiptRepository,
    SalesRepository,
)
from zenith_business.repositories.master import (
    AccountRepository,
    CategoryRepository,
    CompanyRepository,
    CurrencyRepository,
    CustomerRepository,
    ExchangeRateRepository,
    ItemRepository,
    SupplierRepository,
    UnitRepository,
    WarehouseRepository,
)
from zenith_business.repositories.system import (
    AppSettingsRepository,
    AuditRepository,
    DocumentSequenceRepository,
)
from zenith_business.repositories.users import (
    PermissionRepository,
    RoleRepository,
    UserRepository,
)
from zenith_business.services.audit_service import AuditService
from zenith_business.services.authentication import AuthenticationService
from zenith_business.services.authorization import AuthorizationService
from zenith_business.services.backup import BackupService
from zenith_business.services.financial import FinancialService
from zenith_business.services.inventory import InventoryService
from zenith_business.services.numbering import DocumentNumberService
from zenith_business.services.purchases import PurchaseService
from zenith_business.services.sales import SalesService
from zenith_business.services.session import SessionContext
from zenith_business.services.setup import InitialSetupService
from zenith_business.services.users import UserService

_logger = get_logger("services.context")


class ApplicationContext:
    """Composition root holding all repositories and services for one database."""

    def __init__(self, db: Database, *, backups_dir: Path | None = None) -> None:
        self.db = db
        self.session = SessionContext()

        # ---- repositories ----
        self.users_repo = UserRepository(db)
        self.roles_repo = RoleRepository(db)
        self.permissions_repo = PermissionRepository(db)
        self.units_repo = UnitRepository(db)
        self.categories_repo = CategoryRepository(db)
        self.warehouses_repo = WarehouseRepository(db)
        self.currencies_repo = CurrencyRepository(db)
        self.exchange_rates_repo = ExchangeRateRepository(db)
        self.items_repo = ItemRepository(db)
        self.customers_repo = CustomerRepository(db)
        self.suppliers_repo = SupplierRepository(db)
        self.accounts_repo = AccountRepository(db)
        self.company_repo = CompanyRepository(db)
        self.sales_repo = SalesRepository(db)
        self.purchases_repo = PurchaseRepository(db)
        self.inventory_repo = InventoryRepository(db)
        self.receipts_repo = ReceiptRepository(db)
        self.payments_repo = PaymentRepository(db)
        self.expenses_repo = ExpenseRepository(db)
        self.financial_repo = FinancialRepository(db)
        self.audit_repo = AuditRepository(db)
        self.sequences_repo = DocumentSequenceRepository(db)
        self.settings_repo = AppSettingsRepository(db)

        # ---- services ----
        self.authz = AuthorizationService(self.session)
        self.audit = AuditService(self.audit_repo, self.session)
        self.numbering = DocumentNumberService(db, self.sequences_repo)
        self.financial = FinancialService(
            db, self.financial_repo, self.numbering, self.session)
        self.auth = AuthenticationService(db, self.users_repo, self.audit_repo, self.session)
        self.setup = InitialSetupService(
            db, self.users_repo, self.roles_repo, self.audit_repo, self.settings_repo)
        self.users = UserService(
            db, self.users_repo, self.roles_repo, self.audit_repo, self.session, self.authz)
        self.sales = SalesService(
            db, self.sales_repo, self.inventory_repo, self.financial_repo,
            self.accounts_repo, self.currencies_repo, self.items_repo, self.numbering,
            self.audit_repo, self.session, self.authz)
        self.purchases = PurchaseService(
            db, self.purchases_repo, self.inventory_repo, self.financial_repo,
            self.accounts_repo, self.currencies_repo, self.items_repo, self.numbering,
            self.audit_repo, self.session, self.authz)
        self.inventory = InventoryService(
            db, self.inventory_repo, self.audit_repo, self.session, self.authz)
        self.backup = BackupService(
            db, backups_dir or Path("."), self.audit_repo, self.session, self.authz)

    # ---- convenience ----
    @property
    def is_setup_required(self) -> bool:
        return self.setup.is_setup_required()

    @property
    def is_authenticated(self) -> bool:
        return self.session.is_authenticated


def open_application_context(
    db: Database, *, backups_dir: Path | None = None
) -> ApplicationContext:
    """Run pending migrations, then build the application context.

    This is the single entry the startup sequence and tests use to obtain a
    fully-wired, migrated database context.
    """
    db.connect()
    applied = MigrationRunner(db).migrate()
    if applied:
        _logger.info("Database migrated to schema (applied %s).", applied)
    return ApplicationContext(db, backups_dir=backups_dir)
