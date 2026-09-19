"""Application bootstrap and entry point (Prompt 01 §4, Stage 02 §2).

Startup responsibilities are clearly separated into small steps so future stages
can extend them at well-defined extension points.

Production startup order (Stage 02):
    1. resolve + create data directories
    2. load configuration
    3. initialize logging
    4. install global exception handler
    5. [extension point] license verification  -> dev provider only
    6. open database + run migrations + health check
    7. build the application context (repositories + services + session)
    8. create QApplication + apply theme
    9. AUTHENTICATION GATE (initial setup / login) — never straight to dashboard
   10. create + show MainWindow for the authenticated user
"""

from __future__ import annotations

import sys

from zenith_business.core.config import AppConfig, load_config
from zenith_business.core.error_handler import install_global_exception_handler
from zenith_business.core.identity import IDENTITY
from zenith_business.core.logging_setup import get_logger, setup_logging
from zenith_business.core.paths import resolve_paths
from zenith_business.database import Database, check_health
from zenith_business.security.licensing import DevelopmentLicenseProvider
from zenith_business.services.context import ApplicationContext, open_application_context


class Bootstrap:
    """Headless startup steps, separated from Qt so they are unit-testable.

    Running the GUI is a thin wrapper around this (see :func:`run`). Tests can
    drive :meth:`initialize` without creating a QApplication, obtaining a fully
    migrated :class:`ApplicationContext`.
    """

    def __init__(self) -> None:
        self.config: AppConfig | None = None
        self.database: Database | None = None
        self.context: ApplicationContext | None = None
        self.license_provider = DevelopmentLicenseProvider()

    def initialize(self) -> AppConfig:
        """Perform non-GUI startup steps and return the loaded config."""
        # 1. data directories
        paths = resolve_paths().ensure()

        # 2. configuration
        self.config = load_config(paths)

        # 3. logging
        setup_logging(paths.logs_dir, self.config.logging)
        logger = get_logger("app")
        logger.info(
            "Starting %s (%s build) — config=%s",
            IDENTITY.full_title,
            IDENTITY.channel,
            paths.config_file,
        )

        # 4. global exception handling
        install_global_exception_handler()

        # 5. open the production database, run migrations, health-check
        self.database = Database(paths.database_file)
        self.context = open_application_context(
            self.database, backups_dir=paths.backups_dir,
            logo_dir=paths.data_dir / "company",
            # Licence state lives beside the config, NOT with the business data,
            # so a restored database never carries another machine's licence.
            license_dir=paths.license_dir,
        )

        # 6. licence verification — the REAL service, read from the context, so
        #    this log, the login screen, the status bar and the License page all
        #    report one source of truth.
        logger.info("License state: %s", self.context.licensing.summary())
        health = check_health(self.database)
        if health.ok:
            logger.info("Database ready (SQLite %s), schema migrated.", health.sqlite_version)
        else:
            logger.error("Database health degraded: %s", health.message)

        # 7. initial-setup / authentication state is evaluated by the GUI gate.
        logger.info(
            "Initial setup required: %s", self.context.is_setup_required
        )

        return self.config

    def shutdown(self) -> None:
        """Release resources acquired during startup."""
        logger = get_logger("app")
        if self.database is not None:
            self.database.close()
        logger.info("%s shut down cleanly", IDENTITY.product)


def selftest(argv: list[str] | None = None) -> int:
    """Report what this build actually is, then exit (Stage 10 hardening §7).

    A packaged build can be scanned for things that must NOT be in it, but a
    scan cannot prove the licence path is present and working: PyInstaller
    zlib-compresses the Python archive, so our own module strings are not
    visible to a byte scan at all. Asking the binary is the honest check, and
    CI runs exactly this against the frozen executable.

    It only prints. It verifies nothing, unlocks nothing and changes nothing —
    there is no state it can put the application into.
    """
    from zenith_business.core.identity import IDENTITY
    from zenith_business.security import backup_crypto, signatures, vendor_key

    boot = Bootstrap()
    boot.initialize()
    context = boot.context
    assert context is not None
    try:
        state = context.licensing.evaluate()
        print(f"product              : {IDENTITY.product} {IDENTITY.version}")
        print(f"crypto backend       : {signatures.backend_name()}")
        print(f"signature verify     : {signatures.backend_available()}")
        print(f"backup encryption    : {backup_crypto.available()}")
        print(f"vendor key configured: {vendor_key.is_configured()}")
        print(f"licence status       : {state.status}")
        print(f"licence reason       : {state.reason}")
        print(f"machine id           : {state.machine_short}")
        print(f"audit chain          : {context.audit_chain.verify().detail}")
        # A build that cannot verify signatures or encrypt a backup is broken,
        # whether or not a vendor key has been issued yet.
        healthy = signatures.backend_available() and backup_crypto.available()
        print(f"SELFTEST             : {'OK' if healthy else 'FAILED'}")
        return 0 if healthy else 1
    finally:
        boot.shutdown()


def run(argv: list[str] | None = None) -> int:
    """Create the Qt application, gate on authentication, then show the shell."""
    args = list(sys.argv[1:] if argv is None else argv)
    if "--selftest" in args:
        return selftest(args)
    from PyQt6.QtWidgets import QApplication, QDialog

    from zenith_business.ui.auth.auth_window import AuthWindow
    from zenith_business.ui.design.theme import build_stylesheet
    from zenith_business.ui.main_window import MainWindow

    boot = Bootstrap()
    config = boot.initialize()
    context = boot.context
    assert context is not None

    from zenith_business.core.fonts import apply_base_font

    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(IDENTITY.product)
    app.setApplicationDisplayName(IDENTITY.product)
    app.setApplicationVersion(IDENTITY.version)
    app.setOrganizationName(IDENTITY.company)
    apply_base_font(app)  # bundled Vazirmatn — consistent EN + Dari typography
    app.setStyleSheet(build_stylesheet())

    logger = get_logger("app")
    try:
        # Authentication gate → main window loop. Signing out returns here so the
        # login screen appears again without restarting the process.
        while True:
            gate = AuthWindow(context, config)
            if gate.exec() != QDialog.DialogCode.Accepted or gate.authenticated_user is None:
                logger.info("Authentication gate dismissed; exiting.")
                return 0

            relogin = {"requested": False}

            def _logout() -> None:
                context.auth.logout()
                relogin["requested"] = True
                window.close()

            window = MainWindow(
                config,
                database=context.db,
                license_provider=boot.license_provider,
                current_user=gate.authenticated_user,
                on_logout=_logout,
                context=context,
            )
            if config.ui.start_maximized:
                window.showMaximized()
            else:
                window.show()
            app.exec()

            if not relogin["requested"]:
                return 0
    finally:
        boot.shutdown()


def main() -> None:
    """Console-script entry point."""
    raise SystemExit(run())


if __name__ == "__main__":
    main()
